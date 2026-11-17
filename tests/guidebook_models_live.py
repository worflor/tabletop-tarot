"""Actual item-model views in stock clients, using disposable studio displays."""
import json,time


def capture(version,rcon,xdo,work,shot,scale,inventory_left,inventory_top,recipe):
    cmd=rcon.cmd
    expected=recipe['result']['components']
    component='minecraft:custom_model_data' if 'minecraft:custom_model_data' in expected else 'minecraft:item_model'
    probe='execute if data entity Alice SelectedItem.components{'+json.dumps(component)+':'+json.dumps(expected[component])+'}'
    assert 'passed' in cmd(probe).lower(), 'Crafted guide did not retain its model identity'
    time.sleep(.5);shot(':91','guide-model-held.png')
    xdo(':91','key','e');time.sleep(.4)
    xdo(':91','mousemove',str(round(scale*(inventory_left+16))),str(round(scale*(inventory_top+150))))
    time.sleep(.5);shot(':91','guide-model-tooltip.png')
    xdo(':91','key','e');time.sleep(.2)
    # These are test studio fixtures, not a new in-world book-placement mechanic.
    cmd('fill -8 -61 -1 8 -61 7 minecraft:smooth_quartz')
    cmd('fill -8 -60 7 8 -54 7 minecraft:light_gray_concrete')
    cmd('tp Bob 20.5 -60 4.5 180 0')
    cmd('kill @e[tag=tarot_book.preview]')
    for i,(x,yaw) in enumerate([(-2.7,180),(0.,0),(2.7,35)]):
        cmd(f'summon minecraft:item_display {x} -58.8 4 {{Tags:["tarot_book.preview","tarot_book.preview_{i}"],item_display:"none",Rotation:[{float(yaw)}f,0f],transformation:{{translation:[0f,0f,0f],scale:[2.5f,2.5f,2.5f],left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f]}}}}')
        cmd(f'data modify entity @e[tag=tarot_book.preview_{i},limit=1] item set from entity Alice SelectedItem')
        cmd(f'execute store result score #book_preview_scale tarot.sys run data get entity @e[tag=tarot_book.preview_{i},limit=1] transformation.scale[0] 10')
        assert rcon.score('#book_preview_scale','tarot.sys')==25, 'Studio transform was not accepted'
    cmd('tp Alice 0.5 -59.2 0.2 0 0')
    time.sleep(.6);xdo(':91','key','F1');time.sleep(.3)
    try:shot(':91','guide-model-studio.png')
    finally:xdo(':91','key','F1')
    cmd('kill @e[tag=tarot_book.preview]')
    cmd('tp Bob 0.5 -60 4.5 180 0')
    cmd('tp Alice 0.5 -60 0.5 0 0');time.sleep(.3)
