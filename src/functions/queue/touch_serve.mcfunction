scoreboard players operation #cursor tarot.sys = @s tarot.id
# Pickups and scoops share the deck-operation allowance. Leave deferred events intact.
execute if data entity @s attack if score #heavy_left tarot.sys matches ..0 run return 0
execute if data entity @s attack run scoreboard players remove #heavy_left tarot.sys 1
function tarot:table/poll
