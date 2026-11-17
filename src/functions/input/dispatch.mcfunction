tag @s remove tarot.waiting
$execute unless data storage tarot:inputs pending.p$(id) run return 0
data modify storage tarot:inputs current set value {main:{},offhand:{}}
data modify storage tarot:inputs current.main set from entity @s SelectedItem
data modify storage tarot:inputs current.offhand set from entity @s equipment.offhand
$execute store success score #main_changed tarot.sys run data modify storage tarot:inputs current.main set from storage tarot:inputs pending.p$(id).main
$execute store success score #off_changed tarot.sys run data modify storage tarot:inputs current.offhand set from storage tarot:inputs pending.p$(id).offhand
$data remove storage tarot:inputs pending.p$(id)
execute if score #main_changed tarot.sys matches 1 run return run function tarot:input/cancel
execute if score @s tarot.pending matches 3 if score #off_changed tarot.sys matches 1 run return run function tarot:input/cancel
execute if score @s tarot.pending matches 1 run return run function tarot:input/draw
execute if score @s tarot.pending matches 2 run return run function tarot:input/shuffle
execute if score @s tarot.pending matches 3 run return run function tarot:input/return
execute if score @s tarot.pending matches 4 run return run function tarot:input/place
execute if score @s tarot.pending matches 5 run return run function tarot:input/deal
