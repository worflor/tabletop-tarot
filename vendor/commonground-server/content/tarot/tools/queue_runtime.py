"""Bound player/touch transfers and surface maintenance independently of card count."""
def generate(w,command_rule):
    w('queue/register',['scoreboard players add #next_id tarot.sys 1','scoreboard players operation @s tarot.id = #next_id tarot.sys','tag @s add tarot.registered'])
    w('queue/dimension_leader',['execute unless entity @a[tag=tarot.dimension,distance=0..] run tag @s add tarot.dimension'])
    w('queue/prepare_dimension',['tag @e[tag=tarot.visible] remove tarot.visible','tag @e[tag=tarot.maintained] remove tarot.maintained'])
    w('queue/discover',['tag @e[type=minecraft:item_display,tag=tarot.placed,distance=..48] add tarot.visible','tag @e[type=minecraft:interaction,tag=tarot.touch,distance=..6] add tarot.visible'])
    w('queue/register_tables',['execute as @e[type=minecraft:item_display,tag=tarot.visible,tag=!tarot.registered,limit=8] run function tarot:queue/register_table'])
    w('queue/register_table',['function tarot:queue/register','scoreboard players operation #parent_id tarot.sys = @s tarot.id','execute on passengers run scoreboard players operation @s tarot.id = #parent_id tarot.sys'])
    # Scoreboard minimum accepts multiple sources in ONE command. Do not turn
    # large candidate sets into one callback/function per entity.
    w('queue/next',[
        'scoreboard players operation #after tarot.sys = #cursor tarot.sys','scoreboard players add #after tarot.sys 1',
        'execute store result storage tarot:runtime after int 1 run scoreboard players get #after tarot.sys',
        'scoreboard players set #pick tarot.sys 2147483647',
        'function tarot:queue/candidates with storage tarot:runtime',
        'execute if score #pick tarot.sys matches 2147483647 run function tarot:queue/wrap',
        'execute if score #pick tarot.sys matches 2147483647 run return 0',
        'execute store result storage tarot:runtime pick int 1 run scoreboard players get #pick tarot.sys',
        'function tarot:queue/serve with storage tarot:runtime',
    ])
    w('queue/candidates',['$scoreboard players operation #pick tarot.sys < @a[tag=tarot.queued,scores={tarot.id=$(after)..}] tarot.id','execute as @a[tag=tarot.dimension] at @s run function tarot:queue/table_candidates with storage tarot:runtime'])
    w('queue/table_candidates',[
        '$scoreboard players operation #pick tarot.sys < @e[type=minecraft:interaction,tag=tarot.visible,nbt={attack:{}},scores={tarot.id=$(after)..}] tarot.id',
        '$scoreboard players operation #pick tarot.sys < @e[type=minecraft:interaction,tag=tarot.visible,nbt={interaction:{}},scores={tarot.id=$(after)..}] tarot.id',
    ])
    w('queue/wrap',['scoreboard players operation #pick tarot.sys < @a[tag=tarot.queued] tarot.id','execute as @a[tag=tarot.dimension] at @s run function tarot:queue/table_wrap'])
    w('queue/table_wrap',['scoreboard players operation #pick tarot.sys < @e[type=minecraft:interaction,tag=tarot.visible,nbt={attack:{}},scores={tarot.id=1..}] tarot.id','scoreboard players operation #pick tarot.sys < @e[type=minecraft:interaction,tag=tarot.visible,nbt={interaction:{}},scores={tarot.id=1..}] tarot.id'])
    w('queue/serve',['$execute as @a[tag=tarot.queued,scores={tarot.id=$(pick)},limit=1] at @s run function tarot:queue/player_serve','execute as @a[tag=tarot.dimension] at @s run function tarot:queue/table_serve with storage tarot:runtime'])
    w('queue/player_serve',[
        'tag @s remove tarot.queued','scoreboard players operation #cursor tarot.sys = @s tarot.id',
        # Full-stack NBT operations are expensive. Defer excess work without
        # consuming the player's input; lightweight tabletop actions stay quick.
        'execute if score @s tarot.pending matches 1..3 if score #heavy_left tarot.sys matches ..0 run return 0',
        'execute if score @s tarot.pending matches 1..3 run scoreboard players remove #heavy_left tarot.sys 1',
        'function tarot:input/serve',
    ])
    w('queue/table_serve',['$execute as @e[type=minecraft:interaction,tag=tarot.visible,scores={tarot.id=$(pick)},limit=1] at @s run function tarot:queue/touch_serve'])
    w('queue/touch_serve',['scoreboard players operation #cursor tarot.sys = @s tarot.id','function tarot:table/poll'])
    w('queue/maintenance',[
        'scoreboard players operation #after tarot.sys = #maintenance_cursor tarot.sys','scoreboard players add #after tarot.sys 1',
        'execute store result storage tarot:runtime after int 1 run scoreboard players get #after tarot.sys',
        'scoreboard players set #pick tarot.sys 2147483647',
        'execute as @a[tag=tarot.dimension] at @s run function tarot:queue/maintenance_candidates with storage tarot:runtime',
        'execute if score #pick tarot.sys matches 2147483647 as @a[tag=tarot.dimension] at @s run function tarot:queue/maintenance_wrap',
        'execute if score #pick tarot.sys matches 2147483647 run return 0',
        'execute store result storage tarot:runtime pick int 1 run scoreboard players get #pick tarot.sys',
        'execute as @a[tag=tarot.dimension] at @s run function tarot:queue/maintenance_serve with storage tarot:runtime',
    ])
    w('queue/maintenance_candidates',['$scoreboard players operation #pick tarot.sys < @e[type=minecraft:item_display,tag=tarot.visible,tag=tarot.registered,tag=!tarot.maintained,scores={tarot.id=$(after)..}] tarot.id'])
    w('queue/maintenance_wrap',['scoreboard players operation #pick tarot.sys < @e[type=minecraft:item_display,tag=tarot.visible,tag=tarot.registered,tag=!tarot.maintained] tarot.id'])
    w('queue/maintenance_serve',['$execute as @e[type=minecraft:item_display,tag=tarot.visible,tag=tarot.registered,tag=!tarot.maintained,scores={tarot.id=$(pick)},limit=1] at @s run function tarot:queue/check_support'])
    w('queue/check_support',['tag @s add tarot.maintained','scoreboard players operation #maintenance_cursor tarot.sys = @s tarot.id','function tarot:table/support'])
    w('tick',[
        'execute as @a unless score @s tarot.id matches 1.. run function tarot:queue/register',
        'scoreboard players add #maintenance_cursor tarot.sys 0','scoreboard players add @a tarot.cool 0','scoreboard players remove @a[scores={tarot.cool=1..}] tarot.cool 1','scoreboard players enable @a tarot.action',
        'tag @a remove tarot.dimension','execute as @a at @s run function tarot:queue/dimension_leader',
        'execute as @a[tag=tarot.dimension] at @s run function tarot:queue/prepare_dimension',
        'execute as @a at @s run function tarot:queue/discover',
        'execute as @a[tag=tarot.dimension] at @s run function tarot:queue/register_tables',
        'tag @a remove tarot.queued',
        'execute as @a[tag=!tarot.waiting,scores={tarot.use=1..,tarot.cool=0}] run function tarot:input/use',
        'execute as @a[tag=!tarot.waiting,scores={tarot.action=1..4,tarot.cool=0}] run function tarot:input/trigger',
        'scoreboard players set @a[tag=tarot.waiting] tarot.use 0','scoreboard players set @a[tag=tarot.waiting] tarot.action 0',
        'tag @a[tag=tarot.waiting,scores={tarot.cool=0}] add tarot.queued',
        'scoreboard players set #heavy_left tarot.sys 2',*['function tarot:queue/next']*8,
        'scoreboard players set @a[scores={tarot.action=5..}] tarot.action 0','scoreboard players set @a[scores={tarot.action=..-1}] tarot.action 0',
        'execute store result score #table_budget tarot.sys run gamerule '+command_rule,
        *['execute if score #table_budget tarot.sys matches 65536.. run function tarot:queue/maintenance']*8,
        'scoreboard players add #input_gc tarot.sys 1','execute if score #input_gc tarot.sys matches 200.. run function tarot:input/prune',
    ])
