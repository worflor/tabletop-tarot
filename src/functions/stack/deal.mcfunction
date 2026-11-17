execute unless data storage tarot:runtime cards[0] run title @s actionbar {"text":"The band is empty. Put a card on top.","color":"gray"}
execute unless data storage tarot:runtime cards[0] run return 0
data modify storage tarot:runtime chosen set value {}
data modify storage tarot:runtime chosen.item set from storage tarot:runtime cards[0]
function tarot:card/upgrade_chosen
execute unless score #carrier_safe tarot.sys matches 1 run return 0
tag @e[type=minecraft:item_display,tag=tarot.just_dealt] remove tarot.just_dealt
scoreboard players set #placed tarot.sys 0
scoreboard players set #dealing tarot.sys 1
scoreboard players set #ray tarot.sys 100
execute anchored eyes positioned ^ ^ ^ anchored feet run function tarot:table/trace
scoreboard players set #dealing tarot.sys 0
execute if score #placed tarot.sys matches 0 run title @s actionbar {"text":"Aim at a clear tabletop surface within reach.","color":"gray"}
execute unless score #placed tarot.sys matches 1 run tag @e[type=minecraft:item_display,tag=tarot.just_dealt] remove tarot.just_dealt
execute unless score #placed tarot.sys matches 1 run return 0
data remove storage tarot:runtime cards[0]
scoreboard players set #consume tarot.sys 0
scoreboard players set #deliver tarot.sys 0
function tarot:stack/sync
execute if score #committed tarot.sys matches 1 as @e[type=minecraft:item_display,tag=tarot.just_dealt] run function tarot:motion/place
execute if score #committed tarot.sys matches 1 as @e[type=minecraft:item_display,tag=tarot.just_dealt] at @s run function tarot:sound/place
execute unless score #committed tarot.sys matches 1 as @e[type=minecraft:item_display,tag=tarot.just_dealt] at @s run function tarot:table/discard
tag @e[type=minecraft:item_display,tag=tarot.just_dealt] remove tarot.just_dealt
