# The latest logical face wins, including another player's intervening flip.
execute unless score @s tarot.face matches 1 run data merge entity @s {start_interpolation:0,interpolation_duration:2,transformation:{translation:[0f,0f,0f],right_rotation:[0f,0f,0f,1f]}}
execute if score @s tarot.face matches 1 run data merge entity @s {start_interpolation:0,interpolation_duration:2,transformation:{translation:[0f,0f,0f],right_rotation:[0f,1f,0f,0f]}}
