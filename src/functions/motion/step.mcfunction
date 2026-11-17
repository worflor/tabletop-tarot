# One finite state per card. New input replaces it; no delayed UUID callbacks.
scoreboard players remove @s tarot.motion 1
execute if score @s tarot.motion matches 3 run function tarot:motion/settle
execute unless score @s tarot.motion matches 1.. run function tarot:motion/finish
