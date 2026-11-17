"""Real ordered nested ItemStacks let vanilla's DataFixer own cross-version upgrades."""
import json
from profiles import profile
from stack_runtime import CAPACITY,SLOTS
from runtime import CARD_CARRIERS

COMPONENT='minecraft:charged_projectiles'

def generate(out,cards,modules,target,w,printed_item):
    spec=profile(target);old_equipment=spec['offhand_components'].startswith('Inventory')
    head='ArmorItems[3]' if old_equipment else 'equipment.head'
    hand='HandItems[0]' if old_equipment else 'equipment.mainhand'
    backup='HandItems[1]' if old_equipment else 'equipment.offhand'
    offhand=spec['offhand_components'].removesuffix('.components')
    old=(out/'data/tarot/function/stack/validate.mcfunction').read_text()
    w('stack/validate_opaque',old.rstrip())
    w('stack/validate',[
        'scoreboard players set #valid tarot.sys 0','scoreboard players set #promoted tarot.sys 0',
        'scoreboard players set #deliver tarot.sys 0','scoreboard players set #consume tarot.sys 0',
        'execute unless items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:count=1] run return 0',
        'execute if data entity @s SelectedItem.components."minecraft:custom_data".tarot{storage:"native-v1"} run return run function tarot:native/validate',
        'execute if data entity @s SelectedItem.components."minecraft:custom_data".tarot.storage run return 0',
        'execute if data entity @s SelectedItem.components."minecraft:charged_projectiles"[0] run return 0',
        'function tarot:stack/validate_opaque',
        'execute unless score #valid tarot.sys matches 1 run return 0',
        'function tarot:native/promote',
    ])
    validation=[
        'execute if data entity @s SelectedItem.components."minecraft:custom_data".tarot.cards run return 0',
        'data modify storage tarot:runtime cards set value []',
        f'data modify storage tarot:runtime cards set from entity @s SelectedItem.components."{COMPONENT}"',
        'execute store result score #size tarot.roll run data get storage tarot:runtime cards',
        f'execute unless score #size tarot.roll matches 0..{CAPACITY} run return 0',
        'data modify storage tarot:validation unchecked set from storage tarot:runtime cards',
    ]
    for c in cards:
        for carrier in CARD_CARRIERS:
            pattern={'id':carrier,'count':1,'components':{'minecraft:custom_data':{'tarot':{'kind':'card','key':c['key'],'module':c['module']}}}}
            encoded=json.dumps(pattern,separators=(',',':'))
            validation += ['data remove storage tarot:validation unchecked['+encoded+']','data remove storage tarot:validation unchecked['+encoded.replace('"count":1','"count":1b')+']']
    if spec.get('implicit_nested_count'):
        # The native ItemStackTemplate omits default count=1. Reject every remaining
        # explicit count BEFORE matching recognized rows without that field.
        validation += ['execute if data storage tarot:validation unchecked[].count run return 0']
        for c in cards:
            for carrier in CARD_CARRIERS:
                pattern={'id':carrier,'components':{'minecraft:custom_data':{'tarot':{'kind':'card','key':c['key'],'module':c['module']}}}}
                validation += ['data remove storage tarot:validation unchecked['+json.dumps(pattern,separators=(',',':'))+']']
    w('native/validate',validation+['execute if data storage tarot:validation {unchecked:[]} run scoreboard players set #valid tarot.sys 1'])
    w('native/promote',[
        'data modify storage tarot:legacy source set from storage tarot:runtime cards',
        'data modify storage tarot:runtime cards set value []','data modify storage tarot:legacy metadata set value []',
        'function tarot:native/promote_loop','scoreboard players set #promoted tarot.sys 1',
    ])
    w('native/promote_loop',[
        'execute unless data storage tarot:legacy source[0] run return 0',
        'data modify storage tarot:runtime chosen set from storage tarot:legacy source[0]',
        'execute unless data storage tarot:runtime chosen.item run function tarot:stack/legacy',
        'data modify storage tarot:runtime cards append from storage tarot:runtime chosen.item',
        # Retain any legacy row/item-level metadata without duplicating the component payload.
        'data remove storage tarot:runtime chosen.item.components',
        'data modify storage tarot:legacy metadata append from storage tarot:runtime chosen',
        'data remove storage tarot:legacy source[0]','function tarot:native/promote_loop',
    ])
    # Reserve a real empty inventory slot, without handing anything over yet.
    w('native/reserve',['scoreboard players set #room tarot.sys 0',
        *[f'execute unless items entity @s {slot} * run return run function tarot:native/reserve_{i}' for i,slot in enumerate(SLOTS)],
        'title @s actionbar {"text":"Make room in your inventory first.","color":"gray"}'])
    for i,slot in enumerate(SLOTS):w('native/reserve_'+str(i),[f'data modify storage tarot:runtime slot set value "{slot}"','scoreboard players set #room tarot.sys 1'])
    w('stack/draw',[
        'execute unless data storage tarot:runtime cards[0] run title @s actionbar {"text":"The band is empty. Put a card on top.","color":"gray"}',
        'execute unless data storage tarot:runtime cards[0] run return 0','function tarot:native/reserve',
        'execute unless score #room tarot.sys matches 1 run return 0',
        'data modify storage tarot:runtime chosen set value {}','data modify storage tarot:runtime chosen.item set from storage tarot:runtime cards[0]',
        'function tarot:card/upgrade_chosen',
        'execute unless score #carrier_safe tarot.sys matches 1 run return 0',
        'data remove storage tarot:runtime cards[0]','scoreboard players set #deliver tarot.sys 1',
        'function tarot:stack/sync','execute if score #committed tarot.sys matches 1 run function tarot:sound/card',
    ])
    w('stack/insert',[
        f'data modify storage tarot:runtime entry set from entity @s {offhand}','data remove storage tarot:runtime entry.Slot',
        'function tarot:card/upgrade_entry',
        'execute unless score #carrier_safe tarot.sys matches 1 run return 0',
        'data modify storage tarot:runtime cards prepend from storage tarot:runtime entry','scoreboard players set #consume tarot.sys 1',
        'function tarot:stack/sync','execute if score #committed tarot.sys matches 1 run function tarot:sound/card',
    ])
    # Current stack/return already verifies the live singleton's key/module before calling insert.
    w('stack/sync',[
        'scoreboard players set #committed tarot.sys 0','data modify storage tarot:runtime prepared set from entity @s SelectedItem',
        'function tarot:card/upgrade_band','execute unless score #carrier_safe tarot.sys matches 1 run return 0',
        f'data modify storage tarot:runtime prepared.components."{COMPONENT}" set from storage tarot:runtime cards',
        'data modify storage tarot:runtime prepared.components."minecraft:custom_data".tarot.storage set value "native-v1"',
        'execute if score #promoted tarot.sys matches 1 if data storage tarot:runtime prepared.components."minecraft:custom_data".tarot.migration_history run title @s actionbar {"text":"This stack already has migration notes. Nothing was changed.","color":"gray"}',
        'execute if score #promoted tarot.sys matches 1 if data storage tarot:runtime prepared.components."minecraft:custom_data".tarot.migration_history run return 0',
        'execute if score #promoted tarot.sys matches 1 run data modify storage tarot:runtime prepared.components."minecraft:custom_data".tarot.migration_history set value {from:"opaque-v1"}',
        'execute if score #promoted tarot.sys matches 1 run data modify storage tarot:runtime prepared.components."minecraft:custom_data".tarot.migration_history.rows set from storage tarot:legacy metadata',
        'data remove storage tarot:runtime prepared.components."minecraft:custom_data".tarot.cards',
        'execute store result score #size tarot.roll run data get storage tarot:runtime cards',
        'tag @a remove tarot.actor','tag @s add tarot.actor',
        'execute positioned ~ ~-128 ~ summon minecraft:armor_stand run function tarot:native/stage','tag @s remove tarot.actor',
        'execute if score #committed tarot.sys matches 1 run function tarot:stack/appearance',
        'execute unless score #committed tarot.sys matches 1 run title @s actionbar {"text":"This stack could not be preserved exactly. Nothing was changed.","color":"gray"}',
    ])
    stage=[
        'data merge entity @s {Tags:["tarot.transfer"],Invisible:1b,Marker:1b,NoGravity:1b,Silent:1b,Invulnerable:1b}',
        *(['data modify entity @s ArmorItems set value [{},{},{},{}]','data modify entity @s HandItems set value [{},{}]'] if old_equipment else ['data modify entity @s equipment set value {}']),
        'scoreboard players set #ready tarot.sys 1',
        f'data modify entity @s {head} set from storage tarot:runtime prepared',
        'execute unless items entity @s armor.head minecraft:carrot_on_a_stick[minecraft:count=1,minecraft:custom_data~{tarot:{storage:"native-v1"}}] run scoreboard players set #ready tarot.sys 0',
        'item modify entity @s armor.head tarot:native_hide',
        'data modify storage tarot:decoded cards set value []',
        f'data modify storage tarot:decoded cards set from entity @s {head}.components."{COMPONENT}"',
        'execute store result score #decoded tarot.sys run data get storage tarot:decoded cards',
        'execute unless score #decoded tarot.sys = #size tarot.roll run scoreboard players set #ready tarot.sys 0',
        'execute if score #promoted tarot.sys matches 0 if score #consume tarot.sys matches 0 run function tarot:native/verify_array',
    ]
    for i in range(CAPACITY):
        stage += [f'execute if score #promoted tarot.sys matches 1 if score #size tarot.roll matches {i+1}.. run function tarot:native/codec_{i}',f'execute if score #promoted tarot.sys matches 0 if score #consume tarot.sys matches 1 if score #size tarot.roll matches {i+1}.. run function tarot:native/codec_{i}']
        body=[f'data modify storage tarot:decoded compare set from storage tarot:runtime cards[{i}].components',
              f'data modify storage tarot:decoded current set from storage tarot:decoded cards[{i}].components',
              'execute if score #promoted tarot.sys matches 1 run function tarot:native/normalize_factory',
              'function tarot:native/normalize_defaults',
              'execute store success score #different tarot.sys run data modify storage tarot:decoded compare set from storage tarot:decoded current',
              'execute if score #different tarot.sys matches 1 run scoreboard players set #ready tarot.sys 0']
        w('native/codec_'+str(i),body)
    stage += [
        f'execute if score #deliver tarot.sys matches 1 run data modify entity @s {hand} set from storage tarot:runtime chosen.item',
        'execute if score #deliver tarot.sys matches 1 unless items entity @s weapon.mainhand #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set #ready tarot.sys 0',
        'execute if score #deliver tarot.sys matches 1 run function tarot:native/verify_delivery',
        f'execute if score #ready tarot.sys matches 1 run item replace entity @s weapon.offhand from entity @a[tag=tarot.actor,limit=1] weapon.mainhand',
        'execute if score #ready tarot.sys matches 1 store success score #committed tarot.sys run item replace entity @a[tag=tarot.actor,limit=1] weapon.mainhand from entity @s armor.head',
        'execute if score #committed tarot.sys matches 1 if score #deliver tarot.sys matches 1 run function tarot:native/deliver with storage tarot:runtime',
        'execute if score #committed tarot.sys matches 1 if score #consume tarot.sys matches 1 run item replace entity @a[tag=tarot.actor,limit=1] weapon.offhand with minecraft:air',
        'item replace entity @s armor.head with minecraft:air','item replace entity @s weapon.mainhand with minecraft:air','item replace entity @s weapon.offhand with minecraft:air','kill @s',
    ]
    w('native/stage',stage)
    # Draw/shuffle use values already serialized by this host's native component codec.
    # A single exact array comparison is stricter and cheaper than decoding each payload
    # independently. Returns/opaque promotion retain per-item normalization checks:
    # on26.3 a returned live ItemStack has count1, while ItemStackTemplate omits it.
    w('native/verify_array',[
        'data modify storage tarot:decoded compare_cards set from storage tarot:runtime cards',
        'execute store success score #different tarot.sys run data modify storage tarot:decoded compare_cards set from storage tarot:decoded cards',
        'execute if score #different tarot.sys matches 1 run scoreboard players set #ready tarot.sys 0',
    ])
    w('native/verify_delivery',[
        'data modify storage tarot:decoded compare set from storage tarot:runtime chosen.item.components',
        f'data modify storage tarot:decoded current set from entity @s {hand}.components',
        'execute if score #promoted tarot.sys matches 1 run function tarot:native/normalize_factory',
        'function tarot:native/normalize_defaults',
        'execute store success score #different tarot.sys run data modify storage tarot:decoded compare set from storage tarot:decoded current',
        'execute if score #different tarot.sys matches 1 run scoreboard players set #ready tarot.sys 0',
    ])
    w('native/deliver',[
        '$execute store success score #delivered tarot.sys run item replace entity @a[tag=tarot.actor,limit=1] $(slot) from entity @s weapon.mainhand',
        'execute unless score #delivered tarot.sys matches 1 run item replace entity @a[tag=tarot.actor,limit=1] weapon.mainhand from entity @s weapon.offhand',
        'execute unless score #delivered tarot.sys matches 1 run scoreboard players set #committed tarot.sys 0',
    ])
    normalize=['execute if data storage tarot:decoded compare{"minecraft:max_stack_size":1b} run data modify storage tarot:decoded compare."minecraft:max_stack_size" set value 1']
    if spec['text_objects']:normalize += ['execute store result score #name_fields tarot.sys run data get storage tarot:decoded compare."minecraft:custom_name"']
    normalize += [('execute if score #name_fields tarot.sys matches 1 ' if spec['text_objects'] else 'execute ')+'if data storage tarot:decoded compare."minecraft:custom_data".tarot.key run function tarot:native/normalize_factory_name with storage tarot:decoded compare."minecraft:custom_data".tarot']
    w('native/normalize_factory_name',[
        'execute unless score #catalogue_ready tarot.sys matches 1 run function tarot:catalogue/load',
        '$data modify storage tarot:decoded factory_name set from storage tarot:catalogue factories."$(key)".components."minecraft:custom_name"',
        'execute store success score #factory_name_changed tarot.sys run data modify storage tarot:decoded factory_name set from storage tarot:decoded compare."minecraft:custom_name"',
        'execute if score #factory_name_changed tarot.sys matches 0 run data modify storage tarot:decoded compare."minecraft:custom_name" set from storage tarot:decoded current."minecraft:custom_name"',
    ])
    # Only freshly manufactured legacy rows reach this normalizer. Accept the
    # engine's canonical text encoding of our exact single-line factory hint.
    hint=printed_item(cards[0],target)['components']['minecraft:lore']
    normalize += ['execute store result score #lore_lines tarot.sys run data get storage tarot:decoded compare."minecraft:lore"',
                  'execute if score #lore_lines tarot.sys matches 1 if data storage tarot:decoded compare'+json.dumps({'minecraft:lore':hint},ensure_ascii=False,separators=(',',':'))+' run data modify storage tarot:decoded compare."minecraft:lore" set from storage tarot:decoded current."minecraft:lore"']
    w('native/normalize_factory',normalize)
    # A typed template can retain an explicit prototype default that the live
    # ItemStack codec omits. Accept ONLY exact known defaults when absent from
    # the decoded item. Empty-compound NBT predicates are partial matches, so
    # equality here deliberately uses /data's exact replacement result instead.
    defaults={'minecraft:repair_cost':0,'minecraft:damage':0,'minecraft:lore':[],
              'minecraft:rarity':'common','minecraft:enchantments':{} if spec['text_objects'] else {'levels':{}},
              'minecraft:attribute_modifiers':[] if spec['text_objects'] else {'modifiers':[]}}
    w('native/normalize_defaults',[
        f'execute if data storage tarot:decoded compare."{component}" unless data storage tarot:decoded current."{component}" run function tarot:native/default_{i}' for i,component in enumerate(defaults)
    ])
    for i,(component,value) in enumerate(defaults.items()):
        w('native/default_'+str(i),[
            f'data modify storage tarot:decoded implicit set from storage tarot:decoded compare."{component}"',
            'execute store success score #default_changed tarot.sys run data modify storage tarot:decoded implicit set value '+json.dumps(value,separators=(',',':')),
            f'execute if score #default_changed tarot.sys matches 0 run data remove storage tarot:decoded compare."{component}"',
        ])
    modifier={'function':'minecraft:toggle_tooltips','toggles':{COMPONENT:False}} if spec['text_objects'] else {'function':'minecraft:set_components','components':{'minecraft:hide_additional_tooltip':{}}}
    if target=='26.3':modifier['type']=modifier.pop('function')
    path=out/'data/tarot/item_modifier/native_hide.json';path.write_text(json.dumps(modifier,indent=2)+'\n')
    # Reuse integer Fisher–Yates; its rows are now actual native items, not opaque wrappers.
    w('stack/appearance',[
        *[f'execute if score #size tarot.roll matches 0 if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:custom_data~{{tarot:{{module:"{m}"}}}}] run return run function tarot:stack/appearance/{m}' for m in modules],
        'data modify storage tarot:runtime top set from storage tarot:runtime cards[0].components."minecraft:custom_data".tarot',
        *[f'execute if data storage tarot:runtime top{{key:{json.dumps(c["key"])}}} run return run function tarot:stack/appearance/{c["module"]}' for c in cards],
    ])
