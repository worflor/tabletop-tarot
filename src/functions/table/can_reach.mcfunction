# Called as the player. A single tagged display is the endpoint; work is bounded to 4.5m.
scoreboard players set #reachable tarot.sys 0
scoreboard players set #sight_steps tarot.sys 90
execute at @s anchored eyes positioned ^ ^ ^ anchored feet if entity @e[type=minecraft:item_display,tag=tarot.sight,distance=..4.5,limit=1] facing entity @e[type=minecraft:item_display,tag=tarot.sight,limit=1] feet run function tarot:table/sight_trace
