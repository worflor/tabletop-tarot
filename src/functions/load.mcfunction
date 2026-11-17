execute unless data storage tarot:config {schema:8} run function tarot:setup
data remove storage tarot:inputs pending
data remove storage tarot:transaction main
tag @a remove tarot.waiting
scoreboard players set @a tarot.pending 0
function tarot:catalogue/load
