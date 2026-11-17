function tarot:stack/validate
execute unless score #valid tarot.sys matches 1 run title @s actionbar {"text":"This stack has invalid contents. Nothing was changed.","color":"gray"}
execute unless score #valid tarot.sys matches 1 run return 0
execute if score #size tarot.roll matches 128.. run title @s actionbar {"text":"This band holds at most 128 cards.","color":"gray"}
execute if score #size tarot.roll matches 128.. run return 0
scoreboard players set #scoop_limit tarot.sys 1
execute if predicate tarot:is_sneaking run scoreboard players set #scoop_limit tarot.sys 16
scoreboard players set #scooped tarot.sys 0
tag @e[type=minecraft:item_display,tag=tarot.scoop_ok] remove tarot.scoop_ok
tag @a remove tarot.actor
tag @s add tarot.actor
execute store result score #scoop_y tarot.sys run data get entity @e[type=minecraft:item_display,tag=tarot.target,limit=1] Pos[1] 10000
execute as @e[type=minecraft:item_display,tag=tarot.target,limit=1] run function tarot:table/scoop_one
execute if score #scoop_limit tarot.sys matches 2.. if score #scooped tarot.sys matches 1.. at @e[type=minecraft:item_display,tag=tarot.target,limit=1] as @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.scoop_ok,distance=..2.5,sort=nearest,limit=15] run function tarot:table/scoop_one
tag @s remove tarot.actor
execute unless score #scooped tarot.sys matches 1.. run return 0
scoreboard players set #consume tarot.sys 0
scoreboard players set #deliver tarot.sys 0
scoreboard players set #returning tarot.sys 1
function tarot:stack/sync
scoreboard players set #returning tarot.sys 0
execute if score #committed tarot.sys matches 1 if score #scoop_limit tarot.sys matches 2.. if score #size tarot.roll matches 128.. at @e[type=minecraft:item_display,tag=tarot.target,limit=1] if entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.scoop_ok,distance=..2.5] run title @s actionbar {"text":"This band holds at most 128 cards.","color":"gray"}
execute if score #committed tarot.sys matches 1 as @e[type=minecraft:item_display,tag=tarot.scoop_ok] at @s run function tarot:table/discard
execute if score #committed tarot.sys matches 1 if score #scooped tarot.sys matches 1 run function tarot:sound/card
execute if score #committed tarot.sys matches 1 if score #scooped tarot.sys matches 2.. run function tarot:sound/shuffle
tag @e[type=minecraft:item_display,tag=tarot.scoop_ok] remove tarot.scoop_ok
