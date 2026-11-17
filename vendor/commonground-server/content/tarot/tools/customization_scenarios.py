"""Complete card instances retain annotations through storage and redraw."""
import json,time
from pathlib import Path
from game_lab import deck_item,card_keys,card_items
from profiles import profile

def prepare_customizations(lane):
    spec=profile(lane.version);folder='item_modifiers' if spec['plural_paths'] else 'item_modifier'
    fixtures=lane.world_dir/'datapacks/tarot/data/tarot'/folder/'lab'
    if not fixtures.resolve().is_relative_to(lane.server_dir.resolve()):raise ValueError('Unsafe fixture root')
    fixtures.mkdir(parents=True,exist_ok=True)
    text={'text':'A card from my friend','italic':False}
    lore={'text':'Do not lose this note','color':'gold'}
    mutations={
        'renamed':{'minecraft:custom_name':text if spec['text_objects'] else json.dumps(text)},
        'annotated':{'minecraft:lore':[lore if spec['text_objects'] else json.dumps(lore)]},
        'repair_history':{'minecraft:repair_cost':1},
        'extra_component':{'minecraft:enchantment_glint_override':True},
    }
    kind='type' if lane.version=='26.3' else 'function'
    for name,components in mutations.items():
        (fixtures/(name+'.json')).write_text(json.dumps({kind:'minecraft:set_components','components':components}),encoding='utf-8')
    (fixtures/'custom_data.json').write_text(json.dumps({kind:'minecraft:copy_custom_data','source':{'type':'minecraft:storage','source':'tarot:lab'},'ops':[{'source':'note','target':'note','op':'replace'}]}),encoding='utf-8')
    lane.rcon('data modify storage tarot:lab note set value "Keep this card safe"')
    lane.rcon('reload');time.sleep(.5)
    if spec['legacy_models']:
        lane.client_action('quit');lane.client_process.wait(timeout=10);lane.client_process=None;lane.start_player()
    return mutations

def run_customizations(lane):
    mutations=prepare_customizations(lane)
    checks=[]
    def move_to_offhand(slot):
        source=f'hotbar.{slot-36}' if slot>=36 else f'inventory.{slot-9}'
        lane.rcon(f'item replace entity TarotLab weapon.offhand from entity TarotLab {source}')
        lane.rcon(f'item replace entity TarotLab {source} with minecraft:air')
    for name in [*mutations,'custom_data']:
        lane.rcon('clear TarotLab');lane.player_function('tarot:give/numbers');lane.client_action('hold',slot=0)
        state=lane.client_action('chat',text='/trigger tarot.action set 1')['snapshot']
        card=card_items(state,'numbers')[0][0];move_to_offhand(card['slot'])
        lane.rcon(f'item modify entity TarotLab weapon.offhand tarot:lab/{name}')
        before=lane.client_action('snapshot')
        after=lane.client_action('chat',text='/trigger tarot.action set 3')['snapshot']
        expected=before['offhand']['components'];key=card_items(before,'numbers')[0][1]['key']
        if after.get('offhand') or card_keys(deck_item(after,'numbers'))[0]!=key:raise AssertionError('Annotated card did not enter stack: '+name)
        after=lane.client_action('chat',text='/trigger tarot.action set 1')['snapshot']
        restored=card_items(after,'numbers')
        if len(restored)!=1 or restored[0][0]['components']!=expected:raise AssertionError('Customized card changed on redraw: '+name)
        checks.append({'name':'customized_instance_round_trip_'+name,'passed':True,'item_preserved':True})
    # Positive controls exercise every printed Numbers name through the new guard.
    lane.rcon('clear TarotLab');lane.player_function('tarot:give/numbers');lane.client_action('hold',slot=0)
    for _ in range(12):lane.client_action('chat',text='/trigger tarot.action set 1')
    for _ in range(12):
        state=lane.client_action('snapshot');card=card_items(state,'numbers')[0][0];move_to_offhand(card['slot'])
        state=lane.client_action('chat',text='/trigger tarot.action set 3')['snapshot']
        if state.get('offhand'):raise AssertionError('Canonical printed card was incorrectly rejected')
    if len(card_keys(deck_item(state,'numbers')))!=12:raise AssertionError('Canonical return sequence lost cards')
    checks.append({'name':'all_twelve_canonical_returns_accepted','passed':True,'returned':12})
    lane.rcon('clear TarotLab');lane.player_function('tarot:give/rider');lane.client_action('hold',slot=0)
    state=lane.client_action('chat',text='/trigger tarot.action set 1')['snapshot']
    move_to_offhand(card_items(state,'rider')[0][0]['slot'])
    state=lane.client_action('chat',text='/trigger tarot.action set 3')['snapshot']
    if state.get('offhand') or len(card_keys(deck_item(state,'rider')))!=78:raise AssertionError('Canonical Rider return failed')
    checks.append({'name':'canonical_rider_return_accepted','passed':True,'remaining':78})
    return checks
