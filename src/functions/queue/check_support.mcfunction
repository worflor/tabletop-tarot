tag @s add tarot.maintained
scoreboard players operation #maintenance_cursor tarot.sys = @s tarot.id
execute unless entity @s[tag=tarot.motion_ready] run function tarot:motion/init
function tarot:table/support
