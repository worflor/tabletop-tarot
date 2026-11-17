execute positioned ^ ^ ^-0.05 summon minecraft:marker run function tarot:table/previous
scoreboard players set #surface_type tarot.sys 0
execute if block ~ ~ ~ #tarot:table_surface align y positioned ~ ~1.021 ~ run return run function tarot:table/surface
execute if block ~ ~ ~ #minecraft:slabs[type=top] align y positioned ~ ~1.021 ~ run return run function tarot:table/surface
execute if block ~ ~ ~ #minecraft:slabs[type=double] align y positioned ~ ~1.021 ~ run return run function tarot:table/surface
execute if block ~ ~ ~ #minecraft:trapdoors[open=false,half=top] align y positioned ~ ~1.021 ~ run return run function tarot:table/surface
execute if block ~ ~ ~ #minecraft:stairs[half=top] align y positioned ~ ~1.021 ~ run return run function tarot:table/surface
scoreboard players set #surface_type tarot.sys 1
execute if block ~ ~ ~ #minecraft:slabs[type=bottom] align y positioned ~ ~0.521 ~ run return run function tarot:table/surface
scoreboard players set #surface_type tarot.sys 2
execute if block ~ ~ ~ #minecraft:trapdoors[open=false,half=bottom] align y positioned ~ ~0.2085 ~ run return run function tarot:table/surface
scoreboard players set #surface_type tarot.sys 3
execute if block ~ ~ ~ #tarot:carpets align y positioned ~ ~0.0835 ~ run function tarot:table/surface
