"""Additional dedicated-server regressions. RCON arranges fixtures; named clicks use real clients."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from build import _PROFILES, TARGETS


def run_adversarial(ver, rcon, xdo, count_placed, deck_size, work, shot):
    spec = _PROFILES[ver]
    hand = 'equipment.mainhand' if spec['offhand_components'].startswith('equipment.') else 'HandItems[0]'
    target = next(t for t in TARGETS if t.mc_version == ver)
    with zipfile.ZipFile(work/'server/world/datapacks/Tabletop-Tarot.zip') as pack:
        carpets = json.loads(pack.read(f'{target.data_dir}/data/tarot/tags/{"blocks" if target.plural_folders else "block"}/carpets.json'))['values']
    pale_moss = 'minecraft:pale_moss_carpet' in carpets
    def command(text):
        return rcon.cmd(text)

    def reset():
        command('kill @e[type=minecraft:item_display,tag=tarot.placed]')
        command('kill @e[type=minecraft:interaction,tag=tarot.touch]')
        command('kill @e[type=minecraft:item]')
        command('clear Alice')
        command('clear Bob')
        command('fill -12 -60 -4 12 -53 12 air')
        command('fill -8 -60 3 8 -60 9 oak_planks')
        command('tp Alice 0.5 -60 1.5 0 20')
        command('tp Bob 4 -60 1.5 0 20')
        for disp in (':91', ':92'):
            xdo(disp, 'keyup', 'Shift_L')
            xdo(disp, 'key', '1')
        command('loot replace entity Alice hotbar.0 loot peer:baseline')
        command('loot replace entity Bob hotbar.0 loot tarot:decks/numbers')
        time.sleep(0.3)

    def deal(x=0.5, z=4.5, y=-58.979, player='Alice'):
        # Ordinary non-op /trigger sent from a real client, including its permission check.
        pitch = math.degrees(math.atan2(-58.38 - (y - 0.021), z - 1.5))
        command(f'tp {player} {x} -60 1.5 0 {pitch}')
        time.sleep(0.15)
        disp = ':91' if player == 'Alice' else ':92'
        xdo(disp, 'key', 't')
        time.sleep(0.2)
        xdo(disp, 'type', '--clearmodifiers', '--delay', '1', '/trigger tarot.action set 5')
        time.sleep(0.1)
        xdo(disp, 'key', 'Return')
        time.sleep(0.3)

    def select_target(x, z):
        command('tag @e[tag=tarot.target] remove tarot.target')
        sel = f'@e[type=minecraft:item_display,tag=tarot.placed,x={x},y=-58.979,z={z},distance=..0.15,limit=1]'
        command(f'tag {sel} add tarot.target')
        return sel

    def pickup_direct(x, z):
        # Deterministic function-level event service to test server-side checks, not a mouse claim.
        select_target(x, z)
        command('scoreboard players set Alice tarot.cool 0')
        command('execute as Alice at @s run function tarot:table/player_pickup')
        command('tag @e[tag=tarot.target] remove tarot.target')
        time.sleep(0.15)

    def deck_keys(player):
        raw = command(f'data get entity {player} Inventory[{{Slot:0b}}].components."minecraft:charged_projectiles"')
        return Counter(re.findall(r'key: "([^"]+)"', raw))

    reset()
    original_keys = deck_keys('Alice')
    assert sum(original_keys.values()) == 12, original_keys
    # 1.0.0 deck -> 1.1.0 blind-deal -> reload -> physical pickup: content conservation.
    deal()
    shot(':91', 'non_op_deal.png')
    assert deck_size('Alice', 0) == 11 and count_placed() == 1, (deck_size('Alice', 0), count_placed())
    command('reload')
    time.sleep(0.5)
    assert count_placed() == 1 and deck_size('Alice', 0) == 11
    xdo(':91', 'click', '1')
    deadline = time.monotonic()+8
    while count_placed() != 0 or deck_size('Alice', 0) != 12:
        if time.monotonic()>deadline:
            raise AssertionError('Single native post-reload return did not conserve the complete deck')
        time.sleep(.05)
    assert deck_keys('Alice') == original_keys, 'Released card identities changed across deal/reload/pickup'
    print('  [A1] Released 1.0.0 fixture, non-op client trigger, reload and real pickup conserved 12/12', flush=True)

    reset()
    # Failed ray, occupied destination, full inventory and last-card boundary.
    command('tp Alice 0.5 -60 1.5 0 -60')
    command('execute as Alice at @s run trigger tarot.action set 5')
    time.sleep(0.3)
    assert deck_size('Alice', 0) == 12 and count_placed() == 0
    deal()
    deal()
    assert deck_size('Alice', 0) == 11 and count_placed() == 1
    for i in range(1, 36):
        command(f'item replace entity Alice container.{i} with stone')
    deal(1.5)
    assert deck_size('Alice', 0) == 10 and count_placed() == 2
    # Reduce a deck safely in a test staging entity to a single, actual saved card.
    command('summon armor_stand 8 -60 1 {Tags:["peer.stage"],Invisible:1b,NoGravity:1b}')
    command('item replace entity @e[tag=peer.stage,limit=1] weapon.mainhand from entity Alice weapon.mainhand')
    command(f'data modify storage peer:test one set from entity @e[tag=peer.stage,limit=1] {hand}.components."minecraft:charged_projectiles"[0]')
    command(f'data modify entity @e[tag=peer.stage,limit=1] {hand}.components."minecraft:charged_projectiles" set value []')
    command(f'data modify entity @e[tag=peer.stage,limit=1] {hand}.components."minecraft:charged_projectiles" append from storage peer:test one')
    command('item replace entity Alice weapon.mainhand from entity @e[tag=peer.stage,limit=1] weapon.mainhand')
    command('kill @e[tag=peer.stage]')
    deal(2.5)
    assert deck_size('Alice', 0) == 0 and count_placed() == 3
    deal(3.5)
    assert deck_size('Alice', 0) == 0 and count_placed() == 3
    print('  [A2] Failed/occupied deal rollback, full-inventory deal, last card and empty deck verified', flush=True)

    reset()
    deal(0.5)
    deal(2.0)
    command('fill 1 -59 3 1 -57 6 stone')
    command('tp Alice 0.5 -60 1.5 0 20')
    xdo(':91', 'keydown', 'Shift_L')
    time.sleep(0.2)
    pickup_direct(0.5, 4.5)
    assert deck_size('Alice', 0) == 11 and count_placed() == 1, 'Scoop stole a card through the wall'
    xdo(':91', 'keyup', 'Shift_L')
    print('  [A3] Scoop cannot cross a wall', flush=True)

    reset()
    deal(0.5)
    command('setblock 1 -59 4 oak_slab[type=bottom]')
    deal(1.5, y=-58.479)
    command('tp Alice 0.5 -60 1.5 0 20')
    xdo(':91', 'keydown', 'Shift_L')
    time.sleep(0.2)
    pickup_direct(0.5, 4.5)
    assert deck_size('Alice', 0) == 11 and count_placed() == 1, 'Scoop crossed table levels'
    xdo(':91', 'keyup', 'Shift_L')
    print('  [A4] Scoop cannot cross table heights', flush=True)

    reset()
    deal()
    # A click record served after a wall appears must not operate through it.
    command('fill -1 -59 3 1 -57 3 stone')
    pickup_direct(0.5, 4.5)
    assert deck_size('Alice', 0) == 11 and count_placed() == 1
    command('fill -1 -59 3 1 -57 3 air')
    command('tp Alice 0.5 -60 -2 0 0')
    pickup_direct(0.5, 4.5)
    assert deck_size('Alice', 0) == 11 and count_placed() == 1
    print('  [A5] Delayed interactions recheck wall obstruction and eye reach', flush=True)

    reset()
    deal()
    keys_before = deck_keys('Alice') + deck_keys('Bob')
    card_key = command('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] item.components."minecraft:custom_data".tarot.key').split('entity data: ', 1)[-1].strip('"')
    keys_before[card_key] += 1
    # Both real network clients attack the same entity; exactly one receives it.
    pitch = math.degrees(math.atan2(0.62, 3.0))
    command(f'tp Alice 0.5 -60 1.5 0 {pitch}')
    command(f'tp Bob 0.5 -60 7.5 180 {pitch}')
    time.sleep(0.3)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda disp: xdo(disp, 'click', '1'), (':91', ':92')))
    time.sleep(0.5)
    assert deck_size('Alice', 0) + deck_size('Bob', 0) == 24 and count_placed() == 0
    assert deck_keys('Alice') + deck_keys('Bob') == keys_before, 'Race changed card identities'
    print('  [A6] Two real clients racing the same pickup conserve exactly one card', flush=True)

    reset()
    command('gamerule ' + spec['command_rule'] + ' 32768')
    deal()
    assert deck_size('Alice', 0) == 12 and count_placed() == 0
    command('gamerule ' + spec['command_rule'] + ' 65536')
    print('  [A7] Low-command-budget admission refuses mutation', flush=True)

    def resize_deck(size):
        command('summon armor_stand 8 -60 1 {Tags:["peer.stage"],Invisible:1b,NoGravity:1b}')
        command('item replace entity @e[tag=peer.stage,limit=1] weapon.mainhand from entity Alice weapon.mainhand')
        path = f'{hand}.components."minecraft:charged_projectiles"'
        command(f'data modify storage peer:test one set from entity @e[tag=peer.stage,limit=1] {path}[0]')
        command(f'data modify entity @e[tag=peer.stage,limit=1] {path} set value []')
        for _ in range(size):
            command(f'data modify entity @e[tag=peer.stage,limit=1] {path} append from storage peer:test one')
        command('item replace entity Alice weapon.mainhand from entity @e[tag=peer.stage,limit=1] weapon.mainhand')
        command('kill @e[tag=peer.stage]')

    reset()
    resize_deck(128)
    # A dense but legal 20-card spread; collect only the bounded 16-card batch.
    for i in range(20):
        x = -0.4 + (i % 7) * 0.3
        z = 4.0 + (i // 7) * 0.3
        deal(x, z)
    assert deck_size('Alice', 0) == 108 and count_placed() == 20
    layers = []
    for i in range(20):
        x, z = -0.4 + (i % 7) * 0.3, 4.0 + (i // 7) * 0.3
        sel = f'@e[type=minecraft:item_display,tag=tarot.placed,x={x},y=-58.979,z={z},distance=..0.15,limit=1]'
        layer = rcon.score(sel, 'tarot.layer')
        for px, pz, pl in layers:
            if math.hypot(px - x, pz - z) < 0.6:
                assert layer != pl, 'Overlapping neighbors share a height layer'
        layers.append((x, z, layer))

    command('tp Alice 0.5 -60 1.5 0 20')
    xdo(':91', 'keydown', 'Shift_L')
    time.sleep(0.2)
    pickup_direct(0.5, 4.0)
    xdo(':91', 'keyup', 'Shift_L')
    assert deck_size('Alice', 0) == 124 and count_placed() == 4, 'Scoop batch did not stop at 16'
    print('  [A8] Dense 20-card layout, 16-card scoop bound and 128-card conservation verified', flush=True)

    reset()
    for x in (0.2, 0.5, 0.8):
        deal(x)
    resize_deck(126)
    command('tp Alice 0.5 -60 1.5 0 20')
    xdo(':91', 'keydown', 'Shift_L')
    time.sleep(0.2)
    pickup_direct(0.5, 4.5)
    assert deck_size('Alice', 0) == 128 and count_placed() == 1
    xdo(':91', 'keyup', 'Shift_L')
    print('  [A9] Capacity boundary gathers two into 126 and leaves the third on the table', flush=True)

    reset()
    # Malformed native data must not partially deal or consume the deck.
    command('summon armor_stand 8 -60 1 {Tags:["peer.stage"],Invisible:1b,NoGravity:1b}')
    command('item replace entity @e[tag=peer.stage,limit=1] weapon.mainhand from entity Alice weapon.mainhand')
    command(f'data modify entity @e[tag=peer.stage,limit=1] {hand}.components."minecraft:charged_projectiles"[0].components."minecraft:custom_data".tarot.key set value "numbers/not-a-card"')
    command('item replace entity Alice weapon.mainhand from entity @e[tag=peer.stage,limit=1] weapon.mainhand')
    command('kill @e[tag=peer.stage]')
    deal()
    assert deck_size('Alice', 0) == 12 and count_placed() == 0
    print('  [A10] Malformed native deck refuses blind deal without mutation', flush=True)

    reset()
    # Queue accounting: inspect a dispatch with no heavy capacity before the next tick.
    command('tick freeze')
    command('scoreboard players set #heavy_left tarot.sys 0')
    command('scoreboard players set Alice tarot.pending 5')
    command('tag Alice add tarot.waiting')
    command('execute as Alice at @s run function tarot:queue/player_serve')
    waiting = command('execute if entity @a[name=Alice,tag=tarot.waiting,limit=1]')
    assert 'passed' in waiting.lower(), waiting
    command('tag Alice remove tarot.waiting')
    command('scoreboard players set Alice tarot.pending 0')
    command('tick unfreeze')
    print('  [A11] Blind-deal work defers intact when the heavy allowance is exhausted', flush=True)

    if pale_moss:
        reset()
        command('setblock 0 -59 4 pale_moss_carpet[bottom=true]')
        deal(y=-58.9165)
        assert count_placed() == 1
        command('setblock 0 -59 3 stone')
        command('setblock 0 -59 4 pale_moss_carpet[bottom=false,north=low]')
        time.sleep(0.5)
        assert count_placed() == 0, 'Wall-only pale moss retained horizontal support'
        command('execute store result score #drop_count tarot.sys if entity @e[type=minecraft:item]')
        assert rcon.score('#drop_count', 'tarot.sys') == 1
        print('  [A12] Pale moss losing its bottom releases the actual card', flush=True)

    reset()
    resize_deck(128)
    command('item replace entity Bob weapon.mainhand from entity Alice weapon.mainhand')
    pitch = math.degrees(math.atan2(0.62, 3.0))
    command(f'tp Alice 0.2 -60 1.5 0 {pitch}')
    command(f'tp Bob 0.8 -60 1.5 0 {pitch}')
    time.sleep(0.2)
    command('tick freeze')
    command('execute as Alice run trigger tarot.action set 5')
    command('execute as Bob run trigger tarot.action set 5')
    result = command('debug function tarot:tick')
    if 'Unknown' in result or 'Incorrect' in result:
        result += '\n' + command('function tarot:tick')
    (work / 'two_128_deal_trace.txt').write_text(result + '\n')
    assert deck_size('Alice', 0) == 127 and deck_size('Bob', 0) == 127 and count_placed() == 2, result
    assert rcon.score('#heavy_left', 'tarot.sys') == 0
    command('tick unfreeze')
    print('  [A13] Two queued 128-card blind deals share the allowance and conserve 256/256', flush=True)
    return 13 if pale_moss else 12
