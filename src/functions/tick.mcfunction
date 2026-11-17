execute store result score #table_budget tarot.sys run gamerule minecraft:max_command_sequence_length
execute if score #table_budget tarot.sys matches 65536.. as @e[type=minecraft:item_display,tag=tarot.moving] run function tarot:motion/step
execute as @a unless score @s tarot.id matches 1.. run function tarot:queue/register
scoreboard players add #maintenance_cursor tarot.sys 0
scoreboard players add @a tarot.cool 0
scoreboard players remove @a[scores={tarot.cool=1..}] tarot.cool 1
scoreboard players enable @a tarot.action
tag @a remove tarot.dimension
execute as @a at @s run function tarot:queue/dimension_leader
execute as @a[tag=tarot.dimension] at @s run function tarot:queue/prepare_dimension
execute as @a at @s run function tarot:queue/discover
execute as @a[tag=tarot.dimension] at @s run function tarot:queue/register_tables
tag @a remove tarot.queued
execute as @a[tag=!tarot.waiting,scores={tarot.use=1..,tarot.cool=0}] run function tarot:input/use
execute as @a[tag=!tarot.waiting,scores={tarot.action=1..5,tarot.cool=0}] run function tarot:input/trigger
scoreboard players set @a[tag=tarot.waiting] tarot.use 0
scoreboard players set @a[tag=tarot.waiting] tarot.action 0
tag @a[tag=tarot.waiting,scores={tarot.cool=0}] add tarot.queued
scoreboard players set #heavy_left tarot.sys 2
function tarot:queue/next
function tarot:queue/next
function tarot:queue/next
function tarot:queue/next
function tarot:queue/next
function tarot:queue/next
function tarot:queue/next
function tarot:queue/next
scoreboard players set @a[scores={tarot.action=6..}] tarot.action 0
scoreboard players set @a[scores={tarot.action=..-1}] tarot.action 0
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance
scoreboard players add #input_gc tarot.sys 1
execute if score #input_gc tarot.sys matches 200.. run function tarot:input/prune
