scoreboard players set #valid tarot.sys 0
scoreboard players set #promoted tarot.sys 0
scoreboard players set #deliver tarot.sys 0
scoreboard players set #consume tarot.sys 0
scoreboard players set #returning tarot.sys 0
execute unless items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:count=1] run return 0
# Capture once. Every native check and commit preparation reads this same item.
data remove storage tarot:transaction main
execute store success score #band_captured tarot.sys run data modify storage tarot:transaction main set from entity @s SelectedItem
execute unless score #band_captured tarot.sys matches 1 run return 0
execute if data storage tarot:transaction main.components."minecraft:custom_data".tarot{storage:"native-v1"} run return run function tarot:native/validate
execute if data storage tarot:transaction main.components."minecraft:custom_data".tarot.storage run return 0
execute if data storage tarot:transaction main.components."minecraft:charged_projectiles"[0] run return 0
function tarot:stack/validate_opaque
execute unless score #valid tarot.sys matches 1 run return 0
function tarot:native/promote
