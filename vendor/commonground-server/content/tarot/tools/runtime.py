"""Vanilla controls for ordered card stacks and supported surface handling."""
import json,re
from pathlib import Path
from profiles import profile,model_components,stack_model_components

CARD_ITEM = 'minecraft:carrot_on_a_stick'
CARD_CARRIERS = ('minecraft:paper', CARD_ITEM)

def _write(out,rel,lines):
    path=Path(out)/'data/tarot/function'/(rel+'.mcfunction');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(('\n'.join(lines) if isinstance(lines,list) else lines)+'\n',encoding='utf-8')

def printed_item(card,target):
    name={'text':card['name']}
    modern=profile(target)['text_objects'];hint={'text':'Use: place face-down','color':'gray','italic':False}
    return {'id':CARD_ITEM,'count':1,'components':{'!minecraft:max_damage':{},'minecraft:unbreakable':{} if modern else {'show_in_tooltip':False},**({'minecraft:tooltip_display':{'hidden_components':['minecraft:unbreakable']}} if modern else {}),**model_components(card,target),'minecraft:custom_data':{'tarot':{'kind':'card','key':card['key'],'module':card['module']}},'minecraft:custom_name':name if modern else json.dumps(name,ensure_ascii=False),'minecraft:lore':[hint if modern else json.dumps(hint)]}}

