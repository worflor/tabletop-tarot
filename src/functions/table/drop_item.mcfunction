tag @s remove tarot.drop_tmp
data modify entity @s Item set from storage tarot:runtime chosen.item
scoreboard players set #drop_safe tarot.sys 1
execute unless items entity @s contents #tarot:card_carriers[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set #drop_safe tarot.sys 0
data modify storage tarot:decoded compare set from storage tarot:runtime chosen.item.components
data modify storage tarot:decoded current set from entity @s Item.components
function tarot:native/normalize_factory
function tarot:native/normalize_defaults
execute store success score #different tarot.sys run data modify storage tarot:decoded compare set from storage tarot:decoded current
execute if score #different tarot.sys matches 1 run scoreboard players set #drop_safe tarot.sys 0
execute if score #drop_safe tarot.sys matches 1 run scoreboard players set #dropped tarot.sys 1
execute unless score #drop_safe tarot.sys matches 1 run kill @s
