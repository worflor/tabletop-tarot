execute if score @s tarot.cool matches 1.. run return 0
execute unless entity @e[type=minecraft:item_display,tag=tarot.target,distance=..5.5,limit=1] run return 0
tag @e[tag=tarot.sight] remove tarot.sight
tag @e[type=minecraft:item_display,tag=tarot.target,limit=1] add tarot.sight
function tarot:table/can_reach
tag @e[tag=tarot.sight] remove tarot.sight
execute unless score #reachable tarot.sys matches 1 run return 0
function tarot:admission
execute unless score #permit tarot.sys matches 1 run return 0
scoreboard players set @s tarot.cool 4
execute if predicate tarot:is_sneaking as @e[type=minecraft:item_display,tag=tarot.target,limit=1] at @s run return run function tarot:table/rotate
execute as @e[type=minecraft:item_display,tag=tarot.target,limit=1] at @s run function tarot:table/flip
