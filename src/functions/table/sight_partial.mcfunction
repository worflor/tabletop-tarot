execute summon minecraft:marker run function tarot:table/height
execute if block ~ ~ ~ #minecraft:slabs[type=bottom] if score #fraction tarot.sys matches 5000.. run scoreboard players set #sight_clear tarot.sys 1
execute if block ~ ~ ~ #minecraft:trapdoors[open=false,half=bottom] if score #fraction tarot.sys matches 1875.. run scoreboard players set #sight_clear tarot.sys 1
execute if block ~ ~ ~ #tarot:carpets if score #fraction tarot.sys matches 625.. run scoreboard players set #sight_clear tarot.sys 1
