"""Fault controls for transaction-buffer reuse and exact shuffle boundary bags."""
import copy
import json
import re
import time
from profiles import profile


def run(lane,player=None,action=None):
    player=player or lane.player_name
    spec=profile(lane.version);plural=spec['plural_paths']
    directory='loot_tables' if plural else 'loot_table'
    template=json.loads((lane.pack/f'data/tarot/{directory}/decks/numbers.json').read_text())
    offhand=spec['offhand_components'].removesuffix('.components')
    destination=lane.world_dir/f'datapacks/tarot/data/tarot_optimization/{directory}'
    destination.mkdir(parents=True,exist_ok=True)

    def components(loot):
        entry=loot['pools'][0]['entries'][0]
        return (entry['modifier'] if lane.version=='26.3' else entry['functions'][0])['components']

    for size in [0,1,2,3,127,128]:
        loot=copy.deepcopy(template);value=components(loot);original=value['minecraft:charged_projectiles']
        cards=[]
        for i in range(size):
            card=copy.deepcopy(original[i%len(original)])
            card['components']['minecraft:custom_data']['optimization_serial']=str(i)
            card['components']['minecraft:custom_data']['optimization_note']='A separate printing, with its complete components retained.'
            cards.append(card)
        value['minecraft:charged_projectiles']=cards
        (destination/(str(size)+'.json')).write_text(json.dumps(loot))
    lane.rcon('reload');lane.rcon('gamemode survival '+player);lane.rcon('deop '+player)

    def yes(command):return 'Test passed' in lane.rcon(command)

    def wait(label,predicate):
        deadline=time.monotonic()+10
        while not predicate():
            if time.monotonic()>deadline:raise AssertionError(label)
            time.sleep(.05)

    def unchanged(key,path):
        assert yes(f'execute if data entity {player} {path}'),(key,'missing item')
        lane.rcon(f'data modify storage tarot_optimization:oracle compare set from storage tarot_optimization:oracle {key}')
        lane.rcon(f'execute store success score #optimization_changed tarot.sys run data modify storage tarot_optimization:oracle compare set from entity {player} {path}')
        assert 'has 0 ' in lane.rcon('scoreboard players get #optimization_changed tarot.sys'),key

    checks=[]
    for mode in ['equal','different_payload','different_size']:
        lane.rcon('clear '+player)
        lane.rcon(f'loot replace entity {player} hotbar.0 loot tarot_optimization:3')
        lane.rcon(f'item replace entity {player} weapon.offhand with minecraft:diamond[minecraft:custom_data={{control:"retain the exact offhand"}}]')
        if lane.client_process is not None:lane.client_action('hold',slot=0)
        lane.rcon(f'data modify storage tarot_optimization:oracle main set from entity {player} SelectedItem')
        lane.rcon(f'data modify storage tarot_optimization:oracle offhand set from entity {player} {offhand}')
        lane.rcon(f'data modify storage tarot:runtime cards set from entity {player} SelectedItem.components."minecraft:charged_projectiles"')
        lane.rcon(f'data modify storage tarot:runtime prepared set from entity {player} SelectedItem')
        if mode=='different_payload':
            lane.rcon('data modify storage tarot:runtime prepared.components."minecraft:charged_projectiles"[0].components."minecraft:custom_data".codec_fault set value "deliberately changed after validation"')
        if mode=='different_size':
            lane.rcon('data remove storage tarot:runtime prepared.components."minecraft:charged_projectiles"[0]')
        for flag in ['promoted','consume','returning','deliver','committed']:lane.rcon(f'scoreboard players set #{flag} tarot.sys 0')
        lane.rcon('scoreboard players set #size tarot.roll 3')
        lane.rcon('tag @a remove tarot.actor');lane.rcon('tag '+player+' add tarot.actor')
        lane.rcon(f'execute as {player} at @s positioned ~ ~-128 ~ summon minecraft:armor_stand run function tarot:native/stage')
        lane.rcon('tag '+player+' remove tarot.actor')
        expected=1 if mode=='equal' else 0
        assert f'has {expected} ' in lane.rcon('scoreboard players get #committed tarot.sys'),mode
        unchanged('main','SelectedItem');unchanged('offhand',offhand)
        assert not yes('execute if entity @e[tag=tarot.transfer]')
        checks.append({'name':'native_stage_array_'+mode,'passed':True,'committed':bool(expected),
                       'whole_main_and_offhand_unchanged':True,'scope':'Deliberate scratch fault, production native/stage unchanged'})

    last_request=[0.]
    if action is None:
        def action(number):
            time.sleep(max(0.,1.1-(time.monotonic()-last_request[0])));last_request[0]=time.monotonic()
            lane.client_action('chat',text='/trigger tarot.action set '+str(number))
    outcomes=[]
    for size in [0,1,2,3,127,128]:
        lane.rcon('clear '+player);lane.rcon('scoreboard players set '+player+' tarot.cool 0')
        lane.rcon(f'loot replace entity {player} hotbar.0 loot tarot_optimization:{size}')
        if lane.client_process is not None:lane.client_action('hold',slot=0)
        lane.rcon(f'data modify storage tarot_optimization:oracle cards set from entity {player} SelectedItem.components."minecraft:charged_projectiles"')
        lane.rcon('scoreboard players set #committed tarot.sys 0')
        action(2)
        wait('Boundary shuffle commit '+str(size),lambda:'has 1 ' in lane.rcon('scoreboard players get #committed tarot.sys'))
        lane.rcon(f'data modify storage tarot_optimization:oracle actual set from entity {player} SelectedItem.components."minecraft:charged_projectiles"')
        lane.rcon('execute store result score #optimization_size tarot.sys run data get storage tarot_optimization:oracle actual')
        assert f'has {size} ' in lane.rcon('scoreboard players get #optimization_size tarot.sys')
        # Every distinct serial must occur, with its complete original NBT.
        # Together with exact cardinality this proves a bag bijection, including
        # multiple different instances of the same printed card identity.
        for i in range(size):
            path='actual[{components:{"minecraft:custom_data":{optimization_serial:"'+str(i)+'"}}}]'
            assert yes('execute if data storage tarot_optimization:oracle '+path)
            lane.rcon(f'data modify storage tarot_optimization:oracle compare set from storage tarot_optimization:oracle cards[{i}]')
            lane.rcon('execute store success score #optimization_changed tarot.sys run data modify storage tarot_optimization:oracle compare set from storage tarot_optimization:oracle '+path)
            assert 'has 0 ' in lane.rcon('scoreboard players get #optimization_changed tarot.sys'),(size,i)
        outcomes.append({'size':size,'whole_instances_conserved':True})
    checks.append({'name':'descending_shuffle_boundary_bijections','passed':True,'cases':outcomes})
    return checks
