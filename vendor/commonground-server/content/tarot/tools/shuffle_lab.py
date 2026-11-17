"""Final integer-permutation optimization: real engine regressions across adapters."""
import argparse,json
from game_lab import VanillaLane,write_json,sha,card_items,card_keys,deck_item,tarot_data,native_items
from deck_scenarios import run_extra
from customization_scenarios import run_customizations,prepare_customizations
from runtime import printed_item
from profiles import PROFILES

def run(lane,baseline=True):
    if baseline:checks=run_extra(lane)+run_customizations(lane)
    else:prepare_customizations(lane);checks=[]
    def snapshot():return lane.client_action('snapshot')
    def trigger(n):return lane.client_action('chat',text=f'/trigger tarot.action set {n}')['snapshot']
    def rows(state):return native_items(deck_item(state,'numbers'))
    def canonical(value):
        if isinstance(value,list):return [canonical(v) for v in value]
        if isinstance(value,dict):
            return {k:canonical(sorted(v,key=lambda c:str(c['type']))) if k=='components' and isinstance(v,list) else canonical(v) for k,v in value.items()}
        return value
    def bag(values):return sorted(json.dumps(canonical(row),sort_keys=True,ensure_ascii=False) for row in values)
    lane.rcon('clear TarotLab');lane.player_function('tarot:give/numbers');lane.client_action('hold',slot=0);trigger(1)
    state=lane.wait_state(lambda s:bool(card_items(s,'numbers')),'marked shuffle fixture');slot=card_items(state,'numbers')[0][0]['slot'];source=f'hotbar.{slot-36}' if slot>=36 else f'inventory.{slot-9}'
    lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab '+source);lane.rcon('item replace entity TarotLab '+source+' with minecraft:air')
    lane.rcon('item modify entity TarotLab weapon.offhand tarot:lab/annotated');lane.rcon('item modify entity TarotLab weapon.offhand tarot:lab/custom_data');trigger(3)
    before=rows(lane.wait_state(lambda s:not s.get('offhand'),'marked insertion'))
    for _ in range(5):
        state=trigger(2);after=rows(state)
        if after!=before:break
    else:raise AssertionError('Final shuffle never changed order')
    if bag(after)!=bag(before):raise AssertionError('Shuffle changed complete card instances')
    top=tarot_data(after[0])['key'];trigger(1);state=lane.wait_state(lambda s:len(card_items(s,'numbers'))==1,'shuffled top draw')
    if card_items(state,'numbers')[0][1]['key']!=top:raise AssertionError('Shuffled stack did not draw its new top')
    checks.append({'name':'indexed_shuffle_preserves_annotated_instances_and_top_order','passed':True})
    catalogue=json.loads((lane.pack.parent/'catalogue.json').read_text());chosen=[next(c for c in catalogue['cards'] if c['key']==key) for key in ['rider/major-0','numbers/number-1','rider/major-0']]
    mixed=[printed_item(c,lane.version) for c in chosen];mixed[-1]['components']['minecraft:custom_data']['copy_note']='A separate second printing'
    lane.rcon('clear TarotLab');lane.rcon('scoreboard players set TarotLab tarot.cool 0')
    from profiles import profile
    folder='item_modifiers' if profile(lane.version)['plural_paths'] else 'item_modifier';fixture=lane.world_dir/f'datapacks/tarot/data/tarot/{folder}/lab/native_mixed.json'
    fixture.write_text(json.dumps({'type' if lane.version=='26.3' else 'function':'minecraft:set_components','components':{'minecraft:custom_data':{'tarot':{'kind':'deck','module':'numbers','storage':'native-v1'}},'minecraft:charged_projectiles':mixed}}))
    lane.rcon('reload');lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick');lane.rcon('item modify entity TarotLab hotbar.0 tarot:lab/native_mixed');lane.client_action('hold',slot=0)
    before=rows(lane.wait_state(lambda s:len(card_keys(deck_item(s,'numbers')))==3,'mixed repeat fixture'))
    for _ in range(10):
        state=trigger(2);after=rows(state)
        if after!=before:break
    else:raise AssertionError('Mixed shuffle did not permute')
    if bag(after)!=bag(before):raise AssertionError('Mixed/repeated instances changed')
    expected=[tarot_data(row)['key'] for row in after]
    for i in range(3):
        trigger(1);state=lane.wait_state(lambda s:len(card_items(s))==i+1,'mixed ordered draw')
        if sorted(data['key'] for _,data in card_items(state))!=sorted(expected[:i+1]):raise AssertionError('Mixed order or repeated card lost')
    checks.append({'name':'indexed_shuffle_preserves_mixed_and_repeated_instances','passed':True})
    return checks

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',choices=PROFILES,required=True);a=p.parse_args();lane=VanillaLane(a.version);result={'minecraft':a.version,'scope':'focused final shuffle optimization; full baseline suite bound separately','checks':[]}
    try:
        lane.download_server();lane.start();lane.start_player();result['datapack_sha256']={f.relative_to(lane.pack).as_posix():sha(f) for f in lane.pack.rglob('*') if f.is_file()};result['checks']=run(lane);result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines
        write_json(lane.pack.parents[2]/'evidence'/('shuffle-'+a.version+'.json'),result)
