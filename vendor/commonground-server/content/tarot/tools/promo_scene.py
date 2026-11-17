"""Photography-only scenery in the isolated world; never included in the pack."""
import json,math,pathlib,time,sys,uuid,struct,hashlib
from game_lab import RUNTIME,VanillaLane
from promo_client import send

ACTIVE=json.loads((RUNTIME/'promotion/active.json').read_text());ROOT=pathlib.Path(ACTIVE['root']);CONTROL=pathlib.Path(ACTIVE['control'])
props=dict(line.split('=',1) for line in (pathlib.Path(ACTIVE['server_dir'])/'server.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
LANE=VanillaLane.__new__(VanillaLane);LANE.rcon_port=int(props['rcon.port']);LANE.password=props['rcon.password'];LANE.commands=[]

def cmd(command):
    result=LANE.rcon(command)
    with (ROOT/'scene-commands.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps({'command':command,'result':result})+'\n')
    if any(word in result for word in ['Unknown or incomplete','Expected ','Invalid ','Unable to summon','No entity was found','Failed to ']):print(result[:500],flush=True)
    return result

def block(x,y,z,b):return cmd(f'setblock {x} {y} {z} minecraft:{b}')
def fill(x,y,z,xx,yy,zz,b):return cmd(f'fill {x} {y} {z} {xx} {yy} {zz} minecraft:{b}')

def camera(feet,focus,fov=55,settle=2):
    x,y,z=feet;fx,fy,fz=focus;yaw=math.degrees(math.atan2(-(fx-x),fz-z));pitch=math.degrees(math.atan2(y+1.62-fy,math.hypot(fx-x,fz-z)))
    cmd(f'tp CardCamera {x} {y} {z} {yaw} {pitch}');send(CONTROL,'fov',value=fov);time.sleep(settle)

def card(key,x,y,z,yaw=0,face=True):
    module=key.split('/')[0];loot=json.loads((pathlib.Path(__file__).resolve().parents[1]/f'build/java-26.3/datapack/data/tarot/loot_table/decks/{module}.json').read_text());components=loot['pools'][0]['entries'][0]['modifier']['components']
    item=next(c for c in components['minecraft:charged_projectiles'] if c['components']['minecraft:custom_data']['tarot']['key']==key)
    cmd(f'tp CardCamera {x} {y+1} {z} {yaw-180} 90');cmd('tag CardCamera add tarot.actor');cmd('data modify storage tarot:runtime chosen set value '+json.dumps({'item':item},separators=(',',':')))
    cmd(f'execute positioned {x} {y} {z} summon minecraft:item_display run function tarot:table/create');cmd('tag CardCamera remove tarot.actor')
    selector=f'@e[type=minecraft:item_display,tag=tarot.placed,sort=nearest,limit=1,x={x},y={y},z={z}]'
    if face:cmd(f'execute as {selector} at @s run function tarot:table/flip')
    return selector

def person(x,y,z,yaw=0,pose='standing'):
    profile=json.loads((RUNTIME/'promotion/skin-woflo/profile.json').read_text());p={'name':'woflo_','id':'67d58862-7e44-4d3d-8ef5-d2b88ce23f57','properties':profile['properties']}
    nbt={'Tags':['promo.person'],'profile':p,'hide_description':True,'immovable':True,'NoGravity':True,'Invulnerable':True,'Silent':True,'pose':pose,'Rotation':[float(yaw),0.0]}
    cmd('kill @e[type=minecraft:mannequin,tag=promo.person]')
    encoded=json.dumps(nbt,separators=(',',':')).replace(json.dumps(p['id']),'[I;'+','.join(str(v) for v in struct.unpack('>iiii',uuid.UUID(p['id']).bytes))+']')
    result=cmd(f'summon minecraft:mannequin {x} {y} {z} '+encoded)
    print(result,flush=True)
    # The real, unchanged deck item is generated through the production loot table.
    print(cmd('loot replace entity @e[type=minecraft:mannequin,tag=promo.person,limit=1] weapon.mainhand loot tarot:decks/rider'),flush=True)

def photo(name,title,description,feet,focus,fov=55):
    camera(feet,focus,fov,3);result=send(CONTROL,'shot',name=name);path=pathlib.Path(result['path'])
    for _ in range(100):
        if path.exists():break
        time.sleep(.1)
    entry={'file':name+'.png','title':title,'description':description,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'camera':{'feet':feet,'focus':focus,'fov':fov},'edited':False}
    with (ROOT/'photos.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(entry)+'\n')
    print('PHOTO '+name,flush=True)

def porch_photos():
    cmd('time set 3500');cmd('weather clear');person(14,103,13.4,180)
    photo('01-a-place-at-the-table','A place at the table','A sunny veranda, a deck in hand, and a few cards waiting to be turned.',[11,104.2,8],[13.8,104.4,12.5],50)
    photo('02-little-paper-worlds','Little paper worlds','Original card faces, printed backs and slender edges on an ordinary wooden table.',[12.4,104.45,9.2],[13.6,104.015,11.4],43)
    photo('03-cards-with-a-view','Cards with a view','A quiet hillside veranda overlooking the natural inlet.',[16.8,104.5,15],[13.6,104.0,11.4],58)
    cmd('time set 12500')
    photo('04-one-more-before-sunset','One more before sunset','Warm lanterns and a last few cards outside the cottage.',[10.6,104.0,8.6],[13.5,104.3,12.5],52)

def inside():
    cmd('weather clear');cmd('time set 7000')
    fill(11,103,19,13,103,20,'stripped_oak_log[axis=x]');block(11,104,20,'potted_fern');block(13,104,20,'lantern')
    block(12,103,22,'spruce_stairs[facing=north]');block(12,104,22,'spruce_trapdoor[open=true,facing=south]')
    card('rider/major-0',11.5,104.015,19.4,0,True);card('rider/major-21',12.3,104.015,19.4,8,True);card('numbers/number-7',13.1,104.015,19.4,-7,True)
    person(12.5,103,21.3,180)
    photo('05-by-the-open-window','By the window','Cards and a little greenery in a small Minecraft home.',[15.5,104.4,21.6],[12.4,104.15,19.3],57)
    photo('06-your-own-meaning','Your own meaning','Rider and Numbers cards can share the same table.',[12.0,104.7,17.9],[12.3,104.015,19.4],47)
    cmd('weather rain');cmd('time set 12500')
    photo('07-rain-check','Rain check','A window, a lantern, and no reason to go outside just yet.',[15.2,104,22.0],[12.3,104.3,19.5],55)
    cmd('weather clear')

def garden():
    fill(26,102,18,37,102,29,'grass_block');fill(26,103,18,37,112,29,'air')
    fill(29,102,20,34,102,25,'moss_block')
    fill(30,103,22,33,103,23,'stripped_oak_log[axis=x]')
    for z,facing in [(20,'south'),(25,'north')]:
        fill(30,103,z,33,103,z,f'oak_stairs[facing={facing}]')
    block(33,104,23,'potted_red_tulip');block(30,104,23,'lantern')
    for x,z,flower in [(27,19,'cornflower'),(28,26,'oxeye_daisy'),(35,21,'pink_tulip'),(36,25,'poppy'),(34,27,'allium'),(27,23,'dandelion')]:block(x,103,z,flower)
    fill(36,103,28,36,108,28,'birch_log');fill(34,107,26,38,109,30,'birch_leaves[persistent=true]');fill(35,110,27,37,110,29,'birch_leaves[persistent=true]')
    for key,x,z,yaw,face in [('rider/cups-two',30.7,22.35,5,True),('rider/pentacles-nine',31.5,22.35,-5,True),('numbers/number-3',32.3,22.35,12,True)]:card(key,x,104.015,z,yaw,face)
    person(31.6,103,24.3,180)
    cmd('summon minecraft:cat 29.5 103 24.5 {Tags:["promo.cat"],NoAI:1b,PersistenceRequired:1b,Silent:1b,Sitting:1b,variant:"minecraft:calico"}')
    cmd('time set 4500')
    photo('08-afternoon-in-the-garden','Afternoon in the garden','A handful of cards, flowers and a small curious neighbour.',[28.4,104.6,19.2],[31.5,104.0,23.0],54)
    photo('09-something-to-share','Something to share','A deck in hand at the garden table, wearing the woflo_ skin.',[29.7,104.2,20],[31.7,104.4,23.6],49)
    photo('10-small-things','Small things','Numbers and Rider artwork laid together among ordinary Minecraft materials.',[31.1,104.55,20.8],[31.6,104.015,22.4],42)
    cmd('time set 12800')
    photo('11-stay-a-little-longer','Stay a little longer','Lantern light catches the paper edges as the garden grows quiet.',[28.7,104.0,20],[31.8,104.3,23.3],50)

def waterscout():
    cmd('time set 4000');camera([0,78,-100],[0,64,-140],65,5);print(send(CONTROL,'terrain'))
    photo('water-scout','Scout','Location scout',[0,78,-100],[0,64,-140],65)

def dock():
    cmd('weather clear');cmd('time set 5000')
    fill(-8,63,-116,4,63,-114,'spruce_planks');fill(-4,63,-120,4,63,-110,'spruce_planks')
    for x in [-4,4]:
        for z in [-120,-110]:
            fill(x,57,z,x,64,z,'spruce_log');block(x,65,z,'lantern')
    fill(-3,64,-120,3,64,-120,'spruce_fence')
    fill(-2,64,-117,1,64,-116,'stripped_spruce_log[axis=x]')
    fill(-2,64,-113,0,64,-113,'spruce_stairs[facing=north]')
    block(1,65,-117,'lantern');block(-2,65,-117,'potted_oxeye_daisy')
    block(3,64,-119,'barrel');block(3,65,-119,'flower_pot')
    cmd('summon minecraft:oak_boat 5.7 62.8 -115 {Tags:["promo.boat"],Rotation:[25f,0f],Invulnerable:1b}')
    for key,x,z,yaw,face in [('rider/major-17',-1.3,-115.65,180,True),('rider/major-18',-.5,-115.65,188,True),('rider/major-19',.3,-115.65,172,False)]:card(key,x,65.015,z,yaw,face)
    person(.0,64,-118.2,0)
    photo('12-down-by-the-water','Down by the water','A little jetty makes a good place to bring a deck.',[2.5,66.1,-112.0],[-.5,65.1,-116.0],58)
    photo('13-paper-and-timber','Paper and timber','Printed faces and backs on the dockside table, with the inlet beyond.',[-2.7,65.7,-113.8],[-.5,65.02,-116.0],47)
    cmd('time set 12800')
    photo('14-the-last-light','The last light','Nothing scheduled. Just a deck and a place beside the water.',[2.3,65.6,-112.2],[-.5,65.2,-116.2],55)
    cmd('time set 13800')
    photo('15-after-the-sun-goes','After the sun goes','Lanterns keep the cards company on a quiet evening.',[-3.4,65.4,-112.4],[-.4,65.1,-116.3],56)

def retakes():
    cmd('weather clear');cmd('time set 4500');cmd('kill @e[type=minecraft:item]')
    person(16.5,103,11.8,30)
    photo('03-sea-air','Sea air','A few cards and a wide view over the natural hillside inlet.',[14.6,105.1,15.8],[13.8,104.1,11.4],58)
    person(12.5,103,21.3,180)
    # Turn the actual placed items for a readable overhead close-up.
    cmd('execute as @e[type=minecraft:item_display,tag=tarot.placed,x=12,y=104,z=19,distance=..3] at @s run tp @s ~ ~ ~ ~180 ~')
    photo('06-every-card-an-object','Every card an object','Rider and Numbers artwork, together on an ordinary tabletop.',[12.0,104.7,17.9],[12.3,104.015,19.4],47)
    photo('16-window-seat','The window seat','A deck close to hand, with the afternoon outside.',[10.4,104.0,18.0],[12.4,104.5,20.8],57)

def picnic():
    cmd('weather clear');cmd('time set 5000')
    fill(28,102,27,32,102,30,'white_wool');fill(28,102,27,32,102,27,'orange_wool');fill(28,102,30,32,102,30,'orange_wool')
    fill(28,103,27,32,104,30,'air');block(28,103,30,'lantern');block(32,103,30,'potted_cornflower')
    for key,x,z,yaw,face in [('rider/major-3',29.3,28.3,30,True),('rider/cups-ace',30.15,28.6,-10,True),('numbers/number-9',31.0,28.3,15,True)]:card(key,x,103.015,z,yaw,face)
    person(30.6,103,30.8,165,'crouching')
    cmd('tp @e[type=minecraft:cat,tag=promo.cat,limit=1] 28.0 103 28.5 90 0')
    photo('17-an-afternoon-off','An afternoon off','An ordinary wool picnic blanket is another place to lay a few cards.',[26.7,104.1,25.4],[30.1,103.45,29.1],54)
    photo('18-in-good-company','In good company','The woflo_ skin, a full deck and a quiet spot in the grass.',[28.2,103.8,25.7],[30.4,103.8,29.7],48)

def cottage():
    # Small hillside retreat, north-facing veranda looking over the natural inlet.
    fill(5,102,7,22,102,25,'grass_block');fill(5,103,7,22,115,25,'air')
    fill(7,102,9,20,102,15,'spruce_planks');fill(7,102,16,20,102,24,'cobblestone')
    fill(9,103,17,18,106,24,'white_terracotta');fill(10,103,18,17,106,23,'air')
    fill(9,102,17,18,102,24,'spruce_planks')
    for x in [9,18]:
        for z in [17,24]:fill(x,103,z,x,107,z,'stripped_spruce_log')
    for x in range(8,20):
        h=108-min(x-8,19-x)//2
        fill(x,h,16,x,h,25,'spruce_planks')
    # Roof ridge is raised toward the middle.
    for x in range(8,20):
        h=107+min(x-8,19-x)//2
        fill(x,h,16,x,h,25,'spruce_slab[type=bottom]')
    fill(11,104,17,13,105,17,'glass_pane');fill(15,104,17,17,105,17,'glass_pane')
    fill(14,103,17,14,104,17,'air');block(14,103,17,'spruce_door[half=lower,facing=north]');block(14,104,17,'spruce_door[half=upper,facing=north]')
    fill(9,104,19,9,105,21,'glass_pane');fill(18,104,19,18,105,21,'glass_pane')
    for x in [7,20]:
        for z in [9,15]:fill(x,103,z,x,103,z,'spruce_fence')
    fill(7,103,10,7,103,14,'spruce_fence');fill(20,103,10,20,103,14,'spruce_fence')
    block(8,103,9,'lantern');block(19,103,9,'lantern')
    # Veranda table at full block height, real cards rest on the same supported surface as play.
    fill(12,103,11,15,103,12,'stripped_spruce_log[axis=x]')
    for x in [12,15]:
        block(x,103,14,'spruce_stairs[facing=north]');block(x,104,14,'spruce_trapdoor[facing=south,open=true]')
    block(15,104,12,'flower_pot');block(15,104,12,'potted_azure_bluet')
    block(12,104,12,'lantern')
    # Interior: warm window bench, shelves and an ordinary crafting corner.
    fill(10,103,18,12,103,18,'spruce_planks');block(10,104,18,'potted_fern');block(12,104,18,'lantern')
    block(17,103,18,'crafting_table');fill(10,103,23,12,104,23,'bookshelf');block(13,103,23,'barrel')
    block(16,103,23,'orange_bed[facing=north,part=foot]');block(16,103,22,'orange_bed[facing=north,part=head]')
    block(17,104,23,'lantern')
    fill(14,102,7,14,102,8,'spruce_stairs[facing=south]')
    # Cottage garden, soft greenery framing the pictures, with an unobstructed sea view.
    for x,z,flower in [(6,8,'oxeye_daisy'),(21,8,'cornflower'),(6,16,'poppy'),(21,16,'oxeye_daisy'),(8,26,'pink_tulip'),(19,26,'lilac')]:
        block(x,103,z,flower)
    for x,z in [(6,18),(21,20),(6,23),(20,26)]:
        fill(x,103,z,x,104,z,'oak_leaves[persistent=true]');block(x,105,z,'oak_leaves[persistent=true]')
    # A little orchard behind the camera is useful in reverse views.
    fill(25,104,18,25,108,18,'oak_log');fill(23,108,16,27,109,20,'oak_leaves[persistent=true]');fill(24,110,17,26,110,19,'oak_leaves[persistent=true]')
    for key,x,z,yaw,face in [('rider/major-19',13.0,11.35,0,True),('rider/major-17',13.8,11.35,8,True),('rider/major-18',14.6,11.35,-10,False)]:card(key,x,104.015,z,yaw,face)
    person(14.0,103,13.4,180,'crouching')
    camera([10.7,104.5,8.0],[13.5,104.1,12.0],50)
    print('Cottage ready',flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='cottage':cottage()
    elif len(sys.argv)>1 and sys.argv[1]=='porch':porch_photos()
    elif len(sys.argv)>1 and sys.argv[1]=='inside':inside()
    elif len(sys.argv)>1 and sys.argv[1]=='garden':garden()
    elif len(sys.argv)>1 and sys.argv[1]=='water':waterscout()
    elif len(sys.argv)>1 and sys.argv[1]=='dock':dock()
    elif len(sys.argv)>1 and sys.argv[1]=='retakes':retakes()
    elif len(sys.argv)>1 and sys.argv[1]=='picnic':picnic()
    elif len(sys.argv)>1 and sys.argv[1]=='shot':print(send(CONTROL,'shot',name=sys.argv[2]))
    elif len(sys.argv)>1 and sys.argv[1]=='probe':print(send(CONTROL,'probe'))
