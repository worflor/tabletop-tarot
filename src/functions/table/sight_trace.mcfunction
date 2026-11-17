execute if entity @e[type=minecraft:item_display,tag=tarot.sight,distance=..0.051,limit=1] run return run scoreboard players set #reachable tarot.sys 1
scoreboard players set #sight_clear tarot.sys 0
execute if block ~ ~ ~ #tarot:clear run scoreboard players set #sight_clear tarot.sys 1
execute unless score #sight_clear tarot.sys matches 1 run function tarot:table/sight_partial
execute unless score #sight_clear tarot.sys matches 1 run return 0
scoreboard players remove #sight_steps tarot.sys 1
execute if score #sight_steps tarot.sys matches 0.. positioned ^ ^ ^0.05 run function tarot:table/sight_trace
