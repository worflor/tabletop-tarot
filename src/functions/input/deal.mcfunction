execute if score @s tarot.cool matches 1.. run return 0
function tarot:admission
execute unless score #permit tarot.sys matches 1 run return 0
scoreboard players set @s tarot.cool 2
execute if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"deck",module:"rider"}}] run return run function tarot:checked/deal/rider
execute if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:count=1,minecraft:custom_data~{tarot:{kind:"deck",module:"numbers"}}] run return run function tarot:checked/deal/numbers
title @s actionbar {"text":"Hold a card stack in your main hand.","color":"gray"}
