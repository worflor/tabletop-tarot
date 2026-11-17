scoreboard players add @s tarot.face 1
execute if score @s tarot.face matches 2.. run scoreboard players set @s tarot.face 0
# During the lift, a repeated flip changes the landing face without restarting it.
execute if entity @s[tag=tarot.turning,scores={tarot.motion=4..6}] run return run function tarot:sound/flip
# A 0.30 lift keeps the whole 0.36-wide card above the table throughout the turn.
data merge entity @s {start_interpolation:0,interpolation_duration:2,transformation:{translation:[0f,0.30f,0f],right_rotation:[0f,0.70710677f,0f,0.70710677f]}}
scoreboard players set @s tarot.motion 6
tag @s add tarot.moving
tag @s add tarot.turning
function tarot:sound/flip
