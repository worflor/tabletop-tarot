"""Real saved-world content expansion/omission/reinstallation; fixtures never ship."""
import argparse,copy,json,pathlib,shutil,time
from game_lab import ROOT,RUNTIME,VanillaLane,write_json,sha,deck_item,card_items,card_keys
from module_registry import BANDS

def fixture_source(folder):
    source=ROOT/'content/tarot';folder.mkdir(parents=True,exist_ok=True)
    for part in ['core','modules']:shutil.copytree(source/part,folder/part)
    shutil.copyfile(source/'source-lock.json',folder/'source-lock.json')
    module='future_fixture';destination=folder/'modules'/module;destination.mkdir()
    original=source/'modules/numbers';pack=json.loads((original/'pack.json').read_text());pack['cards']=copy.deepcopy(pack['cards'][:3]);pack['manifest']['name']='Isolated expansion fixture'
    for i,card in enumerate(pack['cards']):
        shutil.copyfile(original/(card['id']+'.png'),destination/f'card-{i}.png');card['id']=f'card-{i}';card['canonicalName']=f'Future fixture {i}';card['index']=999
    (destination/'pack.json').write_text(json.dumps(pack,indent=2)+'\n',encoding='utf-8')
    for name in ['deck.json','back.png']:shutil.copyfile(original/name,destination/name)
    path=folder/'core/modules.json';registry=json.loads(path.read_text());registry['modules'][module]={'default':True,'ingredient':'minecraft:amethyst_shard','icon':'card-0'};path.write_text(json.dumps(registry,indent=2)+'\n')
    path=folder/'core/item-identities.json';identities=json.loads(path.read_text());identities['models'].update({module+'/card-'+str(i):270001+i for i in range(3)});identities['models'].update({module+'/'+key:270990+i for i,key in enumerate(BANDS)});path.write_text(json.dumps(identities,indent=2)+'\n')
    return folder

