# Minecraft emits this event synchronously after a successful native block use.
# The main-hand rod statistic may already have increased before the offhand
# placed its last item. That same click must not become a Tarot action too.
advancement revoke @s only tarot:input/vanilla_block_use
execute if items entity @s weapon.mainhand #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] run scoreboard players set @s tarot.use 0
execute if items entity @s weapon.mainhand minecraft:carrot_on_a_stick[minecraft:custom_data~{tarot:{kind:"deck"}}] run scoreboard players set @s tarot.use 0