def generate(out,cards,modules,target,registry=None,identities=None):
    if registry is None or identities is None:
        from module_registry import load
        registry,identities=load()
    out=Path(out);spec=profile(target);groups={m:[] for m in modules};seen=set()
    offhand=spec['offhand_components'].removesuffix('.components')
    if not groups or len(groups)!=len(modules):raise ValueError('Duplicate or empty modules')
    for c in cards:
        if not re.fullmatch(r'[a-z0-9_.-]+/[a-z0-9_.-]+',c['key']) or c['key'] in seen or c['module'] not in groups:raise ValueError('Invalid card identity')
        seen.add(c['key']);groups[c['module']].append(c)
    if any(not group for group in groups.values()):raise ValueError('Empty module')
    w=lambda rel,lines:_write(out,rel,lines)
    w('load',['execute unless data storage tarot:config {schema:6} run function tarot:setup','data remove storage tarot:inputs pending','tag @a remove tarot.waiting','scoreboard players set @a tarot.pending 0','function tarot:catalogue/load'])
    w('catalogue/load',[
        'scoreboard players set #catalogue_ready tarot.sys 0','data modify storage tarot:catalogue factories set value {}',
        *['data modify storage tarot:catalogue factories.'+json.dumps(c['key'])+' set value '+json.dumps(printed_item(c,target),ensure_ascii=False,separators=(',',':')) for c in cards],
        'scoreboard players set #catalogue_ready tarot.sys 1',
    ])
    w('setup',['scoreboard objectives add tarot.use minecraft.used:minecraft.carrot_on_a_stick','scoreboard objectives add tarot.action trigger',*['scoreboard objectives add '+name+' dummy' for name in ['tarot.roll','tarot.i','tarot.j','tarot.sys','tarot.cool','tarot.pending','tarot.id','tarot.face']],'scoreboard players add #next_id tarot.sys 0','scoreboard players add #cursor tarot.sys 0','data modify storage tarot:config schema set value 6','scoreboard players enable @a tarot.action'])
    w('admission',['scoreboard players set #permit tarot.sys 0',f'execute store result score #budget tarot.sys run gamerule {spec["command_rule"]}','execute if score #budget tarot.sys matches 65536.. run scoreboard players set #permit tarot.sys 1','execute unless score #permit tarot.sys matches 1 run scoreboard players set @s tarot.cool 20','execute unless score #permit tarot.sys matches 1 run title @s actionbar {"text":"Card handling is paused: the server command budget is below 65536. Nothing was changed.","color":"gray"}'])
    from queue_runtime import generate as queues
    queues(w,spec['command_rule'])
    # Resolve modifiers BEFORE the work queue. Service never reinterprets a
    # released Shift key or applies an old click to a newly selected deck.
    w('input/trigger',['scoreboard players operation @s tarot.pending = @s tarot.action','function tarot:input/capture'])
    w('input/use',[
        'scoreboard players set @s tarot.pending 0',
        'execute if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:custom_data~{tarot:{kind:"deck"}}] run scoreboard players set @s tarot.pending 1',
        'execute if score @s tarot.pending matches 1 if predicate tarot:is_sneaking run scoreboard players set @s tarot.pending 2',
        'execute if score @s tarot.pending matches 2 if items entity @s weapon.offhand #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set @s tarot.pending 3',
        'execute if items entity @s weapon.mainhand #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set @s tarot.pending 4',
        'execute unless score @s tarot.pending matches 1..4 run scoreboard players set @s tarot.use 0',
        'execute unless score @s tarot.pending matches 1..4 run return 0',
        'scoreboard players set #mounted_pig tarot.sys 0',
        'execute on vehicle if entity @s[type=minecraft:pig] run scoreboard players set #mounted_pig tarot.sys 1',
        'execute if score #mounted_pig tarot.sys matches 1 run return run function tarot:input/physical_busy',
        'execute if items entity @s weapon.offhand * unless items entity @s weapon.offhand #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] unless items entity @s weapon.offhand minecraft:carrot_on_a_stick[minecraft:custom_data~{tarot:{kind:"deck"}}] run return run function tarot:input/physical_busy',
        'function tarot:input/capture',
    ])
    w('input/physical_busy',[
        'scoreboard players set @s tarot.use 0',
        # An explicit trigger remains available with any offhand or mount. Do
        # not discard that command when a physical use happened in the same tick.
        'scoreboard players set @s tarot.cool 0',
        'execute if score #mounted_pig tarot.sys matches 1 run title @s actionbar {"text":"While riding a pig, use /trigger tarot.action.","color":"gray"}',
        'execute unless score #mounted_pig tarot.sys matches 1 run title @s actionbar {"text":"Clear your offhand, or use /trigger tarot.action.","color":"gray"}',
    ])
    w('input/capture',[
        'scoreboard players set @s tarot.use 0','scoreboard players set @s tarot.action 0',
        'execute unless score @s tarot.pending matches 1..4 run return 0',
        'data modify storage tarot:inputs fresh set value {main:{},offhand:{}}',
        'data modify storage tarot:inputs fresh.main set from entity @s SelectedItem',
        f'data modify storage tarot:inputs fresh.offhand set from entity @s {offhand}',
        'execute store result storage tarot:inputs context.id int 1 run scoreboard players get @s tarot.id',
        'function tarot:input/save with storage tarot:inputs context','tag @s add tarot.waiting',
    ])
    w('input/save',['$data modify storage tarot:inputs pending.p$(id) set from storage tarot:inputs fresh'])
    w('input/serve',[
        'execute store result storage tarot:inputs context.id int 1 run scoreboard players get @s tarot.id',
        'function tarot:input/dispatch with storage tarot:inputs context',
    ])
    w('input/dispatch',[
        'tag @s remove tarot.waiting',
        '$execute unless data storage tarot:inputs pending.p$(id) run return 0',
        'data modify storage tarot:inputs current set value {main:{},offhand:{}}',
        'data modify storage tarot:inputs current.main set from entity @s SelectedItem',
        f'data modify storage tarot:inputs current.offhand set from entity @s {offhand}',
        '$execute store success score #main_changed tarot.sys run data modify storage tarot:inputs current.main set from storage tarot:inputs pending.p$(id).main',
        '$execute store success score #off_changed tarot.sys run data modify storage tarot:inputs current.offhand set from storage tarot:inputs pending.p$(id).offhand',
        '$data remove storage tarot:inputs pending.p$(id)',
        'execute if score #main_changed tarot.sys matches 1 run return run function tarot:input/cancel',
        'execute if score @s tarot.pending matches 3 if score #off_changed tarot.sys matches 1 run return run function tarot:input/cancel',
        *[f'execute if score @s tarot.pending matches {n} run return run function tarot:input/{action}' for n,action in [(1,'draw'),(2,'shuffle'),(3,'return'),(4,'place')]],
    ])
    w('input/cancel',['scoreboard players set @s tarot.pending 0','title @s actionbar {"text":"Your cards changed. Use again when ready.","color":"gray"}'])
    # Prune disconnected requests periodically, without copying every queued
    # 128-card item on every tick or retaining abandoned player inventories.
    w('input/prune',['data modify storage tarot:inputs kept set value {}','execute as @a run function tarot:input/retain','data modify storage tarot:inputs pending set from storage tarot:inputs kept','data remove storage tarot:inputs kept','scoreboard players set #input_gc tarot.sys 0'])
    w('input/retain',['execute store result storage tarot:inputs context.id int 1 run scoreboard players get @s tarot.id','function tarot:input/retain_id with storage tarot:inputs context'])
    w('input/retain_id',['$execute if data storage tarot:inputs pending.p$(id) run data modify storage tarot:inputs kept.p$(id) set from storage tarot:inputs pending.p$(id)'])
    # Explicit handling is the upgrade boundary. Never sweep ordinary paper,
    # containers or inventories, and never replace a player's name/lore/notes.
    for path,label in [('chosen.item','chosen'),('entry','entry'),('prepared','band')]:
        w('card/upgrade_'+label,[
            'scoreboard players set #carrier_safe tarot.sys 0',
            f'execute unless data storage tarot:runtime {path}{{id:"minecraft:paper"}} unless data storage tarot:runtime {path}{{id:"{CARD_ITEM}"}} run return 0',
            f'execute if data storage tarot:runtime {path}.components."minecraft:max_damage" if data storage tarot:runtime {path}.components."minecraft:custom_data".tarot.carrier_max_damage run title @s actionbar '+json.dumps({'text':'This item already has carrier history. Nothing was changed.','color':'gray'}),
            f'execute if data storage tarot:runtime {path}.components."minecraft:max_damage" if data storage tarot:runtime {path}.components."minecraft:custom_data".tarot.carrier_max_damage run return 0',
            f'execute if data storage tarot:runtime {path}.components."minecraft:max_damage" run data modify storage tarot:runtime {path}.components."minecraft:custom_data".tarot.carrier_max_damage set from storage tarot:runtime {path}.components."minecraft:max_damage"',
            f'data remove storage tarot:runtime {path}.components."minecraft:max_damage"',
            f'data modify storage tarot:runtime {path}.components."!minecraft:max_damage" set value {{}}',
            f'data modify storage tarot:runtime {path}.id set value "{CARD_ITEM}"',
            *[f'execute if data storage tarot:runtime {path}.components{{"minecraft:max_stack_size":{value}}} run data remove storage tarot:runtime {path}.components."minecraft:max_stack_size"' for value in ['1','1b']],
            f'execute unless data storage tarot:runtime {path}.components."minecraft:unbreakable" run data modify storage tarot:runtime {path}.components."minecraft:unbreakable" set value '+('{}' if spec['text_objects'] else '{show_in_tooltip:0b}'),
            'scoreboard players set #carrier_safe tarot.sys 1',
        ])
    for action in ['draw','shuffle','return','place']:
        body=['execute if score @s tarot.cool matches 1.. run return 0','function tarot:admission','execute unless score #permit tarot.sys matches 1 run return 0','scoreboard players set @s tarot.cool 2']
        if action=='place':body+=['function tarot:table/place']
        else:body += [f'execute if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:count=1,minecraft:custom_data~{{tarot:{{kind:"deck",module:"{m}"}}}}] run return run function tarot:checked/{action}/{m}' for m in modules]+['title @s actionbar {"text":"Hold a card stack in your main hand.","color":"gray"}']
        w('input/'+action,body);w(action,['function tarot:input/'+action])
    for module,group in groups.items():
        deck={'minecraft:max_stack_size':1,'minecraft:unbreakable':{} if spec['text_objects'] else {'show_in_tooltip':False},**stack_model_components(module,len(group),target,identities),'minecraft:custom_data':{'tarot':{'kind':'deck','module':module,'storage':'native-v1'}},'minecraft:charged_projectiles':[printed_item(c,target) for c in group],**({'minecraft:tooltip_display':{'hidden_components':['minecraft:charged_projectiles','minecraft:unbreakable']}} if spec['text_objects'] else {'minecraft:hide_additional_tooltip':{}}),'minecraft:custom_name':{'text':group[0].get('deck_name',module.title()+' Deck')},'minecraft:lore':[{'text':'Use: take the top card','color':'gray','italic':False},{'text':'Sneak-use: shuffle; with a card offhand: put it on top','color':'gray','italic':False},{'text':'Card in hand: use to place face-down','color':'dark_gray','italic':False},{'text':'Clear offhand for use; mounted: use /trigger tarot.action','color':'dark_gray','italic':False}]}
        deck['!minecraft:max_damage']={}
        if not spec['text_objects']:
            deck['minecraft:custom_name']=json.dumps(deck['minecraft:custom_name'],ensure_ascii=False);deck['minecraft:lore']=[json.dumps(v,ensure_ascii=False) for v in deck['minecraft:lore']]
        # JSON component patches support removals even on hosts whose /give
        # parser predates !component command syntax. Keep acquisition native.
        modifier={'type' if target=='26.3' else 'function':'minecraft:set_components','components':deck}
        entry={'type':'minecraft:item','name':CARD_ITEM,**({'modifier':modifier} if target=='26.3' else {'functions':[modifier]})}
        grant={'type':'minecraft:generic','pools':[{'rolls':1,'entries':[entry]}]}
        path=out/f'data/tarot/loot_table/decks/{module}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(grant,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        w('give/'+module,['loot give @s loot tarot:decks/'+module])
        recipe={'type':'minecraft:crafting_shaped','pattern':['###','#X#','###'],'key':{'#':{'item':'minecraft:paper'},'X':{'item':registry[module]['ingredient']}},'result':{'id':'minecraft:carrot_on_a_stick','count':1,'components':deck}}
        if not spec['object_ingredients']:recipe['key']={k:v['item'] for k,v in recipe['key'].items()}
        path=out/f'data/tarot/recipe/{module}_deck.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        # A normal, hidden recipe advancement: no login grants, custom toast or chat.
        advancement={'criteria':{'ingredients':{'trigger':'minecraft:inventory_changed','conditions':{'items':[{'items':['minecraft:paper']},{'items':[registry[module]['ingredient']]}]}}},'rewards':{'recipes':[f'tarot:{module}_deck']}}
        path=out/f'data/tarot/advancement/recipes/{module}_deck.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(advancement,indent=2)+'\n',encoding='utf-8')
        for action in ['draw','shuffle','return']:
            w(f'checked/{action}/{module}',['function tarot:stack/validate','execute unless score #valid tarot.sys matches 1 run title @s actionbar {"text":"This stack has invalid contents. Nothing was changed.","color":"gray"}','execute unless score #valid tarot.sys matches 1 run return 0','function tarot:stack/'+action])
            w(action+'/'+module,['function tarot:stack/'+action])
        w('validate/'+module,['function tarot:stack/validate'])
    from stack_runtime import generate as stacks
    from table_runtime import generate as tables
    stacks(out,cards,modules,target,w,printed_item,identities)
    from native_stack_runtime import generate as native_stacks
    native_stacks(out,cards,modules,target,w,printed_item)
    # Legacy rows have already passed exact known-key validation. A catalogue
    # lookup avoids scanning every printed identity for each individual card.
    w('stack/legacy',['execute unless score #catalogue_ready tarot.sys matches 1 run function tarot:catalogue/load','function tarot:stack/legacy_lookup with storage tarot:runtime chosen'])
    w('stack/legacy_lookup',['$data modify storage tarot:runtime chosen.item set from storage tarot:catalogue factories."$(key)"'])
    tables(out,cards,modules,target,w)
    w('help',['tellraw @s {"text":"Stack in hand: use to draw top; sneak-use to shuffle, or put the offhand card on top. Card in hand: use to place face-down. Sneak-use avoids opening a workstation. On a placed card: use to turn over; sneak-use to rotate; hit to pick up. /trigger tarot.action set 1 draw, 2 shuffle, 3 put on top, 4 place. Keep the offhand clear except for returns. Vanilla blocks, usable offhand items and ridden pigs can take priority; the trigger controls work reliably in those cases. Older paper cards also work with a band offhand or trigger 4.","color":"gray"}'])
    path=out/'data/tarot/tags/item/card_carriers.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'values':list(CARD_CARRIERS)},indent=2)+'\n',encoding='utf-8')
    tags=out/'data/minecraft/tags/function';tags.mkdir(parents=True,exist_ok=True)
    (tags/'load.json').write_text('{"values":["tarot:load"]}\n');(tags/'tick.json').write_text('{"values":["tarot:tick"]}\n')
    predicate=out/'data/tarot/predicate/is_sneaking.json';predicate.parent.mkdir(parents=True,exist_ok=True)
    value={'condition':'minecraft:entity_properties','entity':'this','predicate':{'flags':{'is_sneaking':True}}}
    if target=='26.3':value['type']=value.pop('condition');value['predicate']={'minecraft:flags':{'is_sneaking':True}}
    predicate.write_text(json.dumps(value,indent=2)+'\n')
