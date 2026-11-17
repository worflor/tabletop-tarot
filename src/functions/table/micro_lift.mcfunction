# Allocate a free local height layer; entity IDs modulo four can collide.
scoreboard players set #layer tarot.sys -1
# Unscored saved displays may occupy the old 0/.0012/.0024/.0036 heights.
scoreboard players set #legacy_layer tarot.sys 0
execute as @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65] unless score @s tarot.layer matches 0..31 run scoreboard players set #legacy_layer tarot.sys 1
execute if score #layer tarot.sys matches -1 if score #legacy_layer tarot.sys matches 0 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=0}] run scoreboard players set #layer tarot.sys 0
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=1}] run scoreboard players set #layer tarot.sys 1
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=2}] run scoreboard players set #layer tarot.sys 2
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=3}] run scoreboard players set #layer tarot.sys 3
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=4}] run scoreboard players set #layer tarot.sys 4
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=5}] run scoreboard players set #layer tarot.sys 5
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=6}] run scoreboard players set #layer tarot.sys 6
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=7}] run scoreboard players set #layer tarot.sys 7
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=8}] run scoreboard players set #layer tarot.sys 8
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=9}] run scoreboard players set #layer tarot.sys 9
execute if score #layer tarot.sys matches -1 if score #legacy_layer tarot.sys matches 0 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=10}] run scoreboard players set #layer tarot.sys 10
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=11}] run scoreboard players set #layer tarot.sys 11
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=12}] run scoreboard players set #layer tarot.sys 12
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=13}] run scoreboard players set #layer tarot.sys 13
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=14}] run scoreboard players set #layer tarot.sys 14
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=15}] run scoreboard players set #layer tarot.sys 15
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=16}] run scoreboard players set #layer tarot.sys 16
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=17}] run scoreboard players set #layer tarot.sys 17
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=18}] run scoreboard players set #layer tarot.sys 18
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=19}] run scoreboard players set #layer tarot.sys 19
execute if score #layer tarot.sys matches -1 if score #legacy_layer tarot.sys matches 0 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=20}] run scoreboard players set #layer tarot.sys 20
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=21}] run scoreboard players set #layer tarot.sys 21
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=22}] run scoreboard players set #layer tarot.sys 22
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=23}] run scoreboard players set #layer tarot.sys 23
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=24}] run scoreboard players set #layer tarot.sys 24
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=25}] run scoreboard players set #layer tarot.sys 25
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=26}] run scoreboard players set #layer tarot.sys 26
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=27}] run scoreboard players set #layer tarot.sys 27
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=28}] run scoreboard players set #layer tarot.sys 28
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=29}] run scoreboard players set #layer tarot.sys 29
execute if score #layer tarot.sys matches -1 if score #legacy_layer tarot.sys matches 0 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=30}] run scoreboard players set #layer tarot.sys 30
execute if score #layer tarot.sys matches -1 unless entity @e[type=minecraft:item_display,tag=tarot.placed,tag=!tarot.new,distance=..0.65,scores={tarot.layer=31}] run scoreboard players set #layer tarot.sys 31
scoreboard players operation @s tarot.layer = #layer tarot.sys
execute if score #layer tarot.sys matches 1 run tp @s ~ ~0.00012 ~
execute if score #layer tarot.sys matches 2 run tp @s ~ ~0.00024 ~
execute if score #layer tarot.sys matches 3 run tp @s ~ ~0.00036 ~
execute if score #layer tarot.sys matches 4 run tp @s ~ ~0.00048 ~
execute if score #layer tarot.sys matches 5 run tp @s ~ ~0.00060 ~
execute if score #layer tarot.sys matches 6 run tp @s ~ ~0.00072 ~
execute if score #layer tarot.sys matches 7 run tp @s ~ ~0.00084 ~
execute if score #layer tarot.sys matches 8 run tp @s ~ ~0.00096 ~
execute if score #layer tarot.sys matches 9 run tp @s ~ ~0.00108 ~
execute if score #layer tarot.sys matches 10 run tp @s ~ ~0.00120 ~
execute if score #layer tarot.sys matches 11 run tp @s ~ ~0.00132 ~
execute if score #layer tarot.sys matches 12 run tp @s ~ ~0.00144 ~
execute if score #layer tarot.sys matches 13 run tp @s ~ ~0.00156 ~
execute if score #layer tarot.sys matches 14 run tp @s ~ ~0.00168 ~
execute if score #layer tarot.sys matches 15 run tp @s ~ ~0.00180 ~
execute if score #layer tarot.sys matches 16 run tp @s ~ ~0.00192 ~
execute if score #layer tarot.sys matches 17 run tp @s ~ ~0.00204 ~
execute if score #layer tarot.sys matches 18 run tp @s ~ ~0.00216 ~
execute if score #layer tarot.sys matches 19 run tp @s ~ ~0.00228 ~
execute if score #layer tarot.sys matches 20 run tp @s ~ ~0.00240 ~
execute if score #layer tarot.sys matches 21 run tp @s ~ ~0.00252 ~
execute if score #layer tarot.sys matches 22 run tp @s ~ ~0.00264 ~
execute if score #layer tarot.sys matches 23 run tp @s ~ ~0.00276 ~
execute if score #layer tarot.sys matches 24 run tp @s ~ ~0.00288 ~
execute if score #layer tarot.sys matches 25 run tp @s ~ ~0.00300 ~
execute if score #layer tarot.sys matches 26 run tp @s ~ ~0.00312 ~
execute if score #layer tarot.sys matches 27 run tp @s ~ ~0.00324 ~
execute if score #layer tarot.sys matches 28 run tp @s ~ ~0.00336 ~
execute if score #layer tarot.sys matches 29 run tp @s ~ ~0.00348 ~
execute if score #layer tarot.sys matches 30 run tp @s ~ ~0.00360 ~
execute if score #layer tarot.sys matches 31 run tp @s ~ ~0.00372 ~
