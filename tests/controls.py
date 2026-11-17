"""A complete physical deck cycle, including vanilla offhand priority controls."""
import hashlib
import json
import math
import re
import time
from collections import Counter


def run_controls(version, rcon, xdo, work):
    cmd = rcon.cmd

    def wait(label, predicate):
        deadline = time.monotonic() + 5
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError(label)
            time.sleep(0.05)

    def size():
        cmd('execute store result score #control_size tarot.sys run data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
        return rcon.score('#control_size','tarot.sys')

    def keys():
        return re.findall(r'key: "([^"]+)"',cmd('data get entity Alice SelectedItem.components."minecraft:charged_projectiles"'))

    def sneak(enabled):
        xdo(':91','keydown' if enabled else 'keyup','Shift_L')
        wait('Sneak state did not reach server',lambda: ('passed' in cmd('execute as Alice if predicate tarot:is_sneaking').lower()) == enabled)

    def use():
        wait('Input cooldown did not drain',lambda:rcon.score('Alice','tarot.cool')==0)
        xdo(':91','click','3')

    def ticks():
        return int(re.findall(r'\d+',cmd('time query gametime'))[-1])

    cmd('kill @e[type=minecraft:item_display,tag=tarot.placed]')
    cmd('kill @e[type=minecraft:interaction,tag=tarot.touch]')
    cmd('kill @e[type=minecraft:item]')
    cmd('clear Alice'); cmd('clear Bob')
    cmd('gamemode survival Alice')
    cmd('tp Bob -10.5 -60 -8.5')
    cmd('fill 6 -60 -3 10 -55 3 air')
    cmd('setblock 8 -60 1 stone')
    cmd('loot replace entity Alice hotbar.0 loot tarot:decks/numbers')
    cmd('tp Alice 8.5 -60 -1.5 0 -45')
    xdo(':91','key','1')
    wait('Initial deck missing',lambda:size()==12)
    original = keys()
    use(); wait('Physical right-click did not draw',lambda:size()==11)
    assert keys()==original[1:]
    before = keys()
    sneak(True)
    try:
        for _ in range(3):
            use(); time.sleep(0.3)
            assert Counter(keys())==Counter(before), 'Physical shuffle changed membership'
            if keys()!=before:
                break
        else:
            raise AssertionError('Physical shuffle never permuted')
        cmd('item replace entity Alice weapon.offhand from entity Alice hotbar.1')
        cmd('item replace entity Alice hotbar.1 with air')
        time.sleep(0.3)
        use(); wait('Sneak-use did not return the offhand card',lambda:size()==12)
        assert keys()[0]==original[0] and Counter(keys())==Counter(original)
        assert 'passed' not in cmd('execute if items entity Alice weapon.offhand *').lower()
    finally:
        sneak(False)
    cases=['physical right-click top draw','physical sneak-use shuffle','physical offhand return']
    print('  [C1] Physical draw, shuffle and offhand return preserve the complete Numbers deck',flush=True)

    pitch=math.degrees(math.atan2(0.62,3.0))
    cmd(f'tp Alice 8.5 -60 -1.5 0 {pitch}')
    for count in (64,1):
        cmd('setblock 8 -59 1 air')
        cmd(f'item replace entity Alice weapon.offhand with torch {count}')
        time.sleep(0.3)
        use()
        wait('Vanilla offhand torch was not placed',lambda:'passed' in cmd('execute if block 8 -59 1 torch').lower())
        if count==1:
            assert 'passed' not in cmd('execute if items entity Alice weapon.offhand *').lower(), 'Last torch was not consumed'
        else:
            assert 'passed' in cmd('execute if items entity Alice weapon.offhand minecraft:torch[minecraft:count=63]').lower(), 'Torch control did not consume one item'
        start=ticks(); wait('World did not settle after torch use',lambda:ticks()>=start+6)
        assert size()==12, f'Offhand torch stack {count} also drew a card'
        cases.append(f'vanilla offhand torch placement from stack {count} does not also draw')
    print('  [C2] Both ordinary and last-item offhand torch placement leave the deck intact',flush=True)

    cmd('item replace entity Alice weapon.offhand with torch 2')
    xdo(':91','key','t'); time.sleep(0.2)
    xdo(':91','type','--clearmodifiers','--delay','1','/trigger tarot.action set 1')
    xdo(':91','key','Return')
    wait('Explicit draw with an occupied offhand did not work',lambda:size()==11)
    cmd('item replace entity Alice weapon.offhand with air')
    cmd('setblock 8 -59 1 air')
    xdo(':91','key','2'); time.sleep(0.2)
    use()
    wait('Loose card did not place',lambda:'passed' in cmd('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]').lower())
    xdo(':91','click','1')
    wait('Empty-hand pickup left the display',lambda:'passed' not in cmd('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]').lower())
    assert 'passed' in cmd('execute if items entity Alice hotbar.1 #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}]').lower()
    assert 'passed' not in cmd('execute if entity @e[type=minecraft:interaction,tag=tarot.touch]').lower()
    cases+=['explicit draw with occupied offhand','native loose-card placement and empty-hand pickup']
    print('  [C3] Explicit occupied-offhand draw and native empty-hand tabletop pickup verified',flush=True)
    archive=work/'server/world/datapacks/Tabletop-Tarot.zip'
    (work/'controls-result.json').write_text(json.dumps({'minecraft':version,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'passed':True,'cases':cases,'scope':'actual stock-client mouse/keyboard inputs; RCON prepares fixtures and observes server state'},indent=2)+'\n')
