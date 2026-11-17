"""Real recipe-book discovery, crafting-grid safety and direct loose-card input."""
import json,time
from game_lab import card_items,deck_item,card_keys,tarot_data
from profiles import profile

def run(lane):
    checks=[]
    def record(name,**details):checks.append({'name':name,'passed':True,**details});print(name,flush=True)
    def snap():return lane.client_action('snapshot')
    def fresh():
        lane.rcon('clear TarotLab');lane.rcon('kill @e[type=minecraft:item_display,tag=tarot.placed]');lane.rcon('kill @e[type=minecraft:interaction,tag=tarot.touch]')
        lane.rcon('tp TarotLab 0.5 -60 0.5 0 20');lane.client_action('hold',slot=0)
    fresh();lane.rcon('gamemode survival TarotLab');lane.rcon('deop TarotLab')
    lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data={tarot:{kind:"deck",module:"numbers",cards:[{key:"numbers/number-33"}],kept_note:"old band"}}]')
    lane.client_action('chat',text='/trigger tarot.action set 1')
    state=lane.wait_state(lambda s:bool(card_items(s)),'key-only legacy draw')
    if card_items(state)[0][0]['name']!='carrot_on_a_stick':raise AssertionError('Key-only prototype did not print a protected usable card')
    if tarot_data(deck_item(state,'numbers')).get('kept_note')!='old band':raise AssertionError('Legacy band note changed')
    record('key_only_legacy_band_keeps_notes_and_draws_safe_card')
    fresh()
    modern=profile(lane.version)['text_objects']
    name={'text':'Kept from the old pack','color':'gold'};note={'text':'Rowan’s note: keep "this" card.','italic':False}
    components={'minecraft:max_stack_size':1,'minecraft:max_damage':37,'minecraft:damage':4,'minecraft:custom_name':name if modern else json.dumps(name,ensure_ascii=False),'minecraft:lore':[note if modern else json.dumps(note,ensure_ascii=False)],'minecraft:repair_cost':7,'minecraft:custom_data':{'tarot':{'kind':'card','key':'numbers/number-1','module':'numbers'},'kept_note':'unique legacy annotation'}}
    legacy={'id':'minecraft:paper','count':1,'components':components}
    lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data={tarot:{kind:"deck",module:"numbers",storage:"native-v1"}},minecraft:charged_projectiles=['+json.dumps(legacy,ensure_ascii=False,separators=(',',':'))+']]')
    lane.rcon('data modify storage tarot_lab:quiet expected set from entity TarotLab SelectedItem.components."minecraft:charged_projectiles"[0].components')
    lane.rcon('data remove storage tarot_lab:quiet expected."minecraft:max_stack_size"')
    lane.rcon('data modify storage tarot_lab:quiet expected."minecraft:custom_data".tarot.carrier_max_damage set from storage tarot_lab:quiet expected."minecraft:max_damage"')
    lane.rcon('data remove storage tarot_lab:quiet expected."minecraft:max_damage"')
    lane.rcon('data modify storage tarot_lab:quiet expected."!minecraft:max_damage" set value {}')
    lane.rcon('data modify storage tarot_lab:quiet expected."minecraft:unbreakable" set value '+('{}' if modern else '{show_in_tooltip:0b}'))
    lane.client_action('chat',text='/trigger tarot.action set 1')
    state=lane.wait_state(lambda s:bool(card_items(s)),'old native paper card upgraded on draw');item=card_items(state)[0][0]
    card_slot=f'hotbar.{item["slot"]-36}' if item['slot']>=36 else f'inventory.{item["slot"]-9}'
    lane.rcon('setblock 4 -60 0 minecraft:chest');lane.rcon('item replace block 4 -60 0 container.0 from entity TarotLab '+card_slot)
    lane.rcon('execute store success score #changed tarot.sys run data modify storage tarot_lab:quiet expected set from block 4 -60 0 Items[0].components')
    if item['name']!='carrot_on_a_stick' or 'has 0 ' not in lane.rcon('scoreboard players get #changed tarot.sys'):raise AssertionError('Paper-carrier upgrade changed a unique annotation')
    lane.rcon('item replace block 4 -60 0 container.0 with minecraft:air')
    record('native_paper_card_upgrades_on_draw_preserving_unique_components')
    encoded=','.join(k+'='+json.dumps(v,ensure_ascii=False,separators=(',',':')) for k,v in components.items())
    def expected_from(source):
        lane.rcon('data modify storage tarot_lab:quiet expected set from '+source)
        lane.rcon('data remove storage tarot_lab:quiet expected."minecraft:max_stack_size"')
        lane.rcon('data modify storage tarot_lab:quiet expected."minecraft:custom_data".tarot.carrier_max_damage set from storage tarot_lab:quiet expected."minecraft:max_damage"')
        lane.rcon('data remove storage tarot_lab:quiet expected."minecraft:max_damage"')
        lane.rcon('data modify storage tarot_lab:quiet expected."!minecraft:max_damage" set value {}')
        lane.rcon('data modify storage tarot_lab:quiet expected."minecraft:unbreakable" set value '+('{}' if modern else '{show_in_tooltip:0b}'))
    fresh();lane.rcon('execute as TarotLab run function tarot:give/numbers')
    lane.rcon('item replace entity TarotLab weapon.offhand with minecraft:paper['+encoded+']')
    expected_from('entity TarotLab '+profile(lane.version)['offhand_components'])
    lane.client_action('chat',text='/trigger tarot.action set 3')
    lane.wait_state(lambda s:not s.get('offhand') and len(card_keys(deck_item(s,'numbers')))==13,'old paper return')
    lane.rcon('execute store success score #changed tarot.sys run data modify storage tarot_lab:quiet expected set from entity TarotLab SelectedItem.components."minecraft:charged_projectiles"[0].components')
    if 'has 0 ' not in lane.rcon('scoreboard players get #changed tarot.sys'):raise AssertionError('Returning old paper changed a unique component')
    record('legacy_paper_return_upgrades_carrier_and_preserves_annotations')
    fresh();lane.rcon('setblock 0 -60 2 minecraft:oak_planks')
    lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:paper['+encoded+']')
    lane.rcon('execute as TarotLab run function tarot:give/numbers')
    state=snap();band=deck_item(state,'numbers');slot=f'hotbar.{band["slot"]-36}' if band['slot']>=36 else f'inventory.{band["slot"]-9}'
    lane.rcon('item replace entity TarotLab weapon.offhand from entity TarotLab '+slot);lane.rcon('item replace entity TarotLab '+slot+' with minecraft:air')
    expected_from('entity TarotLab SelectedItem.components')
    lane.client_action('use_offhand');lane.wait_state(lambda s:not card_items(s),'old paper physical placement')
    visual='@e[type=minecraft:item_display,tag=tarot.placed,limit=1]'
    lane.rcon('execute store success score #changed tarot.sys run data modify storage tarot_lab:quiet expected set from entity '+visual+' item.components')
    if 'has 0 ' not in lane.rcon('scoreboard players get #changed tarot.sys'):raise AssertionError('Legacy placement changed annotations')
    if 'Test passed' not in lane.rcon('execute if data entity '+visual+' item{id:"minecraft:carrot_on_a_stick"}'):raise AssertionError('Legacy placement did not upgrade the carrier')
    touch=next(e for e in lane.client_action('entities')['entities'] if e['name']=='interaction');lane.client_action('touch',id=touch['id'],attack=True)
    lane.wait_state(lambda s:bool(card_items(s)),'upgraded old table card pickup')
    record('legacy_paper_place_and_pickup_preserve_unique_card')
    fresh();conflict=json.loads(json.dumps(components));conflict['minecraft:custom_data']['tarot']['carrier_max_damage']=99
    legacy={'id':'minecraft:paper','count':1,'components':conflict}
    lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick[minecraft:custom_data={tarot:{kind:"deck",module:"numbers",storage:"native-v1"}},minecraft:charged_projectiles=['+json.dumps(legacy,ensure_ascii=False,separators=(',',':'))+']]')
    original=lane.rcon('data get entity TarotLab SelectedItem')
    lane.client_action('chat',text='/trigger tarot.action set 1')
    if lane.rcon('data get entity TarotLab SelectedItem')!=original or card_items(snap()):raise AssertionError('Conflicting carrier history was overwritten or consumed')
    record('conflicting_carrier_history_preserved_without_partial_transfer')
    fresh()
    for module,ink in [('rider','ink_sac'),('numbers','lapis_lazuli')]:
        lane.rcon(f'advancement revoke TarotLab only tarot:recipes/{module}_deck')
        lane.rcon(f'recipe take TarotLab tarot:{module}_deck')
        lane.rcon('give TarotLab minecraft:paper 8');lane.rcon('give TarotLab minecraft:'+ink)
        until=time.monotonic()+5
        while True:
            response=lane.rcon(f'execute as TarotLab if entity @s[advancements={{tarot:recipes/{module}_deck=true}}]')
            if 'Test passed' in response:break
            if time.monotonic()>until:raise AssertionError('Ingredient recipe unlock did not fire: '+response)
            time.sleep(.1)
        response=lane.rcon(f'recipe give TarotLab tarot:{module}_deck')
        if 'already' not in response.lower() and 'No new' not in response:raise AssertionError('Recipe was not already learned from ingredients: '+response)
        lane.rcon('setblock 1 -60 0 minecraft:crafting_table')
        state=lane.client_action('craft_deck',x=1,y=-60,z=0,ingredient=ink)
        if len(card_keys(deck_item(state,module)))!={'rider':78,'numbers':12}[module]:raise AssertionError('Normal crafting result incomplete')
        record('quiet_recipe_book_unlock_and_survival_craft_'+module)
        lane.rcon('clear TarotLab')
    fresh();lane.rcon('execute as TarotLab run function tarot:give/numbers')
    lane.client_action('use');state=lane.wait_state(lambda s:bool(card_items(s)),'new loose card')
    card=card_items(state)[0][0]
    if card['name']!='carrot_on_a_stick':raise AssertionError('New card still uses a craftable paper carrier')
    lane.client_action('hold',slot=card['slot']-36)
    lane.rcon('item replace entity TarotLab weapon.offhand with minecraft:air')
    lane.rcon('setblock 0 -60 2 minecraft:oak_planks')
    lane.client_action('use')
    lane.wait_state(lambda s:not card_items(s),'direct loose-card right-click placement')
    if 'Test passed' not in lane.rcon('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]'):raise AssertionError('No placed card after direct use')
    record('loose_card_right_click_places_without_offhand_band')
    fresh();lane.rcon('give TarotLab minecraft:carrot_on_a_stick');before=snap()
    lane.client_action('use_offhand')
    if card_items(snap()) or deck_item(snap()):raise AssertionError('Unmarked vanilla rod became a card')
    if 'has 0 ' not in lane.rcon('scoreboard players get TarotLab tarot.use'):raise AssertionError('Ordinary rod input not cleared')
    record('ordinary_items_do_not_enter_card_handling')
    # Recipe result is observed inside the actual server-side crafting window.
    for use_card in [False,True]:
        fresh();lane.rcon('setblock 1 -60 0 minecraft:crafting_table')
        lane.rcon('give TarotLab minecraft:paper '+('2' if use_card else '3'));lane.rcon('give TarotLab minecraft:leather')
        if use_card:
            lane.rcon('execute as TarotLab run function tarot:give/numbers');lane.client_action('hold',slot=2)
            state=snap();band=deck_item(state,'numbers');lane.client_action('hold',slot=band['slot']-36);lane.client_action('use')
        result=lane.client_action('craft_probe',x=1,y=-60,z=0,card=use_card,card_slot=card_items(snap())[0][0]['slot'] if use_card else None)
        if use_card and result.get('output'):raise AssertionError('Card substituted for paper in a vanilla book recipe')
        if not use_card and (result.get('output') or {}).get('name')!='book':raise AssertionError('Control paper recipe did not produce a book')
        if use_card and len(card_items(snap()))!=1:raise AssertionError('Crafting probe lost the physical card')
        record('card_cannot_substitute_for_paper' if use_card else 'ordinary_paper_recipe_still_works')
    return checks+run_repair(lane)

