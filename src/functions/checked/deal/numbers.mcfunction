function tarot:stack/validate
execute unless score #valid tarot.sys matches 1 run title @s actionbar {"text":"This stack has invalid contents. Nothing was changed.","color":"gray"}
execute unless score #valid tarot.sys matches 1 run return 0
function tarot:stack/deal
