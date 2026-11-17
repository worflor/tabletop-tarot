scoreboard objectives add tarot.use minecraft.used:minecraft.carrot_on_a_stick
scoreboard objectives add tarot.action trigger
scoreboard objectives add tarot.roll dummy
scoreboard objectives add tarot.i dummy
scoreboard objectives add tarot.j dummy
scoreboard objectives add tarot.sys dummy
scoreboard objectives add tarot.cool dummy
scoreboard objectives add tarot.pending dummy
scoreboard objectives add tarot.id dummy
scoreboard objectives add tarot.face dummy
scoreboard objectives add tarot.layer dummy
scoreboard objectives add tarot.motion dummy
scoreboard players add #next_id tarot.sys 0
scoreboard players add #cursor tarot.sys 0
data modify storage tarot:config schema set value 8
scoreboard players enable @a tarot.action
