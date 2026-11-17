"""Ordered stacks retain complete item instances; only explicit shuffling is random."""
import json
from profiles import profile,STACK_MODELS,stack_model_components
from runtime import CARD_CARRIERS

CAPACITY=128
SLOTS=[f'{kind}.{i}' for kind,n in [('hotbar',9),('inventory',27)] for i in range(n)]

def generate(out,cards,modules,target,w,printed_item,identities=None):
    spec=profile(target);offhand=spec['offhand_components'].removesuffix('.components')
    # 1.21.5 moved all mob equipment, independently of the player text format.
    head='ArmorItems[3]' if spec['offhand_components'].startswith('Inventory') else 'equipment.head'
    validation=[
        'scoreboard players set #valid tarot.sys 0',
        'execute unless items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:count=1] run return 0',
        'data modify storage tarot:runtime cards set value {}',
        'data modify storage tarot:runtime cards set from entity @s SelectedItem.components."minecraft:custom_data".tarot.cards',
        'execute store result score #size tarot.roll run data get storage tarot:runtime cards',
        f'execute unless score #size tarot.roll matches 0..{CAPACITY} run return 0',
        'data remove storage tarot:runtime unchecked','data remove storage tarot:runtime payloads','data remove storage tarot:runtime entry',
        'data modify storage tarot:validation unchecked set from storage tarot:runtime cards',
    ]
    # Match whole valid rows in bulk. Recursively copying the entire stack for
    # every individual payload field was correct but far too costly in game.
    # Keep the validation copy in a separate storage so a match never copies the
    # controller's full deck/queue state. Byte counts come from JSON recipes.
    for card in cards:
        for carrier in CARD_CARRIERS:
            pattern={'key':card['key'],'item_schema':target,'item':{'id':carrier,'count':1,'components':{'minecraft:custom_data':{'tarot':{'kind':'card','key':card['key'],'module':card['module']}}}}}
            encoded=json.dumps(pattern,separators=(',',':'))
            validation += ['data remove storage tarot:validation unchecked['+encoded+']','data remove storage tarot:validation unchecked['+encoded.replace('"count":1','"count":1b')+']']
    validation += ['execute if data storage tarot:validation {unchecked:[]} run scoreboard players set #valid tarot.sys 1','execute unless score #valid tarot.sys matches 1 run function tarot:stack/validate_legacy']
    w('stack/validate',validation)
    w('stack/validate_legacy',[
        'execute if data storage tarot:validation unchecked[].item run return 0',
        'execute if data storage tarot:validation unchecked[].item_schema run return 0',
        'data modify storage tarot:validation legacy set from storage tarot:validation unchecked',
        'scoreboard players set #legacy tarot.sys 1','function tarot:stack/legacy_shape',
        'execute unless score #legacy tarot.sys matches 1 run return 0',
        *[f'data remove storage tarot:validation unchecked[{{key:{json.dumps(c["key"])}}}]' for c in cards],
        'execute if data storage tarot:validation {unchecked:[]} run scoreboard players set #valid tarot.sys 1',
    ])
    w('stack/legacy_shape',[
        'execute unless data storage tarot:validation legacy[0] run return 0',
        'execute store result score #fields tarot.sys run data get storage tarot:validation legacy[0]',
        'execute unless score #fields tarot.sys matches 1 run scoreboard players set #legacy tarot.sys 0',
        'execute unless score #legacy tarot.sys matches 1 run return 0',
        'data remove storage tarot:validation legacy[0]','function tarot:stack/legacy_shape',
    ])
    # A one-tick hidden staging stand provides vanilla's exact item-copy API.
    # Text and components are copied as NBT, never interpolated into commands.
    w('transfer/to_player',[
        'scoreboard players set #delivered tarot.sys 0',
        'function tarot:card/upgrade_chosen','execute unless score #carrier_safe tarot.sys matches 1 run return 0',
        *[f'execute unless items entity @s {slot} * run return run function tarot:transfer/slot_{i}' for i,slot in enumerate(SLOTS)],
        'title @s actionbar {"text":"Make room in your inventory first.","color":"gray"}',
    ])
    for i,slot in enumerate(SLOTS):w(f'transfer/slot_{i}',[f'data modify storage tarot:runtime slot set value "{slot}"','function tarot:transfer/ready'])
    w('transfer/ready',['tag @a remove tarot.actor','tag @s add tarot.actor','execute positioned ~ ~-128 ~ summon minecraft:armor_stand run function tarot:transfer/stage','tag @s remove tarot.actor'])
    w('transfer/stage',[
        'data merge entity @s {Tags:["tarot.transfer"],Invisible:1b,Marker:1b,NoGravity:1b,Silent:1b,Invulnerable:1b}',
        *(['data modify entity @s ArmorItems set value [{},{},{},{}]'] if head.startswith('Armor') else ['data modify entity @s equipment set value {}']),
        f'execute store success score #loaded tarot.sys run data modify entity @s {head} set from storage tarot:runtime chosen.item',
        'execute unless items entity @s armor.head #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set #loaded tarot.sys 0',
        'data modify storage tarot:runtime compare set from storage tarot:runtime chosen.item.components."minecraft:custom_data".tarot.key',
        f'execute store success score #different tarot.sys run data modify storage tarot:runtime compare set from entity @s {head}.components."minecraft:custom_data".tarot.key',
        'execute if score #different tarot.sys matches 1 run scoreboard players set #loaded tarot.sys 0',
        'data modify storage tarot:runtime compare set from storage tarot:runtime chosen.item.components',
        f'execute store success score #different tarot.sys run data modify storage tarot:runtime compare set from entity @s {head}.components',
        'execute if score #different tarot.sys matches 1 run scoreboard players set #loaded tarot.sys 0',
        'execute if score #loaded tarot.sys matches 1 run function tarot:transfer/deliver with storage tarot:runtime',
        'item replace entity @s armor.head with minecraft:air','kill @s',
    ])
    w('transfer/deliver',['$execute store success score #delivered tarot.sys run item replace entity @a[tag=tarot.actor,limit=1] $(slot) from entity @s armor.head'])
    w('stack/draw',[
        'execute unless data storage tarot:runtime cards[0] run title @s actionbar {"text":"The band is empty. Put a card on top.","color":"gray"}',
        'execute unless data storage tarot:runtime cards[0] run return 0',
        'data modify storage tarot:runtime chosen set from storage tarot:runtime cards[0]',
        'execute unless data storage tarot:runtime chosen.item run function tarot:stack/legacy',
        'function tarot:transfer/to_player','execute unless score #delivered tarot.sys matches 1 run return 0',
        'data remove storage tarot:runtime cards[0]','function tarot:stack/sync','function tarot:sound/card',
    ])
    w('stack/legacy',[f'execute if data storage tarot:runtime chosen{{key:{json.dumps(c["key"])}}} run data modify storage tarot:runtime chosen.item set value '+json.dumps(printed_item(c,target),ensure_ascii=False,separators=(',',':')) for c in cards])
    w('stack/return',[
        f'execute if score #size tarot.roll matches {CAPACITY}.. run title @s actionbar {{"text":"This band holds at most {CAPACITY} cards.","color":"gray"}}',
        f'execute if score #size tarot.roll matches {CAPACITY}.. run return 0',
        *['execute if items entity @s weapon.offhand #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~'+json.dumps({'tarot':{'kind':'card','key':c['key'],'module':c['module']}},separators=(',',':'))+'] run return run function tarot:stack/insert' for c in cards],
        'title @s actionbar {"text":"Hold one printed card in your offhand to put it on top.","color":"gray"}',
    ])
    w('stack/insert',[
        'data modify storage tarot:runtime entry set value {}',
        'data modify storage tarot:runtime entry.item_schema set value '+json.dumps(target),
        f'data modify storage tarot:runtime entry.item set from entity @s {offhand}',
        'data remove storage tarot:runtime entry.item.Slot',
        'data modify storage tarot:runtime entry.key set from storage tarot:runtime entry.item.components."minecraft:custom_data".tarot.key',
        'data modify storage tarot:runtime cards prepend from storage tarot:runtime entry',
        'function tarot:stack/sync','execute unless score #committed tarot.sys matches 1 run return 0',
        'item replace entity @s weapon.offhand with minecraft:air','function tarot:sound/card',
    ])
    modifier={'function':'minecraft:copy_custom_data','source':{'type':'minecraft:storage','source':'tarot:runtime'},'ops':[{'source':'cards','target':'tarot.cards','op':'replace'}]}
    if target=='26.3':modifier['type']=modifier.pop('function')
    path=out/'data/tarot/item_modifier/deck_sync.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(modifier,indent=2)+'\n')
    w('stack/sync',['execute store success score #committed tarot.sys run item modify entity @s weapon.mainhand tarot:deck_sync','execute store result score #size tarot.roll run data get storage tarot:runtime cards','function tarot:stack/appearance'])
    w('stack/appearance',[
        *[f'execute if score #size tarot.roll matches 0 if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:custom_data~{{tarot:{{module:"{m}"}}}}] run return run function tarot:stack/appearance/{m}' for m in modules],
        'data modify storage tarot:runtime top set from storage tarot:runtime cards[0]',
        *[f'execute if data storage tarot:runtime top{{key:{json.dumps(c["key"])}}} run return run function tarot:stack/appearance/{c["module"]}' for c in cards],
    ])
    for m in modules:
        w('stack/appearance/'+m,[f'execute if score #size tarot.roll matches {lo}..{hi} run item modify entity @s weapon.mainhand tarot:model/{m}_{label}' for label,lo,hi,_,_ in STACK_MODELS])
        for label,lo,hi,_,_ in STACK_MODELS:
            modifier={'type' if target=='26.3' else 'function':'minecraft:set_components','components':stack_model_components(m,lo,target,identities)}
            path=out/f'data/tarot/item_modifier/model/{m}_{label}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(modifier,indent=2)+'\n')
    # Shuffle small integer references, not whole annotated items on every swap.
    # Keep large payloads outside the control storage until the permutation is
    # assembled. This preserves the same ordered on-item format and instances.
    shuffle=['data modify storage tarot:shuffle_source cards set from storage tarot:runtime cards','data remove storage tarot:runtime cards','data modify storage tarot:shuffle indices set value []']
    shuffle += [f'execute if score #size tarot.roll matches {i+1}.. run data modify storage tarot:shuffle indices append value {i}' for i in range(CAPACITY)]
    for i in range(CAPACITY-1):
        shuffle += [f'execute if score #size tarot.roll matches {i+2}.. run scoreboard players set #i tarot.i {i}',f'execute if score #size tarot.roll matches {i+2}.. run scoreboard players operation #max tarot.j = #size tarot.roll',f'execute if score #size tarot.roll matches {i+2}.. run scoreboard players remove #max tarot.j {i+1}',f'execute if score #size tarot.roll matches {i+2}.. store result storage tarot:shuffle max int 1 run scoreboard players get #max tarot.j',f'execute if score #size tarot.roll matches {i+2}.. run function tarot:stack/random with storage tarot:shuffle',f'execute if score #size tarot.roll matches {i+2}.. run scoreboard players operation #j tarot.j += #i tarot.i',f'execute if score #size tarot.roll matches {i+2}.. store result storage tarot:shuffle j int 1 run scoreboard players get #j tarot.j',f'execute if score #size tarot.roll matches {i+2}.. run function tarot:stack/swap_{i} with storage tarot:shuffle']
        w(f'stack/swap_{i}',['data modify storage tarot:shuffle swap set from storage tarot:shuffle indices['+str(i)+']','$data modify storage tarot:shuffle indices['+str(i)+'] set from storage tarot:shuffle indices[$(j)]','$data modify storage tarot:shuffle indices[$(j)] set from storage tarot:shuffle swap'])
    w('stack/shuffle',shuffle+['data modify storage tarot:runtime cards set value []','function tarot:stack/assemble','function tarot:stack/sync','data remove storage tarot:shuffle_source cards','execute if score #size tarot.roll matches 2.. run function tarot:sound/shuffle'])
    w('stack/assemble',['execute unless data storage tarot:shuffle indices[0] run return 0','data modify storage tarot:shuffle index set from storage tarot:shuffle indices[0]','function tarot:stack/append_instance with storage tarot:shuffle','data remove storage tarot:shuffle indices[0]','function tarot:stack/assemble'])
    w('stack/append_instance',['$data modify storage tarot:runtime cards append from storage tarot:shuffle_source cards[$(index)]'])
    w('stack/random',['$execute store result score #j tarot.j run random value 0..$(max)'])
    w('sound/card',['execute at @s run playsound minecraft:item.book.page_turn player @a[distance=..6] ~ ~ ~ 0.18 1.15'])
    w('sound/shuffle',['execute at @s run playsound minecraft:item.book.page_turn player @a[distance=..6] ~ ~ ~ 0.26 0.85'])
