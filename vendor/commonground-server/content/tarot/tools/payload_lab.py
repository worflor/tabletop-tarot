"""Malformed saved-item and foreign-schema probes on an actual vanilla server."""
import argparse,copy,json,random
from game_lab import VanillaLane,write_json,sha,card_items,tarot_data,native_items
from runtime import printed_item
from profiles import PROFILES

def fuzz(lane,seed,count):
    from profiles import profile
    rng=random.Random(seed);spec=profile(lane.version)
    card=next(c for c in json.loads((lane.pack.parent/'catalogue.json').read_text())['cards'] if c['key']=='numbers/number-1')
    base={'key':card['key'],'item_schema':lane.version,'item':printed_item(card,lane.version)}
    offhand=spec['offhand_components'].removesuffix('.components');checks=[]
    lane.rcon('clear TarotLab');lane.rcon('execute as TarotLab run function tarot:give/numbers');lane.client_action('hold',slot=0);lane.client_action('chat',text='/trigger tarot.action set 1')
    state=lane.wait_state(lambda s:bool(card_items(s)),'fuzz offhand positive fixture');slot=card_items(state)[0][0]['slot']
    lane.rcon('setblock 12 -60 0 minecraft:chest');lane.rcon('item replace block 12 -60 0 container.1 from entity TarotLab hotbar.'+str(slot-36))
    for index in range(count):
        row=copy.deepcopy(base);kind=index%12
        if kind==0:row['item_schema']=rng.choice(['missing-host',-1,False,{'x':1}])
        elif kind==1:row['item']['count']=rng.choice([0,-1,2,127,1.5,'one'])
        elif kind==2:row['key']='uninstalled/card-'+str(index)
        elif kind==3:row['item']['id']=rng.choice(['minecraft:diamond','minecraft:stone','minecraft:air'])
        elif kind==4:row['item']['components']['minecraft:custom_data']['tarot']['module']='uninstalled'
        elif kind==5:row['item']['components']['minecraft:custom_data']['tarot']['key']='numbers/missing-'+str(index)
        elif kind==6:row['item']['components']['minecraft:fuzz_unknown_component']={'keep':index}
        elif kind==7:row['item']['components']['minecraft:max_stack_size']=rng.choice([0,-1,1000])
        elif kind==8:row['item']['components']['minecraft:repair_cost']={'unexpected':[{'number':index},{'deep':[False]}]}
        elif kind==9:row['item']['components']['minecraft:custom_name']={'text':{'not_text':[index]}}
        elif kind==10:del row['item_schema']
        else:row['item']['components']['minecraft:custom_data']['tarot']['kind']='deck'
        lane.rcon('clear TarotLab');lane.rcon('scoreboard players set TarotLab tarot.cool 0')
        custom={'tarot':{'kind':'deck','module':'numbers','cards':[row]},'keep_note':'seed-'+str(seed)+'-case-'+str(index)}
        response=lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data='+json.dumps(custom,separators=(',',':'))+']')
        if 'Replaced' not in response:raise AssertionError('Malformed wrapper fixture was not installed: '+response)
        lane.client_action('hold',slot=0);lane.rcon('item replace entity TarotLab weapon.offhand from block 12 -60 0 container.1')
        lane.rcon('data modify storage tarot_fuzz:negative main set from entity TarotLab SelectedItem')
        lane.rcon('data modify storage tarot_fuzz:negative offhand set from entity TarotLab '+offhand)
        for action in [1,2,3]:
            lane.client_action('chat',text='/trigger tarot.action set '+str(action))
            for label,path in [('main','SelectedItem'),('offhand',offhand)]:
                lane.rcon('data modify storage tarot_fuzz:negative compare set from storage tarot_fuzz:negative '+label)
                lane.rcon('execute store success score #fuzz_changed tarot.sys run data modify storage tarot_fuzz:negative compare set from entity TarotLab '+path)
                if 'has 0 ' not in lane.rcon('scoreboard players get #fuzz_changed tarot.sys'):raise AssertionError(f'Malformed fuzz case {index}, mutation {kind}, action {action} changed {label}')
            if 'Test passed' in lane.rcon('execute if entity @e[tag=tarot.transfer]'):raise AssertionError('Malformed payload leaked a staging entity')
        checks.append({'name':'malformed_fuzz_'+str(index),'passed':True,'mutation':kind,'actions':3})
        if index%20==0:print(json.dumps({'seed':seed,'malformed_cases':index+1}),flush=True)
    return checks

