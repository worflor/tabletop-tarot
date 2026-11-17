# Initial pose is published with the committed card; settle on the next tick.
data merge entity @s {interpolation_duration:0,transformation:{translation:[0f,0.035f,0f]}}
scoreboard players set @s tarot.motion 4
tag @s add tarot.moving
