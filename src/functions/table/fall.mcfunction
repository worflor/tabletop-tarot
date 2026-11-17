data modify storage tarot:runtime chosen set value {}
data modify storage tarot:runtime chosen.item set from entity @s item
data modify storage tarot:runtime chosen.item.count set value 1
scoreboard players set #dropped tarot.sys 0
tag @e[type=minecraft:item,tag=tarot.drop_tmp] remove tarot.drop_tmp
summon minecraft:item ~ ~ ~ {Tags:["tarot.drop_tmp"],PickupDelay:10s,Age:0s,Motion:[0d,0d,0d],Item:{id:"minecraft:carrot_on_a_stick",count:1}}
execute as @e[type=minecraft:item,tag=tarot.drop_tmp,limit=1] run function tarot:table/drop_item
execute if score #dropped tarot.sys matches 1 run function tarot:table/discard
