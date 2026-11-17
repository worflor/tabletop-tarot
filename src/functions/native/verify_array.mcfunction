# This buffer belongs to the current transaction. Equality leaves it unchanged.
# A mismatch changes only scratch data and revokes admission before any commit.
execute store success score #different tarot.sys run data modify storage tarot:runtime cards set from storage tarot:decoded cards
execute if score #different tarot.sys matches 1 run scoreboard players set #ready tarot.sys 0