def run_repair(lane):
    checks=[]
    lane.rcon('gamemode survival TarotLab');lane.rcon('deop TarotLab')
    for mode in ['ordinary_rods','cards','bands','card_and_band']:
        lane.rcon('clear TarotLab');lane.rcon('tp TarotLab 0.5 -60 0.5');lane.rcon('setblock 1 -60 0 minecraft:crafting_table');lane.client_action('hold',slot=0)
        if mode=='ordinary_rods':lane.rcon('give TarotLab minecraft:carrot_on_a_stick 2')
        else:
            lane.rcon('execute as TarotLab run function tarot:give/numbers')
            if mode=='bands':lane.rcon('execute as TarotLab run function tarot:give/numbers')
            else:
                lane.client_action('chat',text='/trigger tarot.action set 1')
                if mode=='cards':lane.client_action('chat',text='/trigger tarot.action set 1')
        expected=3 if mode=='cards' else 2
        state=lane.wait_state(lambda s:len(s.get('items',[]))==expected,'repair inputs')
        items=[i for i in state['items'] if (tarot_data(i) or {}).get('kind')=='card'] if mode=='cards' else state['items']
        result=lane.client_action('craft_probe',x=1,y=-60,z=0,repair_slots=[i['slot'] for i in items])
        actual=result.get('output');passed=bool(actual) if mode=='ordinary_rods' else not actual
        row={'name':'vanilla_tool_repair_'+mode,'passed':passed,'output_name':actual.get('name') if actual else None};checks.append(row);print(json.dumps(row),flush=True)
    return checks