def probe(version,bundle,source_root):
    from universal_lab import ZipLane
    lane=ZipLane(version);root=RUNTIME/'expansion-worlds'/f'{version}-{time.time_ns()}';root.mkdir(parents=True)
    baseline=root/'baseline.zip';shutil.copyfile(lane.archive,baseline);expanded=bundle/'Tabletop-Tarot-Universal.zip'
    lane.archive=baseline;lane.archive_sha256=sha(baseline);lane.server_dir=root/'server';lane.world_dir=lane.server_dir/lane.world_name
    production=ROOT/'content/tarot/build'/('java-'+version)/'datapack';added=source_root/'build'/('java-'+version)/'datapack'
    result={'minecraft':version,'scope':'Same-version saved-world pack expansion, content omission and restoration; actual protocol player and vanilla ItemStacks; synthetic third module stays in runtime cache','baseline_zip_sha256':sha(baseline),'expanded_zip_sha256':sha(expanded),'checks':[]}
    def record(name):result['checks'].append({'name':name,'passed':True});print(name,flush=True)
    def trigger(n):return lane.client_action('chat',text='/trigger tarot.action set '+str(n))['snapshot']
    def switch(archive,pack):
        lane.client_action('quit');lane.client_process.wait(timeout=10);lane.client_process=None;lane.stop();lane.process=None;lane.log=None
        lane.archive=archive;lane.archive_sha256=sha(archive);lane.pack=pack;lane.start();lane.start_player();lane.rcon('gamemode survival TarotLab');lane.rcon('deop TarotLab')
    def components_equal(path,expected):
        lane.rcon('data modify storage tarot_fuzz:expansion compare set from '+path)
        lane.rcon('execute store success score #expansion_diff tarot.sys run data modify storage tarot_fuzz:expansion compare set from storage tarot_fuzz:expansion '+expected)
        if 'has 0 ' not in lane.rcon('scoreboard players get #expansion_diff tarot.sys'):raise AssertionError('Expansion changed saved components: '+expected)
    try:
        lane.download_server();lane.start();lane.start_player();lane.rcon('clear TarotLab');lane.rcon('execute as TarotLab run function tarot:give/rider');lane.rcon('execute as TarotLab run function tarot:give/numbers')
        lane.client_action('hold',slot=0);lane.rcon('data modify storage tarot_fuzz:expansion rider set from entity TarotLab SelectedItem.components')
        lane.client_action('hold',slot=1);trigger(1);state=lane.wait_state(lambda s:bool(card_items(s)),'baseline card');card=card_items(state)[0][0]
        lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab hotbar.'+str(card['slot']-36));lane.rcon('item replace entity TarotLab hotbar.'+str(card['slot']-36)+' with minecraft:air')
        # Owner-written data travels in the native item, independently of the registry.
        from profiles import profile
        spec=profile(version);folder='item_modifiers' if spec['plural_paths'] else 'item_modifier';path=lane.world_dir/f'datapacks/tarot/data/tarot/{folder}/lab/expansion.json';path.parent.mkdir(parents=True,exist_ok=True)
        name={'text':'Kept through future editions'};note={'text':'Café "moon"\nKeep this one.'}
        path.write_text(json.dumps({'function':'minecraft:set_components','components':{'minecraft:custom_name':name if spec['text_objects'] else json.dumps(name),'minecraft:lore':[note if spec['text_objects'] else json.dumps(note)],'minecraft:repair_cost':7}},ensure_ascii=False),encoding='utf-8')
        lane.rcon('reload');lane.rcon('item modify entity TarotLab weapon.offhand tarot:lab/expansion');trigger(3);trigger(2)
        state=lane.client_action('snapshot');order=card_keys(state['held']);lane.rcon('data modify storage tarot_fuzz:expansion numbers set from entity TarotLab SelectedItem.components')
        switch(expanded,added)
        components_equal('entity TarotLab SelectedItem.components','numbers');lane.client_action('hold',slot=0);components_equal('entity TarotLab SelectedItem.components','rider')
        record('adding_module_keeps_existing_bands_order_and_all_annotations')
        lane.rcon('execute as TarotLab run function tarot:give/future_fixture');state=lane.wait_state(lambda s:deck_item(s,'future_fixture') is not None,'future module grant')
        future=deck_item(state,'future_fixture');lane.client_action('hold',slot=future['slot']-36);trigger(1)
        state=lane.wait_state(lambda s:bool(card_items(s,'future_fixture')),'future card draw');card=card_items(state,'future_fixture')[0][0]
        if len(card_keys(deck_item(state,'future_fixture')))!=2:raise AssertionError('Future factory deck is incomplete')
        lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab hotbar.'+str(card['slot']-36));lane.rcon('item replace entity TarotLab hotbar.'+str(card['slot']-36)+' with minecraft:air')
        lane.client_action('hold',slot=1);trigger(3);state=lane.client_action('snapshot')
        if card_keys(state['held'])!=['future_fixture/card-0']+order:raise AssertionError('Future card could not mix with an existing annotated band')
        lane.rcon('data modify storage tarot_fuzz:expansion mixed set from entity TarotLab SelectedItem.components')
        record('new_cards_mix_into_existing_saved_bands_without_reprinting')
        switch(baseline,production)
        for action in [1,2,3]:
            trigger(action);components_equal('entity TarotLab SelectedItem.components','mixed')
        record('omitted_module_refuses_mixed_band_without_consuming_or_rewriting_it')
        switch(expanded,added);components_equal('entity TarotLab SelectedItem.components','mixed');trigger(1)
        state=lane.wait_state(lambda s:bool(card_items(s,'future_fixture')),'restored future card draw')
        if card_items(state,'future_fixture')[0][1]['key']!='future_fixture/card-0' or card_keys(state['held'])!=order:raise AssertionError('Restored pack lost physical ordering')
        components_equal('entity TarotLab SelectedItem.components','numbers')
        record('reinstalling_module_restores_the_same_cards_and_original_saved_band')
        lane.rcon('tp TarotLab 0.5 -60 0.5');lane.rcon('setblock 1 -60 0 minecraft:crafting_table')
        lane.rcon('give TarotLab minecraft:paper 8');lane.rcon('give TarotLab minecraft:amethyst_shard 1')
        state=lane.client_action('craft_deck',timeout=45,x=1,y=-60,z=0,ingredient='amethyst_shard')
        from game_lab import native_items,tarot_data
        if not any((tarot_data(item) or {}).get('module')=='future_fixture' and len(native_items(item))==3 for item in state['items']):raise AssertionError('New module recipe failed to craft its complete deck in Survival')
        if card_keys(deck_item(state,'numbers'))!=order or len(card_keys(deck_item(state,'rider')))!=78:raise AssertionError('Crafting an added module changed an existing band')
        record('added_module_uses_a_real_survival_recipe_and_keeps_existing_decks')
        lane.check_fixtures();result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines;write_json(ROOT/f'content/tarot/evidence/expansion-{version}.json',result)

def main(versions):
    folder=RUNTIME/'expansion-builds'/str(time.time_ns());source=fixture_source(folder/'source')
    import build,universal
    old_build,old_universal=build.ROOT,universal.ROOT
    try:
        build.ROOT=source;universal.ROOT=source;bundle=universal.compile_pack()
        # Every original legacy allocation remains byte-for-byte stable.
        before=json.loads((ROOT/'content/tarot/core/item-identities.json').read_text())['models'];after=json.loads((source/'core/item-identities.json').read_text())['models']
        if any(after[key]!=value for key,value in before.items()):raise AssertionError('Expansion reassigned an existing model')
        for version in versions:probe(version,bundle,source)
    finally:build.ROOT=old_build;universal.ROOT=old_universal

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--versions',nargs='+',default=['1.20.6','1.21.11']);p.add_argument('--source',type=pathlib.Path);a=p.parse_args()
    if a.source:
        for version in a.versions:probe(version,a.source/'build/universal',a.source)
    else:main(a.versions)
