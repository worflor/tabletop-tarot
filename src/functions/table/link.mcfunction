data merge entity @s {Tags:["tarot.touch"],width:0.42f,height:0.08f,response:1b}
execute store success score #linked tarot.sys run ride @s mount @e[type=minecraft:item_display,tag=tarot.new,limit=1]
scoreboard players operation @s tarot.id = @e[type=minecraft:item_display,tag=tarot.new,limit=1] tarot.id
execute unless score #linked tarot.sys matches 1 run kill @s
