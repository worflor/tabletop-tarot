"""Concrete ordered-instance and tabletop tests in owned vanilla worlds."""
import argparse,json,time
from pathlib import Path
from game_lab import VanillaLane,write_json,sha,deck_item,card_keys,card_items,tarot_data,unwrap_nbt
from profiles import PROFILES,profile

def run_physical(lane,checks=None):
    checks=[] if checks is None else checks
    # Earlier crafting/chest fixtures can obstruct the ray without being visible
    # in the selected card's inventory snapshot. Give this suite a clear venue.
    lane.rcon('tp TarotLab 0.5 -60 0.5 0 20')
    lane.rcon('fill -6 -60 -6 16 -56 16 minecraft:air')
    lane.rcon('execute at TarotLab run kill @e[type=minecraft:item,distance=..24]')
    def record(name,**details):checks.append({'name':name,'passed':True,**details});print(name,flush=True)
    def snap():return lane.client_action('snapshot')
    def trigger(n):return lane.client_action('chat',text=f'/trigger tarot.action set {n}')['snapshot']
    def fresh(module='numbers'):
        lane.rcon('clear TarotLab');lane.rcon('scoreboard players set TarotLab tarot.cool 0')
        lane.player_function('tarot:give/'+module);state=lane.wait_state(lambda s:deck_item(s,module) is not None,'fresh stack')
        lane.client_action('hold',slot=0);return state
    def source(slot):return f'hotbar.{slot-36}' if slot>=36 else f'inventory.{slot-9}'
    def offhand(slot):
        lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab '+source(slot))
        lane.rcon('item replace entity TarotLab '+source(slot)+' with minecraft:air')
    def wait_response(command,predicate,label):
        until=time.monotonic()+12
        while True:
            response=lane.rcon(command)
            if predicate(response):return response
            if time.monotonic()>until:raise TimeoutError(label+': '+response)
            time.sleep(.05)
    def act(client=None,**args):
        client=lane if client is None else client;until=time.monotonic()+12
        while 'has 0 ' not in client.rcon(f'scoreboard players get {client.player_name} tarot.cool'):
            if time.monotonic()>until:raise TimeoutError('Physical input cooldown did not clear')
            time.sleep(.05)
        return client.client_action('touch',**args)
    state=fresh();before=card_keys(deck_item(state,'numbers'));trigger(1)
    state=lane.wait_state(lambda s:len(card_items(s,'numbers'))==1,'top card delivered')
    card,data=card_items(state,'numbers')[0]
    if data['key']!=before[0] or card_keys(deck_item(state,'numbers'))!=before[1:]:raise AssertionError('Draw did not take exactly the top card')
    record('ordered_top_draw',key=data['key'])
    offhand(card['slot']);state=trigger(3)
    state=lane.wait_state(lambda s:not s.get('offhand'),'top insertion')
    if card_keys(deck_item(state,'numbers'))!=before:raise AssertionError('Insertion did not restore original order')
    record('top_insertion_restores_order')
    # A player-written note stays inside the same physical card.
    trigger(1);state=lane.wait_state(lambda s:len(card_items(s,'numbers'))==1,'card for annotation');offhand(card_items(state,'numbers')[0][0]['slot'])
    folder='item_modifiers' if profile(lane.version)['plural_paths'] else 'item_modifier';fixtures=lane.world_dir/f'datapacks/tarot/data/tarot/{folder}/physical_lab';fixtures.mkdir(parents=True,exist_ok=True)
    name={'text':'A keepsake from Rowan','italic':False};lore={'text':'Meet me at the old café\nKeep "this" card safe.','color':'gold'}
    comp={'minecraft:custom_name':name if profile(lane.version)['text_objects'] else json.dumps(name),'minecraft:lore':[lore if profile(lane.version)['text_objects'] else json.dumps(lore)],'minecraft:repair_cost':3,'minecraft:enchantment_glint_override':False}
    (fixtures/'note.json').write_text(json.dumps({'type' if lane.version=='26.3' else 'function':'minecraft:set_components','components':comp}));lane.rcon('reload');time.sleep(.5)
    lane.rcon('item modify entity TarotLab weapon.offhand tarot:physical_lab/note');annotated=snap()['offhand']['components']
    trigger(3);state=lane.wait_state(lambda s:not s.get('offhand'),'annotated insertion');trigger(1)
    state=lane.wait_state(lambda s:len(card_items(s,'numbers'))==1,'annotated redraw')
    if card_items(state,'numbers')[0][0]['components']!=annotated:raise AssertionError('Card annotations changed during storage')
    record('complete_instance_round_trip_preserves_notes')
    if any(e['name']=='armor_stand' for e in lane.client_action('entities')['entities']):raise AssertionError('Temporary carrier leaked')
    record('temporary_item_carrier_removed')
    # One deliberate physical placement: card forward, stack in offhand.
    card=card_items(state,'numbers')[0][0]
    lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab hotbar.0')
    lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:air')
    lane.client_action('hold',slot=card['slot']-36)
    lane.rcon('setblock 0 -60 2 minecraft:oak_planks');lane.rcon('tp TarotLab 0.5 -60 0.5 0 20')
    lane.client_action('use_offhand')
    state=lane.wait_state(lambda s:not card_items(s),'placed card leaves inventory')
    entities=lane.client_action('entities')['entities'];touches=[e for e in entities if e['name']=='interaction'];visuals=[e for e in entities if e['name']=='item_display']
    if len(touches)!=1 or len(visuals)!=1:raise AssertionError('Placed card must have one exact visual and one hitbox: '+str(entities))
    touch=touches[0];record('offhand_use_places_exact_card',hitbox=touch['uuid'],visual=visuals[0]['uuid'])
    act(id=touch['id'])
    response=wait_response('scoreboard players get @e[type=minecraft:item_display,tag=tarot.placed,limit=1] tarot.face',lambda r:'has 1 ' in r,'placed card reveal')
    if 'has 1 ' not in response:raise AssertionError('Right-click did not flip: '+response)
    record('right_click_flips_card')
    before=lane.rcon('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] Rotation')
    lane.client_action('sneak',enabled=True);act(id=touch['id'])
    after=wait_response('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] Rotation',lambda r:r!=before,'placed card rotation')
    lane.client_action('sneak',enabled=False)
    if before==after:raise AssertionError('Sneak-use did not rotate')
    record('sneak_right_click_rotates_card')
    act(id=touch['id'],attack=True)
    state=lane.wait_state(lambda s:bool(card_items(s)),'picked up placed card')
    if card_items(state)[0][0]['components']!=annotated:raise AssertionError('Placed card lost annotation')
    if any(e['name'] in {'item_display','interaction'} for e in lane.client_action('entities')['entities']):raise AssertionError('Placed pair leaked after pickup')
    record('attack_retrieves_same_annotated_instance')
    # The explicit placement fallback works with loose paper and no deck tool.
    lane.rcon('item replace entity TarotLab weapon.offhand with minecraft:air')
    lane.client_action('hold',slot=card_items(state)[0][0]['slot']-36);lane.rcon('tp TarotLab 0.5 -60 0.5 0 20')
    trigger(4);lane.wait_state(lambda s:not card_items(s),'trigger placement')
    record('loose_card_trigger_placement')
    lane.rcon('setblock 0 -60 2 minecraft:air');time.sleep(.4)
    root=lane.rcon('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]')
    if 'Test passed' in root:raise AssertionError('Unsupported card did not fall')
    lane.rcon('tp TarotLab 0.5 -60 2.5')
    state=lane.wait_state(lambda s:bool(card_items(s)),'fallen card pickup')
    if card_items(state)[0][0]['components']!=annotated:raise AssertionError('Falling changed card details')
    record('support_removal_drops_same_card_with_vanilla_physics')
    # A full inventory does not erase the placed instance.
    lane.rcon('setblock 0 -60 2 minecraft:oak_planks');lane.rcon('tp TarotLab 0.5 -60 0.5 0 20')
    lane.client_action('hold',slot=card_items(state)[0][0]['slot']-36);trigger(4)
    lane.wait_state(lambda s:not card_items(s),'card placed for full-inventory test')
    touch=next(e for e in lane.client_action('entities')['entities'] if e['name']=='interaction')
    for slot in [*[f'hotbar.{i}' for i in range(9)],*[f'inventory.{i}' for i in range(27)]]:lane.rcon('item replace entity TarotLab '+slot+' with minecraft:dirt 64')
    lane.rcon('scoreboard players set #delivered tarot.sys -1');act(uuid=touch['uuid'],attack=True)
    wait_response('scoreboard players get #delivered tarot.sys',lambda r:'has 0 ' in r,'full inventory pickup was actually attempted')
    if 'Test passed' not in lane.rcon('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]'):raise AssertionError('Full inventory consumed placed card')
    if card_items(snap()):raise AssertionError('Full inventory unexpectedly received card')
    record('full_inventory_keeps_placed_instance')
    # Near-coincident cards are rejected instead of producing ambiguous hitboxes.
    state=fresh('rider');trigger(1);state=lane.wait_state(lambda s:bool(card_items(s,'rider')),'second printed pack')
    lane.client_action('hold',slot=card_items(state,'rider')[0][0]['slot']-36);lane.rcon('tp TarotLab 0.5 -60 0.5 0 20');trigger(4)
    if len(card_items(snap(),'rider'))!=1:raise AssertionError('Coincident placement consumed a card')
    record('coincident_placement_rejected_without_consumption')
    # Keep this separate-card fixture well beyond the intentional 0.6-block spacing guard.
    lane.rcon('setblock 1 -60 2 minecraft:oak_planks');lane.rcon('tp TarotLab 0.5 -60 0.5 -30 20');trigger(4)
    lane.wait_state(lambda s:not card_items(s,'rider'),'second separate tabletop card')
    touches=[e for e in lane.client_action('entities')['entities'] if e['name']=='interaction']
    if len(touches)!=2:raise AssertionError('Two placed cards did not retain separate hitboxes')
    left=min(touches,key=lambda e:e['position']['x']);right=max(touches,key=lambda e:e['position']['x'])
    peer=VanillaLane(lane.version);peer.game_port,peer.rcon_port,peer.password=lane.game_port,lane.rcon_port,lane.password
    try:
        peer.start_player('TarotPeer');lane.rcon('tp TarotPeer 0.5 -60 0.5');lane.rcon('clear TarotLab');lane.rcon('clear TarotPeer')
        until=time.monotonic()+12
        while not any(e.get('uuid')==left['uuid'] for e in peer.client_action('entities')['entities']):
            if time.monotonic()>until:raise TimeoutError('Peer did not observe the shared card')
        peer.client_action('snapshot');lane.client_action('snapshot')
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            attempts=[pool.submit(act,client=client,uuid=left['uuid'],attack=True) for client in [lane,peer]]
            for attempt in attempts:attempt.result()
        main,other=snap(),peer.client_action('snapshot');recovered=card_items(main)+card_items(other)
        if len(recovered)!=1 or recovered[0][0]['components']!=annotated:raise AssertionError('Simultaneous pickup duplicated, lost or changed the targeted card')
        remaining=[e for e in lane.client_action('entities')['entities'] if e['name']=='interaction']
        if len(remaining)!=1 or remaining[0]['uuid']!=right['uuid']:raise AssertionError('Pickup affected the neighbouring card')
        record('two_players_one_exact_card_one_recipient',neighbour_preserved=True)
    finally:
        peer.stop();lane.commands.append({'via':'physical-peer-evidence','commands':peer.commands,'protocol_lines':peer.client_lines})
    act(uuid=right['uuid'],attack=True)
    state=lane.wait_state(lambda s:bool(card_items(s,'rider')),'neighbour pickup');rider=card_items(state,'rider')[0][0];expected=rider['components']
    lane.client_action('hold',slot=rider['slot']-36);lane.rcon('tp TarotLab 0.5 -60 0.5 -20 20');trigger(4)
    entities=lane.client_action('entities')['entities'];touch=next(e for e in entities if e['name']=='interaction');visual=next(e for e in entities if e['name']=='item_display')
    act(uuid=touch['uuid']);lane.client_action('sneak',enabled=True);act(uuid=touch['uuid']);lane.client_action('sneak',enabled=False)
    before_rotation=lane.rcon('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] Rotation')
    before_face=lane.rcon('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] transformation.right_rotation')
    lane.client_action('quit');lane.client_process.wait(timeout=10);lane.client_process=None;lane.stop();lane.process=None;lane.log=None
    lane.start();lane.start_player();state=snap()
    restored=[e for e in lane.client_action('entities')['entities'] if e['name']=='item_display']
    if len(restored)!=1 or restored[0]['uuid']!=visual['uuid']:raise AssertionError('Placed card identity did not survive restart')
    after_rotation=lane.rcon('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] Rotation');after_face=lane.rcon('data get entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] transformation.right_rotation')
    import re
    def yaw(text):return float(re.findall(r'\[(-?[\d.]+)f',text)[0])%360
    if abs(yaw(before_rotation)-yaw(after_rotation))>.01 or before_face!=after_face:raise AssertionError('Physical card pose changed after restart')
    act(uuid=touch['uuid'],attack=True);state=lane.wait_state(lambda s:bool(card_items(s,'rider')),'persistent card retrieval')
    if card_items(state,'rider')[0][0]['components']!=expected:raise AssertionError('Persistent tabletop item changed')
    record('placed_identity_pose_and_item_survive_restart')
    # Exercise every printed item, rather than sampling a few identities.
    seen=[]
    for module_index,module in enumerate(json.loads((lane.pack.parent/'catalogue.json').read_text())['modules']):
        total=sum(c['module']==module for c in json.loads((lane.pack.parent/'catalogue.json').read_text())['cards'])
        state=fresh(module);order=card_keys(deck_item(state,module))
        for i,key in enumerate(order):
            trigger(1);state=lane.wait_state(lambda s:bool(card_items(s,module)),'printed card '+key);item,data=card_items(state,module)[0]
            if data['key']!=key:raise AssertionError('Canonical stack order or printed identity changed')
            if len(card_keys(deck_item(state,module)))!=total-i-1:raise AssertionError('Whole-deck conservation failed')
            # Actual chest storage frees the hand/inventory for the next card.
            cx=4+module_index*12+(i//27)*2;lane.rcon(f'setblock {cx} -60 0 minecraft:chest') if i%27==0 else None
            lane.rcon(f'item replace block {cx} -60 0 container.{i%27} from entity TarotLab '+source(item['slot']))
            lane.rcon('item replace entity TarotLab '+source(item['slot'])+' with minecraft:air');seen.append(key)
        trigger(1)
        if card_items(snap(),module):raise AssertionError('Exhausted stack emitted a card')
    if len(seen)!=len(json.loads((lane.pack.parent/'catalogue.json').read_text())['cards']) or len(set(seen))!=len(seen):raise AssertionError('Not all selected printed identities were exercised')
    record('all_selected_printed_items_drawn_in_order_without_replacement',cards=len(seen))
    # Support loss must settle visibly across a room, not only within reach.
    lane.rcon('item replace entity TarotLab hotbar.1 from block 4 -60 0 container.0');lane.rcon('item replace block 4 -60 0 container.0 with minecraft:air')
    state=lane.wait_state(lambda s:bool(card_items(s,'rider')),'distant-support fixture');expected=card_items(state,'rider')[0][0]['components'];lane.client_action('hold',slot=1)
    lane.rcon('tp TarotLab 0.5 -60 10.5 0 20');lane.rcon('setblock 0 -60 12 minecraft:oak_planks');trigger(4)
    lane.wait_state(lambda s:not card_items(s,'rider'),'distant placed card');lane.rcon('tp TarotLab 0.5 -60 0.5');lane.rcon('setblock 0 -60 12 minecraft:air')
    wait_response('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]',lambda r:'Test passed' not in r,'distant support removal')
    lane.rcon('tp TarotLab 0.5 -60 12.5');state=lane.wait_state(lambda s:bool(card_items(s,'rider')),'distant fallen item')
    if card_items(state,'rider')[0][0]['components']!=expected:raise AssertionError('Distant fall changed the physical card')
    record('support_changes_settle_beyond_interaction_range',distance_blocks=12)
    return checks

def main():
    p=argparse.ArgumentParser();p.add_argument('--version',choices=PROFILES,required=True);a=p.parse_args();lane=VanillaLane(a.version)
    evidence={'minecraft':a.version,'scope':'ordered complete-item stacks and physical tabletop handling','checks':[]}
    try:
        lane.download_server();lane.start();lane.start_player();evidence['datapack_sha256']={f.relative_to(lane.pack).as_posix():sha(f) for f in lane.pack.rglob('*') if f.is_file()}
        run_physical(lane,evidence['checks']);evidence['passed']=True
    except Exception as e:
        evidence['passed']=False;evidence['error']=repr(e)
        if lane.process and lane.process.poll() is None:
            for command in ['scoreboard players get #dropped tarot.sys','scoreboard players get #supported tarot.sys','data get storage tarot:runtime chosen','execute as @e[type=minecraft:item] run data get entity @s Item','execute as @e[type=minecraft:item_display,tag=tarot.placed] run data get entity @s Pos']:
                try:lane.rcon(command)
                except Exception:pass
        raise
    finally:
        lane.stop();evidence['commands']=lane.commands;evidence['protocol_lines']=lane.client_lines;evidence['processes']=lane.starts
        write_json(lane.pack.parents[2]/'evidence'/('physical-'+a.version+'.json'),evidence)

if __name__=='__main__':main()
