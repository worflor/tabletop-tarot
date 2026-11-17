data merge entity @s {"Tags":["tarot.placed","tarot.new","tarot.motion_ready"],"item_display":"none","billboard":"fixed","view_range":0.75,"shadow_radius":0.0,"teleport_duration":3,"Rotation":[0.0,0.0],"transformation":{"translation":[0.0,0.0,0.0],"scale":[0.6,0.6,0.6],"left_rotation":[-0.70710677,0.0,0.0,0.70710677],"right_rotation":[0.0,0.0,0.0,1.0]}}
function tarot:queue/register
execute if score #surface_type tarot.sys matches 1 run tag @s add tarot.half
execute if score #surface_type tarot.sys matches 2 run tag @s add tarot.trapdoor_low
execute if score #surface_type tarot.sys matches 3 run tag @s add tarot.carpet
execute if score #dealing tarot.sys matches 1 run tag @s add tarot.just_dealt
data modify entity @s item set from storage tarot:runtime chosen.item
scoreboard players set #codec_ok tarot.sys 1
execute unless items entity @s contents #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set #codec_ok tarot.sys 0
data modify storage tarot:decoded compare set from storage tarot:runtime chosen.item.components
data modify storage tarot:decoded current set from entity @s item.components
function tarot:native/normalize_factory
function tarot:native/normalize_defaults
execute store success score #different tarot.sys run data modify storage tarot:decoded compare set from storage tarot:decoded current
execute if score #different tarot.sys matches 1 run scoreboard players set #codec_ok tarot.sys 0
execute unless score #codec_ok tarot.sys matches 1 run return run function tarot:table/discard
scoreboard players set #reachable tarot.sys 0
execute as @a[tag=tarot.actor,limit=1] at @s anchored eyes positioned ^ ^ ^ if entity @e[type=minecraft:item_display,tag=tarot.new,distance=..4.5,limit=1] run scoreboard players set #reachable tarot.sys 1
execute unless score #reachable tarot.sys matches 1 run return run function tarot:table/discard
execute at @s run function tarot:table/micro_lift
execute if score #layer tarot.sys matches -1 run return run function tarot:table/discard
data modify entity @s Rotation[0] set from entity @a[tag=tarot.actor,limit=1] Rotation[0]
execute at @s run tp @s ~ ~ ~ ~180 0
scoreboard players set @s tarot.face 0
scoreboard players set #linked tarot.sys 0
execute at @s summon minecraft:interaction run function tarot:table/link
execute if score #linked tarot.sys matches 1 run scoreboard players set #placed tarot.sys 1
tag @s remove tarot.new
execute unless score #placed tarot.sys matches 1 run return run function tarot:table/discard
execute unless score #dealing tarot.sys matches 1 run function tarot:motion/place
execute unless score #dealing tarot.sys matches 1 run function tarot:sound/place
