"""Live native ItemStack cases for the factored structural/identity validator."""
import copy
import json
import re
import time

from profiles import profile


def run(lane, player=None, action=None):
    player = player or lane.player_name
    spec = profile(lane.version)
    directory = 'loot_tables' if spec['plural_paths'] else 'loot_table'
    original = lane.pack/f'data/tarot/{directory}/decks'
    numbers = json.loads((original/'numbers.json').read_text())
    rider = json.loads((original/'rider.json').read_text())

    def components(loot):
        entry = loot['pools'][0]['entries'][0]
        return (entry['modifier'] if lane.version == '26.3' else entry['functions'][0])['components']

    first, second = copy.deepcopy(components(numbers)['minecraft:charged_projectiles'][:2])
    rider_card = copy.deepcopy(components(rider)['minecraft:charged_projectiles'][0])
    foreign = copy.deepcopy(first); foreign['id'] = 'minecraft:stone'
    wrong_pair = copy.deepcopy(first); wrong_pair['components']['minecraft:custom_data']['tarot']['module'] = 'rider'
    wrong_kind = copy.deepcopy(first); wrong_kind['components']['minecraft:custom_data']['tarot']['kind'] = 'deck'
    unknown = copy.deepcopy(first); unknown['components']['minecraft:custom_data']['tarot']['key'] = 'numbers/not-installed'
    counted = copy.deepcopy(second); counted['count'] = 2
    # Paper's vanilla stack limit permits this malformed-for-Tarot count, so the
    # host codec accepts the fixture and the datapack must reject it itself.
    counted['id'] = 'minecraft:paper'
    counted['components'].pop('minecraft:max_stack_size', None)
    missing = copy.deepcopy(first); del missing['components']['minecraft:custom_data']['tarot']['key']
    omitted = copy.deepcopy(first); omitted.pop('count', None)
    cases = [
        ('foreign_carrier', [foreign], False),
        ('key_module_pair_mismatch', [wrong_pair], False),
        ('wrong_kind', [wrong_kind], False),
        ('complementary_invalid_rows', [unknown, foreign], False),
        ('valid_singleton_plus_explicit_count_two', [omitted, counted], False),
        ('missing_key', [missing], False),
        ('omitted_and_explicit_default_counts', [omitted, second], True),
        ('valid_mixed_modules', [first, rider_card], True),
    ]
    destination = lane.world_dir/f'datapacks/tarot/data/tarot_native/{directory}'
    destination.mkdir(parents=True, exist_ok=True)
    for name, cards, _ in cases:
        loot = copy.deepcopy(numbers)
        value = components(loot)
        value['minecraft:charged_projectiles'] = cards
        value['minecraft:custom_data']['native_case'] = name
        (destination/(name+'.json')).write_text(json.dumps(loot, ensure_ascii=False))
    return_loot = copy.deepcopy(numbers)
    entry = return_loot['pools'][0]['entries'][0]
    entry['name'] = first['id']
    value = components(return_loot); value.clear(); value.update(copy.deepcopy(first['components']))
    value['minecraft:custom_data']['native_return_note'] = 'keep this exact offhand item'
    (destination/'return_card.json').write_text(json.dumps(return_loot, ensure_ascii=False))
    lane.rcon('reload')
    lane.rcon('gamemode survival '+player); lane.rcon('deop '+player)

    def wait(label, predicate):
        deadline = time.monotonic()+8
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError(label)
            time.sleep(.025)

    def size():
        lane.rcon(f'execute store result score #native_size tarot.sys run data get entity {player} SelectedItem.components."minecraft:charged_projectiles"')
        reply = lane.rcon('scoreboard players get #native_size tarot.sys')
        return int(re.search(r'has (-?\d+) ', reply)[1])

    if action is None:
        last_request = [0.]
        def action(number):
            # Exercise an ordinary non-operator without tripping vanilla chat spam protection.
            remaining = 1.1-(time.monotonic()-last_request[0])
            if remaining > 0:
                time.sleep(remaining)
            last_request[0] = time.monotonic()
            return lane.client_action('chat', text='/trigger tarot.action set '+str(number))
    offhand = spec['offhand_components'].removesuffix('.components')
    checks = []
    for name, cards, accepted in cases:
        lane.rcon('clear '+player)
        lane.rcon('scoreboard players set '+player+' tarot.cool 0')
        reply = lane.rcon(f'loot replace entity {player} hotbar.0 loot tarot_native:{name}')
        if 'Test passed' not in lane.rcon(f'execute if data entity {player} SelectedItem.components."minecraft:custom_data"{{native_case:"{name}"}}'):
            raise AssertionError('Native wrapper fixture was not installed: '+reply)
        lane.rcon(f'loot replace entity {player} weapon.offhand loot tarot_native:return_card')
        if lane.client_process is not None:
            lane.client_action('hold', slot=0)
        assert size() == len(cards), name+' did not install every native row'
        lane.rcon(f'data modify storage tarot_native:oracle main set from entity {player} SelectedItem')
        lane.rcon(f'data modify storage tarot_native:oracle offhand set from entity {player} {offhand}')
        if accepted:
            action(1)
            wait('Valid native draw: '+name, lambda: size() == len(cards)-1)
            found = lane.rcon(f'clear {player} #tarot:card_carriers[minecraft:custom_data~{{tarot:{{kind:"card"}}}}] 0')
            assert 'Found 2 ' in found, found  # delivered card plus the untouched offhand control
            checks.append({'name':'native_accept_'+name,'passed':True,'cards':len(cards)})
        else:
            for number in (1,2,3):
                lane.rcon('scoreboard players set '+player+' tarot.pending 0')
                action(number)
                assert f'has {number} ' in lane.rcon('scoreboard players get '+player+' tarot.pending'), 'Native input was not captured'
                for key, path in [('main','SelectedItem'),('offhand',offhand)]:
                    assert 'Test passed' in lane.rcon(f'execute if data entity {player} {path}'), (name, number, key, 'missing item')
                    lane.rcon(f'data modify storage tarot_native:oracle compare set from storage tarot_native:oracle {key}')
                    lane.rcon(f'execute store success score #native_changed tarot.sys run data modify storage tarot_native:oracle compare set from entity {player} {path}')
                    assert 'has 0 ' in lane.rcon('scoreboard players get #native_changed tarot.sys'), (name, number, key)
                assert 'Test passed' not in lane.rcon('execute if entity @e[tag=tarot.transfer]')
            checks.append({'name':'native_reject_'+name,'passed':True,'actions':3,'whole_main_and_offhand_unchanged':True})
        print(checks[-1]['name'], flush=True)
    return checks
