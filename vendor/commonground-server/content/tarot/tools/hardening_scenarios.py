"""Adversarial fixtures and actual survival crafting on the owned vanilla world."""
import json, math
from game_lab import deck_item,card_keys,card_items,tarot_data
from profiles import profile

def run_hardening(lane):
    checks=[]
    def record(name,**values):checks.append({'name':name,'passed':True,**values})
    def snap():return lane.client_action('snapshot')
    def trigger(n):return lane.client_action('chat',text=f'/trigger tarot.action set {n}')['snapshot']
    def fixture(cards, count=1):
        lane.rcon('clear TarotLab')
        large=isinstance(cards,list) and len(cards)>20
        custom={'tarot':{'kind':'deck','module':'numbers','cards':[] if large else cards,'kept_note':'preserve this'}}
        components='minecraft:custom_data='+json.dumps(custom,separators=(',',':'))
        if count==1:
            response=lane.rcon(f'item replace entity TarotLab hotbar.0 with minecraft:carrot_on_a_stick[{components}] 1')
            if 'Replaced' not in response:raise AssertionError('Deck fixture rejected by engine: '+response)
        else:
            # Component-removal syntax itself differs in older command parsers.
            response=lane.rcon(f'give TarotLab minecraft:carrot_on_a_stick[{components},!minecraft:max_damage,!minecraft:damage,minecraft:max_stack_size=64] 2')
            if 'Gave' not in response:
                lane.rcon('clear TarotLab');s=snap();pos=s['position'];x,y,z=math.floor(pos['x'])+2,math.floor(pos['y'])+1,math.floor(pos['z'])+2
                lane.rcon(f'setblock {x} {y} {z} minecraft:chest')
                stack={'Slot':0,'id':'minecraft:carrot_on_a_stick','count':2,'components':{'minecraft:custom_data':custom}}
                lane.rcon(f'data modify block {x} {y} {z} Items set value '+json.dumps([stack],separators=(',',':')))
                lane.rcon(f'item replace entity TarotLab hotbar.0 from block {x} {y} {z} container.0')
                lane.rcon(f'item replace block {x} {y} {z} container.0 with minecraft:air')
        lane.client_action('hold',slot=0)
        if large:
            lane.rcon('data modify storage tarot:runtime cards set value []')
            for row in cards:lane.rcon('data modify storage tarot:runtime cards append value '+json.dumps(row,separators=(',',':')))
            lane.rcon('item modify entity TarotLab weapon.mainhand tarot:deck_sync')
        return lane.wait_state(lambda s:tarot_data(s.get('held'))=={**custom['tarot'],'cards':cards},'exact deck fixture')
    canonical=[{'key':'numbers/number-'+str(n)} for n in list(range(1,10))+[11,22,33]]
    # Keep actual factory-printed singletons, so the later customization guard
    # cannot mask a malformed-deck or low-budget regression.
    fixture([canonical[-1]])
    state=trigger(1);printed=card_items(state,'numbers')
    if len(printed)!=1:raise AssertionError('Factory return fixture did not draw')
    pos=state['position'];cx,cy,cz=math.floor(pos['x'])+3,math.floor(pos['y'])+1,math.floor(pos['z'])+3
    lane.rcon(f'setblock {cx} {cy} {cz} minecraft:chest')
    slot=printed[0][0]['slot'];source=f'hotbar.{slot-36}' if slot>=36 else f'inventory.{slot-9}'
    lane.rcon(f'item replace block {cx} {cy} {cz} container.0 from entity TarotLab {source}')
    def equip_printed():
        lane.rcon(f'item replace entity TarotLab weapon.offhand from block {cx} {cy} {cz} container.0')
        lane.wait_state(lambda s:s.get('offhand') and s['offhand']['count']==1 and (tarot_data(s['offhand']) or {}).get('key')==canonical[-1]['key'],'actual valid offhand fixture')
    malformed={
        'bad_payload':[{'key':'numbers/number-1','item':{'id':'minecraft:diamond','count':1}}],
        'foreign_key':[{'key':'missing_pack/not_loaded'}],
        'unknown_key':[{'key':'numbers/not_a_card'}],
        'non_list':{'key':'numbers/number-1'},
        'wrong_entry_type':['numbers/number-1'],
        'oversized':[canonical[0]]*129,
    }
    for label,contents in malformed.items():
        state=fixture(contents);before=tarot_data(state['held'])
        equip_printed()
        offhand=tarot_data(snap()['offhand'])
        for action in [1,2,3]:
            state=trigger(action)
            if tarot_data(state['held'])!=before or len(card_items(state))!=1 or tarot_data(state['offhand'])!=offhand:
                raise AssertionError(f'{label}: invalid deck mutated or emitted a card')
        record('invalid_deck_preserved_'+label,actions=3,valid_return_card_preserved=True)
    state=fixture(canonical,2)
    if state['held']['count']!=2:
        checks.append({'name':'stacked_decks_rejected_without_loss','status':'fixture_rejected_by_engine','observed_count':state['held']['count'],'note':'No runtime overstack claim from a singleton fixture'})
    else:
        before=tarot_data(state['held'])
        for action in [1,2]:
            state=trigger(action)
            if state['held']['count']!=2 or tarot_data(state['held'])!=before or card_items(state):raise AssertionError('Stacked deck forked its contents')
        record('stacked_decks_rejected_without_loss',stack=2)

    # A stacked offhand card must never be consumed wholesale as one card.
    fixture(canonical[1:])
    lane.rcon('item replace entity TarotLab weapon.offhand with minecraft:paper[minecraft:custom_data={tarot:{kind:"card",module:"numbers",key:"numbers/number-1"}}] 2')
    state=trigger(3)
    if len(card_keys(deck_item(state,'numbers')))!=11 or state['offhand']['count']!=2:
        raise AssertionError('Returning a stacked card lost or minted cards')
    record('stacked_offhand_return_preserved',stack=2,remaining=11)

    fixture(canonical)
    lane.rcon('execute as TarotLab store result score @s tarot.use run trigger tarot.action set 1')
    state=lane.wait_state(lambda s:deck_item(s,'numbers') and len(card_keys(deck_item(s,'numbers')))!=12 and bool(card_items(s)),'simultaneous input inventory update')
    if len(card_keys(deck_item(state,'numbers')))!=11 or len(card_items(state))!=1:
        raise AssertionError('Simultaneous physical/trigger input did not deal exactly once')
    record('simultaneous_inputs_deal_once',remaining=11)

    # Reproduce the confirmed low-command-budget edge without allowing mutation.
    rule=profile(lane.version)['command_rule']
    for limit in [25,50,100,1000,32768]:
        fixture([])
        equip_printed()
        lane.rcon('scoreboard players set TarotLab tarot.cool 0')
        try:
            response=lane.rcon(f'gamerule {rule} {limit}')
            if 'Unknown' in response or 'Incorrect' in response:raise AssertionError('Command budget fixture was not applied')
            lane.rcon('execute as TarotLab run function tarot:return')
        finally:lane.rcon(f'gamerule {rule} 65536')
        state=snap()
        if card_keys(deck_item(state,'numbers')) or not state.get('offhand') or state['offhand']['count']!=1:
            raise AssertionError(f'Low command budget {limit} changed card custody')
    record('reduced_command_budget_rejected_without_loss',settings=[25,50,100,1000,32768])

    # Real crafting-table clicks in Survival; the player has no command authority.
    try:
        lane.rcon('gamemode survival TarotLab');lane.rcon('deop TarotLab')
        for module,ingredient,total in [('rider','ink_sac',78),('numbers','lapis_lazuli',12)]:
            lane.rcon('clear TarotLab');state=snap();pos=state['position']
            x,y,z=math.floor(pos['x'])+1,math.floor(pos['y']),math.floor(pos['z'])
            lane.rcon(f'setblock {x} {y} {z} minecraft:crafting_table')
            lane.rcon('give TarotLab minecraft:paper 8');lane.rcon(f'give TarotLab minecraft:{ingredient} 1')
            state=lane.client_action('craft_deck',timeout=45,x=x,y=y,z=z,ingredient=ingredient)
            deck=deck_item(state,module)
            if not deck or len(card_keys(deck))!=total or any(i['name'] in {'paper',ingredient} for i in state['items']):
                raise AssertionError(f'{module}: survival crafting did not conserve inputs or create the full physical deck')
            lane.client_action('equip',slot=deck['slot'])
            lane.client_action('use');state=snap()
            if len(card_keys(deck_item(state,module)))!=total-1 or len(card_items(state,module))!=1:
                raise AssertionError('Non-operator survival right-click failed')
            record('survival_crafting_and_use_'+module,cards=total,player_is_operator=False,ingredients_consumed=True)
    finally:lane.rcon('op TarotLab');lane.rcon('gamemode creative TarotLab')
    return checks
