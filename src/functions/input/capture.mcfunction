scoreboard players set @s tarot.use 0
scoreboard players set @s tarot.action 0
execute unless score @s tarot.pending matches 1..5 run return 0
data modify storage tarot:inputs fresh set value {main:{},offhand:{}}
data modify storage tarot:inputs fresh.main set from entity @s SelectedItem
data modify storage tarot:inputs fresh.offhand set from entity @s equipment.offhand
execute store result storage tarot:inputs context.id int 1 run scoreboard players get @s tarot.id
function tarot:input/save with storage tarot:inputs context
tag @s add tarot.waiting
