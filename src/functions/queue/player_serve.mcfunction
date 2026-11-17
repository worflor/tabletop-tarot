tag @s remove tarot.queued
scoreboard players operation #cursor tarot.sys = @s tarot.id
execute unless score @s tarot.pending matches 4 if score #heavy_left tarot.sys matches ..0 run return 0
execute unless score @s tarot.pending matches 4 run scoreboard players remove #heavy_left tarot.sys 1
function tarot:input/serve
