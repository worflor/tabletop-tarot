"""Engine regressions for delayed intent, held-item changes and real surface hits."""
import argparse,time,json
from profiles import profile
from game_lab import ROOT,RUNTIME,VanillaLane,write_json,sha,deck_item,card_items,card_keys

def run(lane):
    checks=[]
    spec=profile(lane.version);functions='functions' if spec['plural_paths'] else 'function'
    defer=lane.world_dir/f'datapacks/tarot/data/tarot/{functions}/lab/defer.mcfunction';defer.parent.mkdir(parents=True,exist_ok=True)
    defer.write_text('scoreboard players set #heavy_left tarot.sys 0\nfunction tarot:queue/player_serve\n',encoding='utf-8')
    folder='item_modifiers' if spec['plural_paths'] else 'item_modifier'
    modifier=lane.world_dir/f'datapacks/tarot/data/tarot/{folder}/lab/refinement_note.json';modifier.parent.mkdir(parents=True,exist_ok=True)
    name={'text':'A different keepsake'}
    modifier.write_text(json.dumps({'type' if lane.version=='26.3' else 'function':'minecraft:set_components','components':{'minecraft:custom_name':name if spec['text_objects'] else json.dumps(name)}}),encoding='utf-8')
    lane.rcon('reload');time.sleep(.5)
    def record(name,**details):checks.append({'name':name,'passed':True,**details});print(name,flush=True)
    def wait(command,predicate,label):
        until=time.monotonic()+12
        while True:
            value=lane.rcon(command)
            if predicate(value):return value
            if time.monotonic()>until:raise TimeoutError(label+': '+value)
            time.sleep(.05)
    def fresh():
        lane.client_action('sneak',enabled=False);lane.rcon('clear TarotLab')
        lane.rcon('kill @e[type=minecraft:item_display,tag=tarot.placed]');lane.rcon('kill @e[type=minecraft:interaction,tag=tarot.touch]')
        lane.rcon('fill -3 -60 -2 4 -56 8 minecraft:air');lane.rcon('tp TarotLab 0.5 -60 0.5 0 20')
        lane.client_action('hold',slot=0);lane.rcon('scoreboard players set TarotLab tarot.cool 0');lane.player_function('tarot:give/numbers')
        return lane.wait_state(lambda s:deck_item(s,'numbers') is not None,'new numbers band')
    def capture(action):
        lane.rcon('scoreboard players set TarotLab tarot.cool 200')
        lane.rcon('scoreboard players set TarotLab tarot.action '+str(action))
        lane.rcon('execute as TarotLab at @s run function tarot:input/trigger')
        lane.rcon('execute as TarotLab at @s run function tarot:lab/defer')
        if 'Test passed' not in lane.rcon('execute if entity @a[name=TarotLab,tag=tarot.waiting]'):raise AssertionError('Request was not deferred')
    def served():
        lane.rcon('scoreboard players set TarotLab tarot.cool 0')
        wait('execute if entity @a[name=TarotLab,tag=tarot.waiting]',lambda r:'Test passed' not in r,'pending request served')
        return lane.client_action('snapshot')
    fresh();lane.client_action('sneak',enabled=True)
    lane.rcon('scoreboard players set TarotLab tarot.cool 200');lane.rcon('execute as TarotLab at @s run function tarot:input/use')
    lane.rcon('execute as TarotLab at @s run function tarot:lab/defer')
    if 'has 2 ' not in lane.rcon('scoreboard players get TarotLab tarot.pending'):raise AssertionError('Shift intent was not captured')
    lane.client_action('sneak',enabled=False);state=served()
    if len(card_keys(deck_item(state,'numbers')))!=12 or card_items(state):raise AssertionError('Released Shift became a draw')
    record('deferred_shift_release_keeps_shuffle_intent')
    fresh();lane.player_function('tarot:give/rider');lane.wait_state(lambda s:deck_item(s,'rider') is not None,'second band')
    capture(1);lane.client_action('hold',slot=1);state=served()
    if len(card_keys(deck_item(state,'numbers')))!=12 or len(card_keys(deck_item(state,'rider')))!=78 or card_items(state):raise AssertionError('Queued draw followed a hotbar switch')
    record('queued_draw_cancels_after_switching_to_another_band')
    fresh();capture(1)
    # Same hotbar slot, different complete item: slot identity alone is unsafe.
    lane.rcon('item replace entity TarotLab hotbar.1 from entity TarotLab hotbar.0')
    lane.rcon('clear TarotLab minecraft:carrot_on_a_stick 1');lane.player_function('tarot:give/rider')
    state=served()
    if card_items(state) or len(card_keys(deck_item(state,'rider')))!=78:raise AssertionError('Queued draw accepted a replacement item in the same slot')
    record('queued_draw_cancels_after_same_slot_item_replacement')
    fresh();lane.client_action('chat',text='/trigger tarot.action set 1')
    state=lane.wait_state(lambda s:bool(card_items(s)),'offhand return card');card=card_items(state)[0][0]
    slot=f'hotbar.{card["slot"]-36}'
    lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab '+slot);lane.rcon('item replace entity TarotLab '+slot+' with minecraft:air')
    capture(3);lane.rcon('item modify entity TarotLab weapon.offhand tarot:lab/refinement_note');state=served()
    if not state.get('offhand') or len(card_keys(deck_item(state,'numbers')))!=11:raise AssertionError('Deferred return consumed a changed offhand card')
    record('queued_return_cancels_after_offhand_card_changes')
    lane.rcon('data modify storage tarot:inputs pending.p2147483646 set value {main:{kept_note:"disconnected request"}}')
    lane.player_function('tarot:input/prune')
    if 'Test passed' in lane.rcon('execute if data storage tarot:inputs pending.p2147483646'):raise AssertionError('Disconnected snapshot was retained')
    record('disconnected_input_snapshots_are_pruned')
    for offhand in ['minecraft:torch','minecraft:apple','minecraft:shield']:
        fresh();lane.rcon('item replace entity TarotLab weapon.offhand with '+offhand)
        state=lane.client_action('raw_use')
        if card_items(state) or len(card_keys(deck_item(state,'numbers')))!=12:raise AssertionError('Physical use also acted with an ordinary occupied offhand')
        lane.client_action('chat',text='/trigger tarot.action set 1')
        state=lane.wait_state(lambda s:bool(card_items(s)),'explicit draw with '+offhand)
        if len(card_keys(deck_item(state,'numbers')))!=11:raise AssertionError('Explicit draw failed with an occupied offhand')
        record('ordinary_offhand_'+offhand.split(':')[1]+'_does_not_also_draw',explicit_control_works=True)
    for name,block,y,pitch,accepted in [
        ('full_block_top','minecraft:oak_planks',-60,20,True),
        ('full_block_side','minecraft:oak_planks',-59,0,False),
        ('full_block_underside','minecraft:oak_planks',-58,-20,False),
        ('bottom_slab_empty_upper_half','minecraft:oak_slab[type=bottom]',-59,0,False),
        ('bottom_slab_top','minecraft:oak_slab[type=bottom]',-60,35,True),
        ('top_slab_top','minecraft:oak_slab[type=top]',-60,20,True),
    ]:
        fresh();lane.client_action('chat',text='/trigger tarot.action set 1')
        state=lane.wait_state(lambda s:bool(card_items(s)),'card for '+name);card=card_items(state)[0][0]
        lane.client_action('hold',slot=card['slot']-36);lane.rcon(f'setblock 0 {y} 2 {block}');lane.rcon(f'tp TarotLab 0.5 -60 0.5 0 {pitch}')
        lane.client_action('chat',text='/trigger tarot.action set 4');state=lane.client_action('snapshot')
        placed='Test passed' in lane.rcon('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]')
        if placed!=accepted or bool(card_items(state))==accepted:raise AssertionError('Wrong placement result for '+name)
        if not accepted and card_items(state)[0][0]['components']!=card['components']:raise AssertionError('Refused placement changed the held card')
        record('placement_'+name,accepted=accepted)
    if 'Test passed' in lane.rcon('execute if entity @e[type=minecraft:marker]'):raise AssertionError('Ray measurement marker leaked')
    record('placement_probe_entities_do_not_persist')
    fresh();lane.rcon('summon minecraft:pig 0.5 -60 0.5 {Tags:["tarot.lab_pig"],NoAI:1b,Saddle:1b}')
    try:
        if list(__import__('profiles').PROFILES).index(lane.version)>=list(__import__('profiles').PROFILES).index('1.21.6'):
            equipped=lane.rcon('item replace entity @e[type=minecraft:pig,tag=tarot.lab_pig,limit=1] saddle with minecraft:saddle')
            if 'Replaced' not in equipped:raise AssertionError('Pig fixture was not saddled: '+equipped)
        lane.rcon('ride TarotLab mount @e[type=minecraft:pig,tag=tarot.lab_pig,limit=1]')
        until=time.monotonic()+12
        while lane.client_action('mount_state').get('vehicle')!='pig':
            if time.monotonic()>until:raise TimeoutError('Client did not observe its pig mount')
            time.sleep(.05)
        state=lane.client_action('raw_use')
        lane.client_action('raw_use');state=lane.client_action('snapshot')
        if card_items(state) or len(card_keys(deck_item(state,'numbers')))!=12:raise AssertionError('Unexpected mounted vanilla use behavior; revisit carrier policy')
        lane.client_action('chat',text='/trigger tarot.action set 1')
        state=lane.wait_state(lambda s:bool(card_items(s)),'mounted explicit draw')
        if len(card_keys(deck_item(state,'numbers')))!=11:raise AssertionError('Mounted trigger did not draw once')
        record('mounted_pig_uses_explicit_controls_without_losing_cards',vanilla_use_takes_priority=True)
    finally:lane.rcon('ride TarotLab dismount');lane.rcon('kill @e[type=minecraft:pig,tag=tarot.lab_pig]')
    return checks

def main(version,adapter=False):
    from universal_lab import ZipLane
    lane=VanillaLane(version) if adapter else ZipLane(version)
    lane.server_dir=RUNTIME/('refinement-server-'+version);lane.world_dir=lane.server_dir/lane.world_name
    result={'minecraft':version,'scope':'Official vanilla engine; focused delayed-input and surface-shape regressions, plus mounted carrier boundary','checks':[]}
    if not adapter:result['combined_zip_sha256']=sha(lane.archive)
    try:
        lane.download_server();lane.start();lane.start_player();result['checks']=run(lane)
        if not adapter:lane.check_fixtures()
        result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines
        write_json(ROOT/f'content/tarot/evidence/refinement-{version}.json',result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='1.21.11');p.add_argument('--adapter',action='store_true');a=p.parse_args();main(a.version,a.adapter)
