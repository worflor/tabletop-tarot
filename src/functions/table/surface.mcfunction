execute summon minecraft:marker run function tarot:table/plane
scoreboard players remove #plane_y tarot.sys 210
execute if score #previous_y tarot.sys < #plane_y tarot.sys run return 0
scoreboard players set #dest_clear tarot.sys 0
execute if block ~ ~ ~ #tarot:clear run scoreboard players set #dest_clear tarot.sys 1
execute if score #surface_type tarot.sys matches 1 if block ~ ~ ~ #minecraft:slabs[type=bottom] run scoreboard players set #dest_clear tarot.sys 1
execute if score #surface_type tarot.sys matches 2 if block ~ ~ ~ #minecraft:trapdoors[open=false,half=bottom] run scoreboard players set #dest_clear tarot.sys 1
execute if score #surface_type tarot.sys matches 3 if block ~ ~ ~ #tarot:carpets run scoreboard players set #dest_clear tarot.sys 1
execute unless score #dest_clear tarot.sys matches 1 run return 0
execute if entity @e[type=minecraft:item_display,tag=tarot.placed,distance=..0.24] run return run function tarot:table/space
tag @a remove tarot.actor
tag @s add tarot.actor
execute summon minecraft:item_display run function tarot:table/create
execute if score #placed tarot.sys matches 1 unless score #dealing tarot.sys matches 1 run item replace entity @s weapon.mainhand with minecraft:air
tag @s remove tarot.actor
