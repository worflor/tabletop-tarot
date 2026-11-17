"""Backend lifecycle probes with an idle stock client on protocol-only gaps.

Attach only to the owned visual-server world. These are RCON fixture/action
probes, not claims of additional native mouse input or the full protocol suite.
"""
import argparse,json,time,re,shutil
from pathlib import Path
from game_lab import VanillaLane,RUNTIME,write_json,sha

def main(version,universal_lane=None):
    lane=universal_lane or VanillaLane(version)
    if universal_lane is None:
        server=RUNTIME/f'visual-{version}/server-{version}'
        props=dict(line.split('=',1) for line in (server/'server.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
        lane.server_dir=server;lane.world_dir=server/props['level-name'];lane.game_port=int(props['server-port']);lane.rcon_port=int(props['rcon.port']);lane.password=props['rcon.password']
    result={'minecraft':version,'scope':'official vanilla server with an idle unmodified stock client; RCON fixtures and queued action probes, not mouse input or full protocol suite','checks':[]}
    def record(name):result['checks'].append({'name':name,'passed':True});print(name,flush=True)
    def command(s):return lane.rcon(s)
    def wait(s,predicate,label):
        until=time.monotonic()+20
        while True:
            value=command(s)
            if predicate(value):return value
            if time.monotonic()>until:raise TimeoutError(label+': '+value)
            time.sleep(.1)
    def value(s):
        response=command(s)
        if 'following entity data:' not in response:raise AssertionError(response)
        return response.split('following entity data:',1)[1].strip()
    def action(n):
        command(f'scoreboard players set TarotVisual tarot.action {n}')
        wait('scoreboard players get TarotVisual tarot.action',lambda r:'has 0 ' in r,'action queue drain')
    display='@e[type=minecraft:item_display,tag=tarot.placed,limit=1]'
    touch='@e[type=minecraft:interaction,tag=tarot.touch,limit=1]'
    def event(name):
        ticks=int(re.findall(r'\d+',command('time query gametime'))[-1])
        command('data modify storage tarot_lab:native event set value {timestamp:'+str(ticks)+'L}')
        command('data modify storage tarot_lab:native event.player set from entity TarotVisual UUID')
        command(f'data modify entity {touch} {name} set from storage tarot_lab:native event')
    try:
        wait('list',lambda r:'TarotVisual' in r,'stock client login')
        staged=lane.world_dir/'datapacks/tarot'
        if not staged.resolve().is_relative_to(lane.server_dir.resolve()):raise ValueError('Unexpected world path')
        # Replace only generated fixture files, within this owned test pack.
        desired={p.relative_to(lane.pack) for p in lane.pack.rglob('*') if p.is_file()}
        for p in staged.rglob('*'):
            if p.is_file() and p.relative_to(staged) not in desired:p.unlink()
        if universal_lane is None:shutil.copytree(lane.pack,staged,dirs_exist_ok=True)
        command('reload');time.sleep(1)
        if universal_lane is not None:
            result['combined_zip_sha256']=sha(lane.archive)
            result['scope']+='; all production code from the combined ZIP, loose pack contains observer fixtures only'
            result['datapack_list']=command('datapack list enabled')
        result['datapack_sha256']={p.relative_to(lane.pack).as_posix():sha(p) for p in lane.pack.rglob('*') if p.is_file()}
        command('clear TarotVisual');command('tp TarotVisual 0.5 -60 0.5 0 20');command('gamemode survival TarotVisual');command('deop TarotVisual')
        # A default singleton can omit count on26.3; an explicit count2 must not pass the same identity check.
        command('item replace entity TarotVisual hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data={tarot:{kind:"deck",module:"numbers",storage:"native-v1"}},minecraft:charged_projectiles=[{id:"minecraft:paper",count:2,components:{"minecraft:custom_data":{tarot:{kind:"card",module:"numbers",key:"numbers/number-1"}}}}]]')
        counted=value('data get entity TarotVisual SelectedItem')
        for number in [1,2,3]:
            action(number)
            if value('data get entity TarotVisual SelectedItem')!=counted or 'No items' not in command('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0'):raise AssertionError('Count2 native card admitted')
        record('native_explicit_count_two_rejected_without_mutation')
        command('clear TarotVisual')
        command('setblock 4 -60 0 minecraft:chest');command('setblock 0 -60 2 minecraft:oak_planks');command('execute as TarotVisual run function tarot:give/numbers')
        action(1);wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'Found 1 ' in r,'top draw delivery')
        if 'number-2' not in value('data get entity TarotVisual SelectedItem.components."minecraft:charged_projectiles"[0].components."minecraft:custom_data".tarot.key'):raise AssertionError('New adapter did not draw the top card')
        record('queued_top_draw_with_stock_player_context')
        folder=staged/'data/tarot/function/native_lab';folder.mkdir(parents=True,exist_ok=True)
        (folder/'compare_loop.mcfunction').write_text('execute unless data storage tarot_lab:native todo[0] run return 0\ndata modify storage tarot_lab:native row set from storage tarot_lab:native todo[0]\nfunction tarot:native_lab/compare_row with storage tarot_lab:native\nexecute unless score #removed tarot.sys matches 1 run scoreboard players set #bag tarot.sys 0\ndata remove storage tarot_lab:native todo[0]\nfunction tarot:native_lab/compare_loop\n')
        (folder/'compare_row.mcfunction').write_text('$execute store result score #removed tarot.sys run data remove storage tarot_lab:native before[$(row)]\n')
        command('reload');time.sleep(.5)
        command('data modify storage tarot_lab:native before set from entity TarotVisual SelectedItem.components."minecraft:charged_projectiles"')
        command('data modify storage tarot_lab:native order_before set from storage tarot_lab:native before')
        for _ in range(4):
            action(2);command('execute store success score #changed tarot.sys run data modify storage tarot_lab:native order_before set from entity TarotVisual SelectedItem.components."minecraft:charged_projectiles"')
            if 'has 1 ' in command('scoreboard players get #changed tarot.sys'):break
        else:raise AssertionError('Indexed shuffle never changed order on new adapter')
        command('data modify storage tarot_lab:native todo set from entity TarotVisual SelectedItem.components."minecraft:charged_projectiles"');command('scoreboard players set #bag tarot.sys 1');command('function tarot:native_lab/compare_loop')
        if 'has 1 ' not in command('scoreboard players get #bag tarot.sys') or 'Test passed' not in command('execute if data storage tarot_lab:native {before:[]}'):raise AssertionError('Indexed shuffle changed serialized card instances')
        record('indexed_shuffle_changes_order_and_preserves_complete_remaining_items')
        command('item replace block 4 -60 0 container.0 from entity TarotVisual hotbar.0');command('item replace entity TarotVisual hotbar.0 from entity TarotVisual hotbar.1');command('item replace entity TarotVisual hotbar.1 with minecraft:air')
        folder=staged/'data/tarot/item_modifier/native_lab';folder.mkdir(parents=True,exist_ok=True)
        (folder/'note.json').write_text(json.dumps({'type' if version=='26.3' else 'function':'minecraft:set_components','components':{'minecraft:custom_name':{'text':'A keepsake from Rowan'},'minecraft:lore':[{'text':'Meet at the old café\nKeep "this" card safe.','color':'gold'}],'minecraft:repair_cost':3}}));command('reload');time.sleep(.5);command('item modify entity TarotVisual weapon.mainhand tarot:native_lab/note')
        original=value('data get entity TarotVisual SelectedItem')
        command('item replace entity TarotVisual weapon.offhand from entity TarotVisual weapon.mainhand');command('item replace entity TarotVisual weapon.mainhand from block 4 -60 0 container.0');command('item replace block 4 -60 0 container.0 with minecraft:air');action(3)
        wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'No items' in r,'annotated insertion');action(1);wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'Found 1 ' in r,'annotated redraw')
        command('item replace block 4 -60 0 container.0 from entity TarotVisual hotbar.0');command('item replace entity TarotVisual hotbar.0 from entity TarotVisual hotbar.1');command('item replace entity TarotVisual hotbar.1 with minecraft:air')
        if value('data get entity TarotVisual SelectedItem')!=original:raise AssertionError('Notes changed in saved item round trip')
        record('complete_saved_item_round_trip_preserves_notes')
        action(4);wait(f'execute if entity {display}',lambda r:'Test passed' in r,'table placement')
        wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'No items' in r,'placement consumes hand item');record('queued_face_down_placement')
        event('interaction');wait(f'scoreboard players get {display} tarot.face',lambda r:'has 1 ' in r,'flip callback')
        record('interaction_record_resolves_exact_stock_player_and_flips')
        before=value(f'data get entity {display} Rotation');command(f'execute as {display} at @s run function tarot:table/rotate');after=value(f'data get entity {display} Rotation')
        if before==after:raise AssertionError('Pose rotation did not execute')
        record('rotation_backend_changes_physical_pose')
        time.sleep(.3);event('attack');wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'Found 1 ' in r,'attack pickup callback')
        if value('data get entity TarotVisual SelectedItem')!=original:raise AssertionError('Table pickup changed the card')
        if 'Test passed' in command(f'execute if entity {display}'):raise AssertionError('Retrieved card remained in world')
        record('attack_record_returns_exact_annotated_item_once')
        action(4);wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'No items' in r,'fall fixture placement');command('setblock 0 -60 2 minecraft:air')
        wait(f'execute if entity {display}',lambda r:'Test passed' not in r,'unsupported card fall');command('tp TarotVisual 0.5 -60 2.5')
        wait('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0',lambda r:'Found 1 ' in r,'vanilla falling-item pickup')
        if value('data get entity TarotVisual SelectedItem')!=original:raise AssertionError('Falling changed the card')
        record('support_loss_and_vanilla_pickup_preserve_exact_notes')
        command('clear TarotVisual')
        for module,ink in [('rider','ink_sac'),('numbers','lapis_lazuli')]:
            command(f'advancement revoke TarotVisual only tarot:recipes/{module}_deck');command(f'recipe take TarotVisual tarot:{module}_deck')
            command('give TarotVisual minecraft:paper 8');command('give TarotVisual minecraft:'+ink)
            wait(f'execute as TarotVisual if entity @s[advancements={{tarot:recipes/{module}_deck=true}}]',lambda r:'Test passed' in r,'ingredient recipe discovery')
            response=command(f'recipe give TarotVisual tarot:{module}_deck')
            if 'already' not in response.lower() and 'No new' not in response:raise AssertionError('Recipe was not already learned: '+response)
            record('quiet_ingredient_recipe_discovery_'+module)
            command('clear TarotVisual')
        # A real redstone crafter exercises the engine's repair recipe on the
        # newest host without inventing unsupported protocol-click packets.
        for mode in ['ordinary_rods','cards','bands','card_and_band']:
            command('clear TarotVisual');command('setblock 9 -60 4 minecraft:air');command('setblock 8 -60 4 minecraft:air');command('setblock 8 -60 4 minecraft:crafter')
            if mode=='ordinary_rods':
                for slot in [0,1]:command(f'item replace block 8 -60 4 container.{slot} with minecraft:carrot_on_a_stick')
            else:
                command('execute as TarotVisual run function tarot:give/numbers')
                if mode in {'cards','card_and_band'}:action(1)
                if mode=='cards':action(1)
                sources={'cards':[1,2],'bands':[0,0],'card_and_band':[0,1]}[mode]
                for slot,source in enumerate(sources):command(f'item replace block 8 -60 4 container.{slot} from entity TarotVisual hotbar.{source}')
            before=command('data get block 8 -60 4 Items')
            command('execute store result score #craft_slots tarot.sys run data get block 8 -60 4 Items')
            if 'has 2 ' not in command('scoreboard players get #craft_slots tarot.sys'):raise AssertionError('Crafter fixture did not contain two actual input items')
            start=int(re.findall(r'\d+',command('time query gametime'))[-1]);command('setblock 9 -60 4 minecraft:redstone_block')
            wait('time query gametime',lambda r:int(re.findall(r'\d+',r)[-1])>=start+10,'redstone crafter ticks')
            after=command('data get block 8 -60 4 Items')
            if mode=='ordinary_rods':
                if not after.endswith('[]'):raise AssertionError('Ordinary tool repair control did not craft')
            elif after!=before:raise AssertionError('A card/band entered vanilla crafter repair: '+mode)
            record('native_crafter_repair_'+mode)
        command('setblock 9 -60 4 minecraft:air');command('setblock 8 -60 4 minecraft:air')
        result['passed']=True
    except Exception as e:
        result['passed']=False;result['error']=repr(e);result['failure_state']={}
        for query in ['scoreboard players get #valid tarot.sys','scoreboard players get #ready tarot.sys','scoreboard players get #different tarot.sys','scoreboard players get #committed tarot.sys','scoreboard players get TarotVisual tarot.pending','data get entity TarotVisual SelectedItem']:
            try:result['failure_state'][query]=command(query)
            except Exception as diagnostic:result['failure_state'][query]=repr(diagnostic)
        raise
    finally:
        if universal_lane is not None:lane.check_fixtures()
        result['commands']=lane.commands;write_json(lane.pack.parents[2]/'evidence'/(('universal-backend-' if universal_lane is not None else 'backend-')+version+'.json'),result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='26.3');main(p.parse_args().version)
