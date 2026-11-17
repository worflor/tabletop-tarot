"""One placed card owns its item; its mounted hitbox addresses that exact card."""
import json
from profiles import profile

def generate(out,cards,modules,target,w):
    def tag(name,values):
        p=out/f'data/tarot/tags/block/{name}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'values':values},indent=2)+'\n')
    tag('clear',['minecraft:air','minecraft:cave_air','minecraft:void_air'])
    tag('table_surface',['#minecraft:planks','#minecraft:logs','#minecraft:wool',*['minecraft:'+v for v in ['stone','cobblestone','mossy_cobblestone','smooth_stone','stone_bricks','mossy_stone_bricks','deepslate','cobbled_deepslate','polished_deepslate','deepslate_bricks','deepslate_tiles','granite','polished_granite','andesite','polished_andesite','diorite','polished_diorite','bricks','sandstone','smooth_sandstone','cut_sandstone','red_sandstone','smooth_red_sandstone','cut_red_sandstone','quartz_block','smooth_quartz','glass','tinted_glass','ice','packed_ice','blue_ice','bedrock','iron_block','gold_block','diamond_block','emerald_block','netherite_block','lapis_block','redstone_block','coal_block','crafting_table','smithing_table','fletching_table','cartography_table','loom','barrel']]])
    w('table/place',[
        'scoreboard players set #paper tarot.sys 0',
        *['execute if items entity @s weapon.mainhand #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~'+json.dumps({'tarot':{'kind':'card','key':c['key'],'module':c['module']}},separators=(',',':'))+'] run scoreboard players set #paper tarot.sys 1' for c in cards],
        'execute unless score #paper tarot.sys matches 1 run title @s actionbar {"text":"Hold one card in your main hand to place it.","color":"gray"}',
        'execute unless score #paper tarot.sys matches 1 run return 0',
        'data modify storage tarot:runtime chosen set value {}','data modify storage tarot:runtime chosen.item set from entity @s SelectedItem',
        'function tarot:card/upgrade_chosen',
        'execute unless score #carrier_safe tarot.sys matches 1 run return 0',
        'scoreboard players set #placed tarot.sys 0','scoreboard players set #ray tarot.sys 45',
        'execute anchored eyes positioned ^ ^ ^ anchored feet run function tarot:table/trace',
        'execute if score #placed tarot.sys matches 0 run title @s actionbar {"text":"Aim at a clear tabletop or slab within reach.","color":"gray"}',
    ])
    w('table/trace',[
        'execute if block ~ ~ ~ #tarot:clear run return run function tarot:table/step',
        'execute if block ~ ~ ~ #minecraft:slabs[type=bottom] run return run function tarot:table/slab',
        'function tarot:table/hit',
    ])
    w('table/step',[
        'scoreboard players remove #ray tarot.sys 1','execute if score #ray tarot.sys matches 1.. positioned ^ ^ ^0.1 run function tarot:table/trace',
    ])
    # Block tags describe a whole cell. Measure the ray's actual fractional Y
    # before deciding whether a bottom slab was hit or passed above.
    w('table/slab',[
        'execute summon minecraft:marker run function tarot:table/height',
        'execute if score #fraction tarot.sys matches 5000.. run return run function tarot:table/step',
        'function tarot:table/hit',
    ])
    w('table/height',[
        'execute store result score #ray_y tarot.sys run data get entity @s Pos[1] 10000',
        'execute align y run tp @s ~ ~ ~',
        'execute store result score #floor_y tarot.sys run data get entity @s Pos[1] 10000',
        'scoreboard players operation #fraction tarot.sys = #ray_y tarot.sys',
        'scoreboard players operation #fraction tarot.sys -= #floor_y tarot.sys','kill @s',
    ])
    for label,score in [('previous','previous_y'),('plane','plane_y')]:
        w('table/'+label,[f'execute store result score #{score} tarot.sys run data get entity @s Pos[1] 10000','kill @s'])
    w('table/hit',[
        'execute positioned ^ ^ ^-0.1 summon minecraft:marker run function tarot:table/previous',
        'scoreboard players set #half tarot.sys 0',
        'execute if block ~ ~ ~ #tarot:table_surface align y positioned ~ ~1.021 ~ run return run function tarot:table/surface',
        'execute if block ~ ~ ~ #minecraft:slabs[type=top] align y positioned ~ ~1.021 ~ run return run function tarot:table/surface',
        'execute if block ~ ~ ~ #minecraft:slabs[type=double] align y positioned ~ ~1.021 ~ run return run function tarot:table/surface',
        'scoreboard players set #half tarot.sys 1',
        'execute if block ~ ~ ~ #minecraft:slabs[type=bottom] align y positioned ~ ~0.521 ~ run function tarot:table/surface',
    ])
    w('table/surface',[
        'execute summon minecraft:marker run function tarot:table/plane',
        'scoreboard players remove #plane_y tarot.sys 210',
        'execute if score #previous_y tarot.sys < #plane_y tarot.sys run return 0',
        'execute unless block ~ ~ ~ #tarot:clear unless block ~ ~ ~ #minecraft:slabs[type=bottom] run return 0',
        'execute if entity @e[type=minecraft:item_display,tag=tarot.placed,distance=..0.6] run return run function tarot:table/space',
        'tag @a remove tarot.actor','tag @s add tarot.actor',
        'execute summon minecraft:item_display run function tarot:table/create',
        'execute if score #placed tarot.sys matches 1 run item replace entity @s weapon.mainhand with minecraft:air','tag @s remove tarot.actor',
    ])
    w('table/space',['scoreboard players set #placed tarot.sys -1','title @s actionbar {"text":"Leave a little space for this card.","color":"gray"}'])
    # The item renderer reverses the plate normal: this verified pose shows the
    # printed BACK. Placement and revealing remain separate deliberate actions.
    visual={'Tags':['tarot.placed','tarot.new'],'item_display':'none','billboard':'fixed','view_range':.75,'shadow_radius':0.0,'Rotation':[0.0,0.0],'transformation':{'translation':[0.0,0.0,0.0],'scale':[.6,.6,.6],'left_rotation':[-.70710677,0.0,0.0,.70710677],'right_rotation':[0.0,0.0,0.0,1.0]}}
    w('table/create',[
        'data merge entity @s '+json.dumps(visual,separators=(',',':')),
        'function tarot:queue/register',
        'execute if score #half tarot.sys matches 1 run tag @s add tarot.half',
        'data modify entity @s item set from storage tarot:runtime chosen.item',
        # NBT-write success alone is insufficient: require a decoded singleton
        # and the complete retained component set before consuming the source.
        'scoreboard players set #codec_ok tarot.sys 1',
        'execute unless items entity @s contents #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set #codec_ok tarot.sys 0',
        'data modify storage tarot:decoded compare set from storage tarot:runtime chosen.item.components',
        'data modify storage tarot:decoded current set from entity @s item.components',
        'function tarot:native/normalize_factory',
        'function tarot:native/normalize_defaults',
        'execute store success score #different tarot.sys run data modify storage tarot:decoded compare set from storage tarot:decoded current',
        'execute if score #different tarot.sys matches 1 run scoreboard players set #codec_ok tarot.sys 0',
        'execute unless score #codec_ok tarot.sys matches 1 run return run function tarot:table/discard',
        'scoreboard players set #reachable tarot.sys 0',
        'execute as @a[tag=tarot.actor,limit=1] at @s anchored eyes positioned ^ ^ ^ if entity @e[type=minecraft:item_display,tag=tarot.new,distance=..4.5,limit=1] run scoreboard players set #reachable tarot.sys 1',
        'execute unless score #reachable tarot.sys matches 1 run return run function tarot:table/discard',
        'data modify entity @s Rotation[0] set from entity @a[tag=tarot.actor,limit=1] Rotation[0]',
        'execute at @s run tp @s ~ ~ ~ ~180 0','scoreboard players set @s tarot.face 0',
        'scoreboard players set #linked tarot.sys 0','execute at @s summon minecraft:interaction run function tarot:table/link',
        'execute if score #linked tarot.sys matches 1 run scoreboard players set #placed tarot.sys 1',
        'tag @s remove tarot.new','execute unless score #placed tarot.sys matches 1 run return run function tarot:table/discard',
        'function tarot:sound/card',
    ])
    w('table/link',[
        'data merge entity @s {Tags:["tarot.touch"],width:0.6f,height:0.09f,response:1b}',
        'execute store success score #linked tarot.sys run ride @s mount @e[type=minecraft:item_display,tag=tarot.new,limit=1]',
        'scoreboard players operation @s tarot.id = @e[type=minecraft:item_display,tag=tarot.new,limit=1] tarot.id',
        'execute unless score #linked tarot.sys matches 1 run kill @s',
    ])
    w('table/support',[
        'scoreboard players set #supported tarot.sys 0',
        'execute if entity @s[tag=tarot.half] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:slabs[type=bottom] run scoreboard players set #supported tarot.sys 1',
        'execute unless entity @s[tag=tarot.half] positioned ~ ~-0.03 ~ if block ~ ~ ~ #tarot:table_surface run scoreboard players set #supported tarot.sys 1',
        'execute unless entity @s[tag=tarot.half] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:slabs[type=top] run scoreboard players set #supported tarot.sys 1',
        'execute unless entity @s[tag=tarot.half] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:slabs[type=double] run scoreboard players set #supported tarot.sys 1',
        'execute unless score #supported tarot.sys matches 1 run function tarot:table/fall',
    ])
    # Parent/passenger identity is persistent and exact; no nearest-card lookup.
    w('table/poll',[
        'execute if data entity @s attack run return run function tarot:table/attack',
        'execute if data entity @s interaction run function tarot:table/use',
    ])
    for event,relation,handler in [('attack','attacker','pickup'),('interaction','target','manipulate')]:
        w('table/'+('attack' if event=='attack' else 'use'),[
            'execute on vehicle run tag @s add tarot.target',
            f'execute on {relation} at @s run function tarot:table/player_{handler}',
            'execute on vehicle run tag @s remove tarot.target',
            'data remove entity @s '+event,
        ])
    admission=['execute if score @s tarot.cool matches 1.. run return 0','execute unless entity @e[type=minecraft:item_display,tag=tarot.target,distance=..5.5,limit=1] run return 0','function tarot:admission','execute unless score #permit tarot.sys matches 1 run return 0','scoreboard players set @s tarot.cool 4']
    w('table/player_manipulate',admission+[
        'execute if predicate tarot:is_sneaking as @e[type=minecraft:item_display,tag=tarot.target,limit=1] at @s run return run function tarot:table/rotate',
        'execute as @e[type=minecraft:item_display,tag=tarot.target,limit=1] at @s run function tarot:table/flip',
    ])
    w('table/flip',[
        'scoreboard players add @s tarot.face 1','execute if score @s tarot.face matches 2.. run scoreboard players set @s tarot.face 0',
        'execute if score @s tarot.face matches 0 run data modify entity @s transformation.right_rotation set value [0f,0f,0f,1f]',
        'execute if score @s tarot.face matches 1 run data modify entity @s transformation.right_rotation set value [0f,1f,0f,0f]',
        'function tarot:sound/card',
    ])
    w('table/rotate',['tp @s ~ ~ ~ ~45 ~','function tarot:sound/card'])
    w('table/player_pickup',admission+[
        'data modify storage tarot:runtime chosen set value {}','data modify storage tarot:runtime chosen.item set from entity @e[type=minecraft:item_display,tag=tarot.target,limit=1] item',
        'function tarot:transfer/to_player',
        'execute if score #delivered tarot.sys matches 1 as @e[type=minecraft:item_display,tag=tarot.target,limit=1] at @s run function tarot:table/discard',
        'execute if score #delivered tarot.sys matches 1 run function tarot:sound/card',
    ])
    w('table/discard',['execute on passengers run function tarot:table/remove_touch','data remove entity @s item','scoreboard players reset @s tarot.id','scoreboard players reset @s tarot.face','kill @s'])
    w('table/remove_touch',['scoreboard players reset @s tarot.id','kill @s'])
    w('table/fall',[
        'data modify storage tarot:runtime chosen set value {}','data modify storage tarot:runtime chosen.item set from entity @s item',
        'scoreboard players set #dropped tarot.sys 0',
        'execute store success score #dropped tarot.sys run function tarot:table/drop_item with storage tarot:runtime chosen',
        'execute if score #dropped tarot.sys matches 1 run function tarot:table/discard',
    ])
    # Summon with a complete valid item. An empty item entity is discarded during
    # construction, even if /data later reports success against its command source.
    # Macro input is the server's serialized compound, never a raw user string.
    w('table/drop_item',['$return run summon minecraft:item ~ ~ ~ {Item:$(item),PickupDelay:10s,Age:0s,Motion:[0d,0d,0d]}'])
