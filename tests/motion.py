"""Actual stock-client motion capture plus interruption and custody regressions."""
import hashlib
import json
import math
import re
import subprocess
import time
import zipfile

from build import _PROFILES


def run_motion(version, rcon, xdo, work, shot, baseline=False):
    cmd = rcon.cmd
    display = '@e[type=minecraft:item_display,tag=tarot.placed,limit=1]'
    recordings = []
    checks = []
    archive = work/'server/world/datapacks/Tabletop-Tarot.zip'
    with zipfile.ZipFile(archive) as source:
        has_motion = any(name.endswith('/motion/step.mcfunction') for name in source.namelist())
    assert has_motion != baseline, 'Motion admission does not match the supplied archive'
    for player in ['Alice','Bob']:
        assert any('Reloading ResourceManager' in line and 'server/' in line for line in
                   (work/f'client_{player}.log').read_text(errors='replace').splitlines()), 'Client resource pack was not applied'

    def wait(label, predicate):
        deadline = time.monotonic()+6
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError(label)
            time.sleep(.025)

    def yes(command):
        return 'passed' in cmd(command).lower()

    def ticks():
        return int(re.findall(r'\d+', cmd('time query gametime'))[-1])

    def native_chat(text):
        # Wait for the rendered input bar, so a busy render thread cannot send
        # command digits to the hotbar before its queued chat-open key is served.
        def brightness():
            result = subprocess.run(['import','-window','root','-crop','1x1+32+708','-depth','8','rgb:-'],
                env={**__import__('os').environ,'DISPLAY':':91'}, capture_output=True, check=True)
            assert len(result.stdout) == 3
            return sum(result.stdout)
        before = brightness()
        xdo(':91','key','t')
        wait('Chat input did not open', lambda: brightness() < before*.72)
        xdo(':91','type','--clearmodifiers','--delay','1',text)
        xdo(':91','key','Return')

    def after_ticks(count):
        start = ticks()
        wait('World tick progress', lambda: ticks() >= start+count)

    def vector(path):
        reply = cmd(f'data get entity {display} {path}')
        assert 'following entity data:' in reply, reply
        return [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?', reply.split('following entity data:',1)[1])]

    def aim(player, crouching=False):
        x, y, z = vector('Pos')
        player_z = .5 if player == 'Alice' else 4.5
        pitch = math.degrees(math.atan2(-60+(1.27 if crouching else 1.62)-(y+.04), abs(z-player_z)))
        cmd(f'tp {player} {x} -60 {player_z} {0 if player=="Alice" else 180} {pitch}')

    def click(player, button=3):
        wait('Player input eligibility', lambda: rcon.score(player,'tarot.cool') == 0)
        xdo(':91' if player == 'Alice' else ':92', 'click', str(button))

    def settled():
        wait('Motion did not settle', lambda: not yes('execute if entity @e[type=minecraft:item_display,tag=tarot.moving]'))

    def face():
        return rcon.score(display, 'tarot.face')

    def flip(player):
        previous = face()
        click(player)
        wait('Native flip did not change the logical face', lambda: face() == 1-previous)
        return previous

    def start_capture(player, screen):
        log = (work/f'motion-{player}.ffmpeg.log').open('w')
        process = subprocess.Popen(['ffmpeg','-y','-loglevel','warning','-f','x11grab','-framerate','60',
            '-video_size','1280x720','-draw_mouse','0','-i',screen+'.0','-an','-c:v','ffv1',
            '-threads','1','-level','3','-pix_fmt','bgr0',str(work/f'motion-{player}.mkv')],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log, text=True)
        recordings.append((process,log))

    def stop_capture():
        for process, log in recordings:
            if process.poll() is None:
                process.stdin.write('q\n'); process.stdin.flush()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate(); process.wait(timeout=5)
            log.close()
            assert process.returncode == 0, 'Screen recording failed'
        recordings.clear()

    cmd('kill @e[type=minecraft:item_display,tag=tarot.placed]')
    cmd('kill @e[type=minecraft:interaction,tag=tarot.touch]')
    cmd('kill @e[type=minecraft:item]')
    for player in ['Alice','Bob']:
        cmd('ride '+player+' dismount')
        cmd('clear '+player); cmd('gamemode survival '+player); cmd('deop '+player)
    cmd('fill -3 -60 -2 3 -57 7 air')
    cmd('fill -2 -60 2 2 -60 3 oak_planks')
    cmd('setblock 0 -59 2 purple_carpet')
    cmd('loot replace entity Alice hotbar.0 loot tarot:decks/numbers')
    cmd('tp Alice 0.5 -60 0.5 0 20')
    cmd('tp Bob 0.5 -60 4.5 180 20')
    xdo(':91','key','1')
    native_chat('/trigger tarot.action set 5')
    wait('Native blind deal failed', lambda: yes(f'execute if entity {display}'))
    settled()
    aim('Alice'); aim('Bob')
    cmd('execute store result score #motion_cards tarot.sys run data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
    assert rcon.score('#motion_cards','tarot.sys') == 11
    xdo(':91','key','F1'); xdo(':92','key','F1')
    time.sleep(6)
    idle_query = cmd('tick query')
    cmd(f'data modify storage tarot_motion:oracle item set from entity {display} item')
    uuid_reply = cmd(f'data get entity {display} UUID')
    shot(':91','motion-before.png')
    start_capture('Alice',':91'); start_capture('Bob',':92')
    time.sleep(.4)
    try:
        for player in ['Alice','Bob','Alice','Bob']:
            flip(player)
            if not baseline:
                assert yes('execute if entity @e[type=minecraft:item_display,tag=tarot.moving]'), 'Flip skipped its motion state'
            settled(); after_ticks(3)
        checks.append('native flips from both clients settle to the accepted face')
        # A second player may change the accepted face while the first turn is in flight.
        flip('Alice')
        was_moving = yes('execute if entity @e[type=minecraft:item_display,tag=tarot.moving]')
        flip('Bob')
        if not baseline:
            assert was_moving
        settled(); after_ticks(3)
        assert face() == 0
        assert abs(vector('transformation.translation')[1]) < 1e-6
        assert vector('transformation.right_rotation') == [0.,0.,0.,1.]
        checks.append('interrupted two-client turn keeps the latest face and returns to the tabletop')
        before = vector('Rotation')[0]
        xdo(':91','keydown','Shift_L')
        try:
            wait('Sneak intent', lambda: yes('execute as Alice if predicate tarot:is_sneaking'))
            aim('Alice',True)
            click('Alice')
            wait('Native rotation failed', lambda: abs((vector('Rotation')[0]-before)%360-45) < 1e-4)
        finally:
            xdo(':91','keyup','Shift_L')
        after_ticks(6); aim('Alice')
        if not baseline:
            assert yes(f'execute if data entity {display} {{teleport_duration:3}}')
        checks.append('native rotation preserves exact 45-degree tabletop alignment')
        assert yes(f'execute if data entity {display} item')
        cmd('data modify storage tarot_motion:oracle compare set from storage tarot_motion:oracle item')
        cmd(f'execute store success score #motion_changed tarot.sys run data modify storage tarot_motion:oracle compare set from entity {display} item')
        assert rcon.score('#motion_changed','tarot.sys') == 0
        shot(':91','motion-after.png'); shot(':92','motion-after-Bob.png')
        normal_query = cmd('tick query')
        time.sleep(.4)
    finally:
        stop_capture()
    if not baseline:
        flip('Bob')
        cmd('data modify storage tarot:config schema set value 7')
        cmd('reload')
        settled()
        assert face() == 1 and vector('transformation.right_rotation') == [0.,1.,0.,0.]
        assert yes('execute if data storage tarot:config {schema:8}')
        cmd(f'data merge entity {display} {{teleport_duration:0}}')
        cmd(f'tag {display} remove tarot.motion_ready')
        wait('Older display interpolation defaults were not upgraded', lambda: yes('execute if entity @e[type=minecraft:item_display,tag=tarot.placed,tag=tarot.motion_ready]'))
        assert yes(f'execute if data entity {display} {{teleport_duration:3}}')
        checks.append('reload during a turn settles correctly and saved older displays acquire interpolation defaults')
    # Custody changes must remain immediate during a purely visual transition.
    flip('Alice' if not baseline else 'Bob')
    xdo(':91','key','2'); click('Alice',1)
    wait('Pickup during motion failed', lambda: not yes(f'execute if entity {display}'))
    assert yes('execute if items entity Alice hotbar.1 #tarot:card_carriers[minecraft:custom_data~{tarot:{key:"numbers/number-1"}}]')
    assert not yes('execute if entity @e[type=minecraft:interaction,tag=tarot.touch]')
    if not baseline:
        ints = [int(v) for v in re.findall(r'-?\d+', uuid_reply.split('[I;',1)[1])]
        import uuid
        card_uuid = str(uuid.UUID(int=sum((v&0xffffffff) << (32*(3-i)) for i,v in enumerate(ints))))
        assert ' has ' not in cmd(f'scoreboard players get {card_uuid} tarot.motion'), 'Dead display retained motion score'
    checks.append('pickup during a turn transfers exactly one card and cleans its hitbox and motion score')
    start_capture('placement',':91')
    try:
        time.sleep(.25)
        click('Alice')
        wait('Replacement failed', lambda: yes(f'execute if entity {display}'))
        placed_position = vector('Pos')
        settled(); after_ticks(3)
        assert vector('Pos') == placed_position
        assert vector('transformation.translation') == [0.,0.,0.]
        time.sleep(.25)
    finally:
        stop_capture()
    checks.append('native placement settles visually while logical support position remains fixed')
    aim('Alice'); aim('Bob')
    if not baseline:
        flip('Bob')
        rule = _PROFILES[version]['command_rule']
        previous_budget = int(re.findall(r'\d+',cmd('gamerule '+rule))[-1])
        try:
            cmd('gamerule '+rule+' 32768')
            after_ticks(2)
            saved = rcon.score(display,'tarot.motion')
            after_ticks(5)
            assert rcon.score(display,'tarot.motion') == saved
        finally:
            cmd('gamerule '+rule+' '+str(previous_budget))
        settled()
        checks.append('reduced command budget pauses motion intact and resumes it afterward')
    flip('Alice')
    cmd('setblock 0 -59 2 air')
    wait('Support loss during motion failed', lambda: not yes(f'execute if entity {display}'))
    cmd('tp Alice 0.5 -59 2.5')
    wait('Released card pickup failed', lambda: yes('execute if items entity Alice hotbar.1 #tarot:card_carriers[minecraft:custom_data~{tarot:{key:"numbers/number-1"}}]'))
    assert not yes('execute if entity @e[tag=tarot.moving]')
    assert not yes('execute if entity @e[type=minecraft:interaction,tag=tarot.touch]')
    cmd('execute store result score #motion_cards tarot.sys run data get entity Alice Inventory[{Slot:0b}].components."minecraft:charged_projectiles"')
    assert rcon.score('#motion_cards','tarot.sys') == 11
    checks.append('support loss during motion preserves the complete 12-card deck custody')
    archive = work/'server/world/datapacks/Tabletop-Tarot.zip'
    (work/'motion-result.json').write_text(json.dumps({'minecraft':version,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'passed':True,'baseline':baseline,'checks':checks,'idle_tick_query':idle_query,'normal_interactions_tick_query':normal_query,
        'scope':'two stock graphical clients, native mouse/keyboard input, actual screen recordings; RCON fixture setup and state inspection'},indent=2)+'\n')
