execute unless score #size tarot.roll matches ..127 run return 0
execute unless score #scooped tarot.sys < #scoop_limit tarot.sys run return 0
# Gather only the same tabletop plane, within eye reach and unobstructed from the player.
execute store result score #candidate_y tarot.sys run data get entity @s Pos[1] 10000
scoreboard players operation #candidate_y tarot.sys -= #scoop_y tarot.sys
execute unless score #candidate_y tarot.sys matches -100..100 run return 0
tag @s add tarot.sight
execute as @a[tag=tarot.actor,limit=1] run function tarot:table/can_reach
tag @s remove tarot.sight
execute unless score #reachable tarot.sys matches 1 run return 0
data modify storage tarot:runtime entry set from entity @s item
execute as @a[tag=tarot.actor,limit=1] run function tarot:card/upgrade_entry
execute unless score #carrier_safe tarot.sys matches 1 run return 0
data modify storage tarot:runtime cards prepend from storage tarot:runtime entry
scoreboard players add #size tarot.roll 1
scoreboard players add #scooped tarot.sys 1
tag @s add tarot.scoop_ok
