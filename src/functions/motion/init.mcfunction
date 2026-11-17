# Upgrade loaded older displays once, ahead of their next rotation.
data merge entity @s {teleport_duration:3}
tag @s add tarot.motion_ready
