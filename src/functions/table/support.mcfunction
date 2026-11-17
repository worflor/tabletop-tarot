scoreboard players set #supported tarot.sys 0
execute if entity @s[tag=tarot.half] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:slabs[type=bottom] run scoreboard players set #supported tarot.sys 1
execute if entity @s[tag=tarot.trapdoor_low] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:trapdoors[open=false,half=bottom] run scoreboard players set #supported tarot.sys 1
execute if entity @s[tag=tarot.carpet] positioned ~ ~-0.03 ~ if block ~ ~ ~ #tarot:carpets run scoreboard players set #supported tarot.sys 1
execute unless entity @s[tag=tarot.half] unless entity @s[tag=tarot.trapdoor_low] unless entity @s[tag=tarot.carpet] positioned ~ ~-0.03 ~ if block ~ ~ ~ #tarot:table_surface run scoreboard players set #supported tarot.sys 1
execute unless entity @s[tag=tarot.half] unless entity @s[tag=tarot.trapdoor_low] unless entity @s[tag=tarot.carpet] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:slabs[type=top] run scoreboard players set #supported tarot.sys 1
execute unless entity @s[tag=tarot.half] unless entity @s[tag=tarot.trapdoor_low] unless entity @s[tag=tarot.carpet] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:slabs[type=double] run scoreboard players set #supported tarot.sys 1
execute unless entity @s[tag=tarot.half] unless entity @s[tag=tarot.trapdoor_low] unless entity @s[tag=tarot.carpet] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:trapdoors[open=false,half=top] run scoreboard players set #supported tarot.sys 1
execute unless entity @s[tag=tarot.half] unless entity @s[tag=tarot.trapdoor_low] unless entity @s[tag=tarot.carpet] positioned ~ ~-0.03 ~ if block ~ ~ ~ #minecraft:stairs[half=top] run scoreboard players set #supported tarot.sys 1
execute unless score #supported tarot.sys matches 1 run function tarot:table/fall
