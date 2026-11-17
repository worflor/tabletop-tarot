execute if block ~ ~ ~ #tarot:clear run return run function tarot:table/step
execute if block ~ ~ ~ #tarot:carpets run return run function tarot:table/carpet
execute if block ~ ~ ~ #minecraft:slabs[type=bottom] run return run function tarot:table/slab
execute if block ~ ~ ~ #minecraft:trapdoors[open=false,half=bottom] run return run function tarot:table/trapdoor_low
function tarot:table/hit
