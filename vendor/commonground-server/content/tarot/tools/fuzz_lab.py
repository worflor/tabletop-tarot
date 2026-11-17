"""Seeded real-engine gameplay fuzzing with an independent whole-item custody oracle."""
import argparse,collections,copy,json,math,random,re,time,shutil
from pathlib import Path
from game_lab import ROOT,RUNTIME,VanillaLane,write_json,sha,tarot_data,card_items,native_items,unwrap_nbt
from profiles import profile
from runtime import printed_item

def source(slot):
    return 'weapon.offhand' if slot==45 else f'hotbar.{slot-36}' if slot>=36 else f'inventory.{slot-9}'

def custom(item):
    value=unwrap_nbt(item or {});components=value.get('components') or {}
    if isinstance(components,list):components={str(c['type']):c.get('data') for c in components}
    return components.get('minecraft:custom_data',components.get('custom_data',{}))

def serials(item):
    values=[custom(card).get('fuzz_serial') for card in native_items(item)]
    if any(type(v) is not int for v in values):raise AssertionError('Observer could not identify a native card instance')
    return values

def run(lane,peer,seed,steps,result):
    rng=random.Random(seed);spec=profile(lane.version);n=24
    function_dir='functions' if spec['plural_paths'] else 'function';loot_dir='loot_tables' if spec['plural_paths'] else 'loot_table'
    base=lane.world_dir/'datapacks/tarot/data/tarot';folder=base/function_dir/'lab/fuzz';folder.mkdir(parents=True,exist_ok=True)
    def fixture(name,lines):(folder/(name+'.mcfunction')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    catalogue=json.loads((lane.pack.parent/'catalogue.json').read_text())['cards']
    notes=['A keepsake — café "moon"\n谢谢','\\\"} run scoreboard players set #injected tarot_fuzz 1\n#','🌙\u200d☀\ufe0f\u202e  a  b','', 'line\r\nnext\tend']
    cards=[]
    for i in range(n):
        card=printed_item(rng.choice(catalogue),lane.version);components=card['components']
        components['minecraft:custom_data'].update({'fuzz_serial':i,'kept_note':rng.choice(notes),'nested':{'ints':[i,-i,0],'flag':True}})
        name={'text':f'{i}: '+rng.choice(notes),'color':rng.choice(['gold','aqua','white']),'italic':bool(i%2)}
        lore=[{'text':rng.choice(notes),'italic':False},{'text':str(i),'color':'gray'}]
        components['minecraft:custom_name']=name if spec['text_objects'] else json.dumps(name,ensure_ascii=False)
        components['minecraft:lore']=lore if spec['text_objects'] else [json.dumps(v,ensure_ascii=False) for v in lore]
        components['minecraft:repair_cost']=rng.randrange(30);components['minecraft:enchantment_glint_override']=bool(i%3==0)
        defaults=[('minecraft:repair_cost',0),('minecraft:damage',0),('minecraft:lore',[]),('minecraft:rarity','common'),('minecraft:enchantments',{} if spec['text_objects'] else {'levels':{}}),('minecraft:attribute_modifiers',[] if spec['text_objects'] else {'modifiers':[]})]
        if i<6:components[defaults[i][0]]=defaults[i][1]
        cards.append(card)
    for index,(actor,module) in enumerate([('TarotLab','numbers'),('TarotPeer','rider')]):
        loot=json.loads((lane.pack/f'data/tarot/{loot_dir}/decks/{module}.json').read_text())
        entry=loot['pools'][0]['entries'][0];modifier=entry['modifier'] if lane.version=='26.3' else entry['functions'][0]
        modifier['components']['minecraft:charged_projectiles']=cards[index*12:(index+1)*12]
        modifier['components']['minecraft:custom_data']['band_note']=f'Keep band {index}'
        path=base/loot_dir/f'lab/fuzz/{index}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(loot,ensure_ascii=False),encoding='utf-8')
    fixture('swap',[
        '$item replace block 12 -60 0 container.0 from entity @s $(destination)',
        '$item replace entity @s $(destination) from entity @s $(source)',
        '$item replace entity @s $(source) from block 12 -60 0 container.0',
        'item replace block 12 -60 0 container.0 with minecraft:air',
    ])
    fixture('trade',[
        '$execute if items entity $(recipient) $(destination) * run return 0',
        '$item replace entity $(recipient) $(destination) from entity @s $(source)',
        '$item replace entity @s $(source) with minecraft:air',
    ])
    # The oracle reads canonical items on the server. Protocol display decoding
    # never decides whether an annotation survived or a physical card exists.
    fixture('player',['data modify storage tarot_fuzz:audit entries append from entity @s Inventory[]',
        *([] if spec['offhand_components'].startswith('Inventory') else ['data modify storage tarot_fuzz:audit entries append from entity @s equipment.offhand'])])
    fixture('audit',[
        'scoreboard players set #bad tarot_fuzz 0','execute unless score #injected tarot_fuzz matches 0 run scoreboard players add #bad tarot_fuzz 1',
        *[f'scoreboard players set #s{i} tarot_fuzz 0' for i in range(n)],
        'data modify storage tarot_fuzz:audit entries set value []',
        'execute as @a[tag=tarot_fuzz.actor] run function tarot:lab/fuzz/player',
        'execute as @e[type=minecraft:item_display,tag=tarot.placed] run data modify storage tarot_fuzz:audit entries append from entity @s item',
        'execute as @e[type=minecraft:item] run data modify storage tarot_fuzz:audit entries append from entity @s Item',
        'data modify storage tarot_fuzz:audit entries append from block 12 -60 0 Items[]',
        'function tarot:lab/fuzz/scan',
        *[f'execute unless score #s{i} tarot_fuzz matches 1 run scoreboard players add #bad tarot_fuzz 1' for i in range(n)],
        'execute if entity @e[tag=tarot.transfer] run scoreboard players add #bad tarot_fuzz 1',
        'execute if entity @e[type=minecraft:marker] run scoreboard players add #bad tarot_fuzz 1',
        'scoreboard players set #audit_done tarot_fuzz 1',
    ])
    fixture('scan',[
        'execute unless data storage tarot_fuzz:audit entries[0] run return 0',
        'data modify storage tarot_fuzz:audit item set from storage tarot_fuzz:audit entries[0]',
        'data remove storage tarot_fuzz:audit entries[0]',
        'execute if data storage tarot_fuzz:audit item.components."minecraft:custom_data".tarot{kind:"deck"} run data modify storage tarot_fuzz:audit entries append from storage tarot_fuzz:audit item.components."minecraft:charged_projectiles"[]',
        'execute if data storage tarot_fuzz:audit item.components."minecraft:custom_data".tarot{kind:"card"} run function tarot:lab/fuzz/card',
        'function tarot:lab/fuzz/scan',
    ])
    fixture('card',[
        'data modify storage tarot_fuzz:audit args set value {}',
        'data modify storage tarot_fuzz:audit args.serial set from storage tarot_fuzz:audit item.components."minecraft:custom_data".fuzz_serial',
        'execute unless data storage tarot_fuzz:audit args.serial run scoreboard players add #bad tarot_fuzz 1',
        'execute if data storage tarot_fuzz:audit args.serial run function tarot:lab/fuzz/compare with storage tarot_fuzz:audit args',
    ])
    fixture('compare',[
        '$execute unless data storage tarot_fuzz:oracle s$(serial) run scoreboard players add #bad tarot_fuzz 1',
        'scoreboard players set #quantity tarot_fuzz 1',
        'execute if data storage tarot_fuzz:audit item.count store result score #quantity tarot_fuzz run data get storage tarot_fuzz:audit item.count',
        '$scoreboard players operation #s$(serial) tarot_fuzz += #quantity tarot_fuzz',
        'execute as @e[type=minecraft:armor_stand,tag=tarot_fuzz.codec,limit=1] run function tarot:lab/fuzz/canonical',
        '$execute store success score #different tarot_fuzz run data modify storage tarot_fuzz:audit compare set from storage tarot_fuzz:oracle s$(serial).components',
        'execute if score #different tarot_fuzz matches 1 run scoreboard players add #bad tarot_fuzz 1',
    ])
    equipment='ArmorItems[3]' if spec['offhand_components'].startswith('Inventory') else 'equipment.head'
    fixture('canonical',[
        f'data modify entity @s {equipment} set from storage tarot_fuzz:audit item',
        'execute unless items entity @s armor.head #tarot:card_carriers[minecraft:count=1] run scoreboard players add #bad tarot_fuzz 1',
        f'data modify storage tarot_fuzz:audit compare set from entity @s {equipment}.components',
        'item replace entity @s armor.head with minecraft:air',
    ])
    fixture_bytes={p.relative_to(base):p.read_bytes() for p in base.rglob('*') if p.is_file() and '/lab/' in '/'+p.relative_to(base).as_posix()}
    lane.rcon('reload');time.sleep(.5);lane.rcon('scoreboard objectives add tarot_fuzz dummy');lane.rcon('scoreboard players set #injected tarot_fuzz 0')
    lane.rcon('setblock 12 -60 0 minecraft:chest');lane.rcon('fill -4 -60 -4 9 -56 7 minecraft:air')
    lane.rcon('summon minecraft:armor_stand 12 -59 0 {Tags:["tarot_fuzz.codec"],Invisible:1b,Marker:1b,NoGravity:1b,Invulnerable:1b}')
    for index,client in enumerate([lane,peer]):
        name=client.player_name;lane.rcon('clear '+name);lane.rcon('tag '+name+' add tarot_fuzz.actor')
        lane.rcon(f'loot replace entity {name} hotbar.0 loot tarot:lab/fuzz/{index}');client.client_action('hold',slot=0)
        lane.rcon(f'tp {name} {index*4+.5} -60 0.5 0 20');lane.rcon('gamemode survival '+name);lane.rcon('deop '+name)
        for i in range(12):
            lane.rcon(f'data modify storage tarot_fuzz:audit item set from entity {name} SelectedItem.components."minecraft:charged_projectiles"[{i}]')
            lane.rcon('execute as @e[type=minecraft:armor_stand,tag=tarot_fuzz.codec,limit=1] run function tarot:lab/fuzz/canonical')
            lane.rcon(f'data modify storage tarot_fuzz:oracle s{index*12+i}.components set from storage tarot_fuzz:audit compare')
    def audit(step):
        lane.rcon('scoreboard players set #bad tarot_fuzz -1');lane.rcon('scoreboard players set #audit_done tarot_fuzz 0')
        lane.rcon('function tarot:lab/fuzz/audit');value=lane.rcon('scoreboard players get #bad tarot_fuzz')
        if 'has 1 ' not in lane.rcon('scoreboard players get #audit_done tarot_fuzz'):raise AssertionError('Whole-item oracle did not complete: '+str(step))
        if 'has 0 ' not in value:
            lane.rcon('data get storage tarot_fuzz:audit');lane.rcon('scoreboard players list')
            raise AssertionError(f'Whole-item conservation/annotation oracle failed at step {step}: '+value)
        result['audits']+=1
    def snap(client):return client.client_action('snapshot')
    def equip(client,item):
        slot=item['slot']
        if slot>=36 and slot<45:client.client_action('hold',slot=slot-36)
        else:
            client.client_action('hold',slot=0)
            lane.rcon(f'execute as {client.player_name} run function tarot:lab/fuzz/swap '+json.dumps({'source':source(slot),'destination':'weapon.mainhand'}))
    def cool(client):lane.rcon('scoreboard players set '+client.player_name+' tarot.cool 0')
    audit(-1)
    forced=['draw','draw','shuffle','return','place','pickup','drop','trade','reload','reconnect','restart']
    for step in range(steps):
        client=rng.choice([lane,peer]);state=snap(client);items=state['items']
        decks=[i for i in items if (tarot_data(i) or {}).get('kind')=='deck'];loose=[i for i in items if (tarot_data(i) or {}).get('kind')=='card']
        operation=forced[step] if step<len(forced) else rng.choices(['draw','shuffle','return','place','pickup','drop','trade','reload','reconnect','restart','fall'],[22,15,18,15,12,4,8,2,1,1,4])[0]
        event={'step':step,'player':client.player_name,'operation':operation};result['trace'].append(event)
        if operation in {'draw','shuffle','return'} and decks:
            equip(client,rng.choice(decks));cool(client);held=snap(client)['held'];before=serials(held);band=custom(held)['band_note'];returned=None
            loose=[item for item,_ in card_items(snap(client))]
            if operation=='return' and loose:
                chosen=rng.choice(loose)
                returned=custom(chosen)['fuzz_serial']
                if chosen['slot']!=45:lane.rcon(f'execute as {client.player_name} run function tarot:lab/fuzz/swap '+json.dumps({'source':source(chosen['slot']),'destination':'weapon.offhand'}))
            after=client.client_action('chat',text='/trigger tarot.action set '+str({'draw':1,'shuffle':2,'return':3}[operation]))['snapshot']
            actual=serials(after['held'])
            event.update(before=before,after=actual,returned=returned)
            if custom(after['held']).get('band_note')!=band:raise AssertionError('Band annotations changed')
            if operation=='draw' and actual!=before[1:]:raise AssertionError('Valid top draw refused or changed order')
            if operation=='return' and returned is not None and actual!=[returned]+before:raise AssertionError('Valid return refused or changed order')
            if operation=='shuffle' and sorted(actual)!=sorted(before):raise AssertionError('Shuffle changed whole-instance membership')
            result['transitions'][operation]+=1
        elif operation=='place' and loose:
            chosen=rng.choice(loose);equip(client,chosen);cool(client);x=rng.randrange(-2,8)
            block=rng.choice(['oak_planks','stone','oak_slab[type=bottom]','oak_slab[type=top]','glass','barrel'])
            lane.rcon(f'setblock {x} -60 2 minecraft:{block}');lane.rcon(f'tp {client.player_name} {x+.5} -60 0.5 0 '+('35' if 'bottom' in block else '20'))
            event.update(x=x,block=block);client.client_action('chat',text='/trigger tarot.action set 4')
        elif operation=='pickup':
            observed=[e for e in client.client_action('entities')['entities'] if e['name']=='interaction']
            if observed:
                target=rng.choice(observed);p=target['position'];lane.rcon(f'tp {client.player_name} {p["x"]} -60 {p["z"]-1.5}');cool(client)
                client.client_action('touch',uuid=target['uuid'],attack=True)
        elif operation=='drop' and loose:
            client.client_action('drop',slot=rng.choice(loose)['slot'])
        elif operation=='trade' and (decks or loose):
            recipient=peer if client is lane else lane;other=snap(recipient);occupied={i['slot'] for i in other['items']};empty=next((i for i in range(36,45) if i not in occupied),None)
            if empty is not None:
                chosen=rng.choice(decks+loose);event.update(source=source(chosen['slot']),recipient=recipient.player_name,destination=source(empty))
                lane.rcon(f'execute as {client.player_name} run function tarot:lab/fuzz/trade '+json.dumps({'source':source(chosen['slot']),'recipient':recipient.player_name,'destination':source(empty)}))
        elif operation=='reload':lane.rcon('reload');time.sleep(.2)
        elif operation=='reconnect':
            name=client.player_name;client.client_action('quit');client.client_process.wait(timeout=10);client.client_process=None;client.start_player(name)
            lane.rcon('gamemode survival '+name);lane.rcon('deop '+name)
        elif operation=='restart':
            for actor in [lane,peer]:actor.client_action('quit');actor.client_process.wait(timeout=10);actor.client_process=None
            lane.stop();lane.process=None;lane.log=None;lane.start();lane.start_player('TarotLab');peer.start_player('TarotPeer')
            for relative,data in fixture_bytes.items():
                path=base/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            lane.rcon('reload');time.sleep(.2)
            for actor in [lane,peer]:lane.rcon('gamemode survival '+actor.player_name);lane.rcon('deop '+actor.player_name)
        elif operation=='fall':lane.rcon(f'setblock {rng.randrange(-2,8)} -60 2 minecraft:air');time.sleep(.2)
        audit(step);result['operations'][operation]+=1
        if step%25==0:print(json.dumps({'seed':seed,'step':step,'audits':result['audits']}),flush=True)
    if hasattr(lane,'check_fixtures'):lane.check_fixtures()
    result['checks'].append({'name':'seeded_whole_item_custody_and_annotation_conservation','passed':True,'cards':n,'steps':steps,'audits':result['audits']})

def main(version,seed,steps,adapter=False):
    from universal_lab import ZipLane
    lane=VanillaLane(version) if adapter else ZipLane(version)
    run_root=RUNTIME/'fuzz-runs'/f'{version}-{seed}-{time.time_ns()}';run_root.mkdir(parents=True,exist_ok=True)
    lane.server_dir=run_root/'server';lane.world_dir=lane.server_dir/lane.world_name
    # Each invocation freezes its actual production bytes. Rebuilds and another
    # run of the same seed cannot change a restart's pack or server properties.
    source_output=lane.pack.parent;shutil.copytree(lane.pack,run_root/'adapter/datapack');shutil.copyfile(source_output/'catalogue.json',run_root/'adapter/catalogue.json')
    lane.pack=run_root/'adapter/datapack'
    if not adapter:
        shutil.copyfile(lane.archive,run_root/lane.archive.name);lane.archive=run_root/lane.archive.name
    peer=VanillaLane(version);peer.game_port,peer.rcon_port,peer.password=lane.game_port,lane.rcon_port,lane.password
    result={'minecraft':version,'scope':'Seeded two-player vanilla-engine state machine; independent live-ItemStack canonical component comparison and global unique-instance conservation after every action','seed':seed,'steps_requested':steps,'checks':[],'trace':[],'operations':collections.Counter(),'transitions':collections.Counter(),'audits':0}
    if not adapter:result['combined_zip_sha256']=sha(lane.archive)
    else:result['datapack_sha256']={p.relative_to(lane.pack).as_posix():sha(p) for p in lane.pack.rglob('*') if p.is_file()}
    result['fuzzer_source_sha256']=sha(Path(__file__))
    try:
        lane.download_server();lane.start();lane.start_player('TarotLab');peer.start_player('TarotPeer');run(lane,peer,seed,steps,result);result['passed']=True
    except Exception as error:
        result['passed']=False;result['error']=repr(error)
        for command in ['data get storage tarot:decoded','data get storage tarot:runtime chosen','scoreboard players get #ready tarot.sys','scoreboard players get #different tarot.sys']:
            try:lane.rcon(command)
            except Exception:pass
        raise
    finally:
        peer.stop();lane.stop();result['commands']=lane.commands+peer.commands;result['protocol_lines']=lane.client_lines+peer.client_lines
        write_json(ROOT/f'content/tarot/evidence/fuzz-{version}-{seed}.json',result)
    print(json.dumps({'passed':True,'version':version,'seed':seed,'audits':result['audits']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='1.21.11');p.add_argument('--seed',type=int,default=671083);p.add_argument('--steps',type=int,default=200);p.add_argument('--adapter',action='store_true');a=p.parse_args();main(a.version,a.seed,a.steps,a.adapter)
