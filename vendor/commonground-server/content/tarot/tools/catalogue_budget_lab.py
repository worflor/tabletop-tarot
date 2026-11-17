"""Exercise maximum catalogue size and simultaneous legacy promotion in vanilla."""
import argparse,copy,json,pathlib,shutil,time
from game_lab import ROOT,RUNTIME,VanillaLane,write_json,sha,deck_item,card_items,card_keys
from expansion_lab import fixture_source
from module_registry import BANDS,load

def make_source(root):
    fixture_source(root);registry=json.loads((root/'core/modules.json').read_text());ids=json.loads((root/'core/item-identities.json').read_text())
    source=ROOT/'content/tarot/modules/numbers';template=json.loads((source/'pack.json').read_text());original=template['cards'][0]
    ingredients=['amethyst_shard','emerald','diamond','gold_ingot','iron_ingot','copper_ingot','quartz','redstone']
    for group,count in enumerate([128]*7+[38]):
        module='future_fixture' if group==0 else 'budget_'+str(group);folder=root/'modules'/module;folder.mkdir(exist_ok=True)
        pack=copy.deepcopy(template);pack['manifest']['name']='Budget fixture '+str(group);pack['cards']=[]
        base=270000 if group==0 else 300000+group*10000
        for index in range(count):
            key='card-'+str(index);card={**original,'id':key,'canonicalName':f'Budget {group} / {index}'};pack['cards'].append(card)
            shutil.copyfile(source/(original['id']+'.png'),folder/(key+'.png'));ids['models'][module+'/'+key]=base+index+1
        for name in ['deck.json','back.png']:shutil.copyfile(source/name,folder/name)
        (folder/'pack.json').write_text(json.dumps(pack,indent=2)+'\n')
        registry['modules'][module]={'default':True,'ingredient':'minecraft:'+ingredients[group],'icon':'card-0'}
        ids['models'].update({module+'/'+key:base+990+index for index,key in enumerate(BANDS)})
    (root/'core/modules.json').write_text(json.dumps(registry,indent=2)+'\n');(root/'core/item-identities.json').write_text(json.dumps(ids,indent=2)+'\n')
    if sum(s['count'] for s in load(root)[0].values())!=1024:raise AssertionError('Wrong stress catalogue size')

def probe(version,source,output):
    lane=VanillaLane(version);run=RUNTIME/'catalogue-budget-worlds'/f'{version}-{time.time_ns()}';lane.server_dir=run/'server';lane.world_dir=lane.server_dir/lane.world_name;lane.pack=output/'datapack'
    peer=VanillaLane(version);peer.game_port,peer.rcon_port,peer.password=lane.game_port,lane.rcon_port,lane.password
    result={'minecraft':version,'scope':'1024 registered cards; two real players simultaneously promote and draw from 128-card key-only legacy bands under vanilla 65536 command budget','datapack_sha256':{p.relative_to(lane.pack).as_posix():sha(p) for p in lane.pack.rglob('*') if p.is_file()},'checks':[]}
    try:
        lane.download_server();lane.start();lane.start_player();peer.start_player('TarotPeer')
        from profiles import profile
        functions='functions' if profile(version)['plural_paths'] else 'function'
        fixture=lane.world_dir/f'datapacks/tarot/data/tarot/{functions}/lab/budget/give.mcfunction';fixture.parent.mkdir(parents=True,exist_ok=True)
        fixture.write_text('item replace entity @s hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data='+json.dumps({'tarot':{'kind':'deck','module':'budget_7','cards':[{'key':'budget_7/card-37'}]*128}},separators=(',',':'))+']\n',encoding='utf-8')
        lane.rcon('reload')
        for name in ['TarotLab','TarotPeer']:
            lane.rcon('clear '+name);lane.rcon('execute as '+name+' run function tarot:lab/budget/give')
        lane.rcon('scoreboard players set @a tarot.cool 0');lane.rcon('scoreboard players set @a tarot.action 1')
        for client in [lane,peer]:
            state=client.wait_state(lambda s:len(card_keys(deck_item(s,'budget_7')))==127 and len(card_items(s,'budget_7'))==1,'full-catalogue legacy promotion',timeout=20)
            if set(card_keys(deck_item(state,'budget_7')))!={'budget_7/card-37'}:raise AssertionError('Promotion changed an identity')
        if 'Test passed' in lane.rcon('execute if entity @e[tag=tarot.transfer]'):raise AssertionError('Stress migration leaked a staging entity')
        result['checks'].append({'name':'two_128_card_legacy_promotions_finish_at_maximum_catalogue','passed':True,'catalogue':1024,'cards_conserved':256})
        result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        peer.stop();lane.stop();result['commands']=lane.commands+peer.commands;result['protocol_lines']=lane.client_lines+peer.client_lines;write_json(ROOT/f'content/tarot/evidence/catalogue-budget-{version}.json',result)

def main(versions):
    source=RUNTIME/'catalogue-budget-builds'/str(time.time_ns())/'source';source.mkdir(parents=True);make_source(source)
    import build
    original=build.ROOT
    try:
        build.ROOT=source
        for version in versions:probe(version,source,build.build(version))
    finally:build.ROOT=original

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--versions',nargs='+',default=['1.20.6','26.1.2']);p.add_argument('--source',type=pathlib.Path);a=p.parse_args()
    if a.source:
        import build
        old=build.ROOT
        try:
            build.ROOT=a.source
            for version in a.versions:
                output=a.source/'build'/('java-'+version)
                if not output.exists():output=build.build(version)
                probe(version,a.source,output)
        finally:build.ROOT=old
    else:main(a.versions)