def run(lane):
    card=next(c for c in json.loads((lane.pack.parent/'catalogue.json').read_text())['cards'] if c['key']=='numbers/number-1')
    base={'key':card['key'],'item_schema':lane.version,'item':printed_item(card,lane.version)}
    cases={}
    for name,key,value in [('invalid_stack_limit','minecraft:max_stack_size',0),('invalid_text_component','minecraft:custom_name',{'text':{'invalid':[1,2]}}),('unknown_component','minecraft:physical_cards_unknown_component',True)]:
        row=copy.deepcopy(base);row['item']['components'][key]=value;cases[name]=row
    row=copy.deepcopy(base);row['item']['components']['minecraft:custom_data']['tarot']['module']='rider';cases['wrong_module']=row
    row=copy.deepcopy(base);del row['item']['components']['minecraft:custom_data']['tarot']['module'];cases['missing_module']=row
    row=copy.deepcopy(base);row['item_schema']='1.20.6' if lane.version!='1.20.6' else '1.21.11';row['item']=printed_item(card,row['item_schema']);cases['foreign_schema']=row
    row=copy.deepcopy(base);del row['item_schema'];cases['unstamped_opaque_payload']=row
    checks=[]
    def fixture(row,collision=False):
        lane.rcon('clear TarotLab');lane.rcon('scoreboard players set TarotLab tarot.cool 0')
        custom={'tarot':{'kind':'deck','module':'numbers','cards':[row]}}
        extra=',minecraft:charged_projectiles=[{id:"minecraft:stone",count:1}]' if collision else ''
        lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data='+json.dumps(custom,separators=(',',':'))+extra+'] 1');lane.client_action('hold',slot=0)
        return lane.wait_state(lambda s:tarot_data(s.get('held'))==custom['tarot'] and len(native_items(s.get('held')))==(1 if collision else 0),'exact opaque payload fixture')
    for name,row in cases.items():
        before=fixture(row);lane.rcon('scoreboard players set TarotLab tarot.pending 0')
        lane.client_action('chat',text='/trigger tarot.action set 1');after=lane.client_action('snapshot')
        accepted=lane.rcon('scoreboard players get TarotLab tarot.pending')
        if 'has 1 ' not in accepted:raise AssertionError('Probe input was not processed')
        if card_items(after) or tarot_data(after['held'])!=tarot_data(before['held']):raise AssertionError('Saved payload was consumed or rewritten: '+name)
        checks.append({'name':'opaque_payload_kept_'+name,'passed':True})
    before=fixture(base,True)
    for action in [1,2,3]:
        lane.client_action('chat',text='/trigger tarot.action set '+str(action));after=lane.client_action('snapshot')
        if after['held']['components']!=before['held']['components'] or card_items(after):raise AssertionError('Legacy promotion overwrote existing native storage')
    checks.append({'name':'legacy_native_component_collision_preserved_exactly','passed':True})
    fixture(base);lane.client_action('chat',text='/trigger tarot.action set 1')
    lane.wait_state(lambda s:len(card_items(s))==1,'valid opaque payload positive control')
    checks.append({'name':'valid_saved_item_is_delivered','passed':True})
    return checks

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',choices=PROFILES,default='1.21.11');p.add_argument('--fuzz-cases',type=int,default=0);p.add_argument('--seed',type=int,default=65537);a=p.parse_args();lane=VanillaLane(a.version);result={'minecraft':a.version,'scope':'actual ItemStack codec rejection and version/module fail-closed behavior','checks':[],'fuzz_seed':a.seed}
    lane.server_dir=lane.server_dir.parent/f'payload-server-{a.version}-{__import__("time").time_ns()}';lane.world_dir=lane.server_dir/lane.world_name
    try:
        lane.download_server();lane.start();lane.start_player();result['datapack_sha256']={f.relative_to(lane.pack).as_posix():sha(f) for f in lane.pack.rglob('*') if f.is_file()};result['checks']=run(lane)
        if a.fuzz_cases:result['checks']+=fuzz(lane,a.seed,a.fuzz_cases)
        result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines
        write_json(lane.pack.parents[2]/'evidence'/('payload-'+a.version+('-fuzz-'+str(a.seed) if a.fuzz_cases else '')+'.json'),result)
