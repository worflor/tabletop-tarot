"""Use real decks before and after a forward world upgrade on a disposable copy."""
import argparse,json,shutil,time
from game_lab import VanillaLane,RUNTIME,ROOT,card_keys,card_items,deck_item,tarot_data,write_json,sha
from profiles import profile

def main(source,target):
    run=RUNTIME/'deck-upgrades'/str(time.time_ns());old=VanillaLane(source);new=VanillaLane(target)
    for lane,label in [(old,'source'),(new,'target')]:lane.server_dir=run/label;lane.world_dir=lane.server_dir/lane.world_name
    result={'source':source,'target':target,'scope':'Actual native-stack gameplay, chest storage, saved world copy, official vanilla DataFixer and resumed gameplay; no external NBT edits','checks':[]}
    name='A keepsake from Rowan — café "moon"';note='Line one\nKeep this card safe.'
    def record(label):result['checks'].append({'name':label,'passed':True})
    def trigger(lane,action):return lane.client_action('chat',text='/trigger tarot.action set '+str(action))['snapshot']
    try:
        result['source_datapack_sha256']={p.relative_to(old.pack).as_posix():sha(p) for p in old.pack.rglob('*') if p.is_file()}
        result['target_datapack_sha256']={p.relative_to(new.pack).as_posix():sha(p) for p in new.pack.rglob('*') if p.is_file()}
        old.download_server();old.start();old.start_player();old.rcon('clear TarotLab');old.player_function('tarot:give/numbers');old.client_action('hold',slot=0);trigger(old,1)
        state=old.wait_state(lambda s:bool(card_items(s,'numbers')),'source draw');card=card_items(state,'numbers')[0][0];slot='hotbar.'+str(card['slot']-36)
        old.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab '+slot);old.rcon('item replace entity TarotLab '+slot+' with minecraft:air')
        folder='item_modifiers' if profile(source)['plural_paths'] else 'item_modifier';fixture=old.world_dir/f'datapacks/tarot/data/tarot/{folder}/lab/upgrade_note.json';fixture.parent.mkdir(parents=True,exist_ok=True)
        text={'text':name,'color':'gold'};lore={'text':note,'italic':False}
        components={'minecraft:custom_name':text if profile(source)['text_objects'] else json.dumps(text,ensure_ascii=False),'minecraft:lore':[lore if profile(source)['text_objects'] else json.dumps(lore)],'minecraft:repair_cost':7}
        fixture.write_text(json.dumps({'function':'minecraft:set_components','components':components},ensure_ascii=False),encoding='utf-8');old.rcon('reload');old.rcon('item modify entity TarotLab weapon.offhand tarot:lab/upgrade_note');trigger(old,3)
        old.wait_state(lambda s:not s.get('offhand'),'source annotated insertion');trigger(old,2)
        state=old.client_action('snapshot');order=card_keys(deck_item(state,'numbers'))
        if len(order)!=12 or len(set(order))!=12:raise AssertionError('Source membership')
        old.rcon('setblock 3 -60 0 minecraft:chest');old.rcon('item replace block 3 -60 0 container.0 from entity TarotLab hotbar.0');old.rcon('clear TarotLab')
        # Unhandled factory Rider stack, and loose card, travel beside the handled Numbers stack.
        old.player_function('tarot:give/rider');old.client_action('hold',slot=0);old.rcon('item replace block 3 -60 0 container.1 from entity TarotLab hotbar.0');trigger(old,1)
        state=old.wait_state(lambda s:bool(card_items(s,'rider')),'source loose card');item=card_items(state,'rider')[0][0]
        old.rcon('item replace block 3 -60 0 container.2 from entity TarotLab hotbar.'+str(item['slot']-36));old.rcon('clear TarotLab');old.rcon('save-all flush');record('source_real_draw_annotation_return_shuffle_and_chest_storage');old.stop()
        shutil.copytree(old.world_dir,new.world_dir);new.download_server();new.start();new.start_player();new.rcon('clear TarotLab')
        new.rcon('item replace entity TarotLab hotbar.0 from block 3 -60 0 container.0');new.rcon('item replace block 3 -60 0 container.0 with minecraft:air');new.client_action('hold',slot=0)
        state=new.wait_state(lambda s:deck_item(s,'numbers') is not None,'upgraded Numbers stack')
        if card_keys(deck_item(state,'numbers'))!=order or tarot_data(deck_item(state,'numbers')).get('storage')!='native-v1':raise AssertionError('Saved deck order/schema changed')
        record('upgraded_stack_retains_exact_shuffled_order_without_version_stamp')
        if 'Test passed' not in new.rcon('execute if data entity TarotLab SelectedItem.components."!minecraft:max_damage"'):raise AssertionError('Forward upgrade lost the band repair protection')
        found=False
        for index,key in enumerate(order):
            trigger(new,1);state=new.wait_state(lambda s:len(card_items(s,'numbers'))==index+1,'upgraded top draw')
            if sorted(d['key'] for _,d in card_items(state,'numbers'))!=sorted(order[:index+1]):raise AssertionError('Upgraded draw membership/order changed')
            if key=='numbers/number-1':
                # Check the canonical target-side actual item through engine predicates, not a lossy observer conversion.
                chosen=next(item for item,data in card_items(state,'numbers') if data['key']==key);source_slot=f'hotbar.{chosen["slot"]-36}' if chosen['slot']>=36 else f'inventory.{chosen["slot"]-9}'
                new.rcon('item replace block 3 -60 0 container.3 from entity TarotLab '+source_slot)
                new.rcon('data modify storage tarot:upgrade actual set from block 3 -60 0 Items[{Slot:3b}]')
                expected={'components':{'minecraft:custom_name':{'text':name,'color':'gold'},'minecraft:lore':[{'text':note}],'minecraft:repair_cost':7}}
                if 'Test passed' not in new.rcon('execute if data storage tarot:upgrade actual'+json.dumps(expected,separators=(',',':'))):raise AssertionError('Upgraded real annotation changed')
                new.rcon('item replace block 3 -60 0 container.3 with minecraft:air');found=True
        if not found:raise AssertionError('Marked card lost')
        record('all_twelve_upgraded_items_drawn_and_marked_card_keeps_name_notes_and_repair_cost')
        new.rcon('clear TarotLab');new.rcon('item replace entity TarotLab hotbar.0 from block 3 -60 0 container.1');new.rcon('item replace block 3 -60 0 container.1 with minecraft:air');new.client_action('hold',slot=0)
        state=new.wait_state(lambda s:deck_item(s,'rider') is not None,'untouched upgraded factory deck')
        if len(card_keys(deck_item(state,'rider')))!=78:raise AssertionError('Untouched factory contents changed')
        trigger(new,1);new.wait_state(lambda s:len(card_keys(deck_item(s,'rider')))==77 and len(card_items(s,'rider'))==1,'upgraded untouched factory draw')
        record('untouched_old_factory_rider_deck_remains_playable_with_all_78_cards')
        new.rcon('item replace entity TarotLab hotbar.2 from block 3 -60 0 container.2');new.rcon('item replace block 3 -60 0 container.2 with minecraft:air')
        state=new.wait_state(lambda s:len(card_items(s,'rider'))==2,'upgraded loose card')
        if any(data['key']!='rider/major-0' for _,data in card_items(state,'rider')):raise AssertionError('Loose card identity changed')
        record('loose_old_card_keeps_identity_beside_upgraded_stack')
        result['passed']=True
    except Exception as error:result['passed']=False;result['error']=repr(error);raise
    finally:
        old.stop();new.stop();result['commands']=old.commands+new.commands;result['protocol_lines']=old.client_lines+new.client_lines;result['processes']=old.starts+new.starts
        write_json(ROOT/f'content/tarot/evidence/deck-upgrade-{source}-to-{target}.json',result)
    print(json.dumps({'source':source,'target':target,'passed':True,'checks':len(result['checks'])}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='1.20.6');p.add_argument('--target',default='1.21.11');a=p.parse_args();main(a.source,a.target)
