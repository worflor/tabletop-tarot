"""Owned vanilla-engine checks for selected modules and nine-player queue pressure."""
import json,os,subprocess,time
from pathlib import Path
from build import build
from game_lab import VanillaLane,write_json,sha,deck_item,card_keys,card_items,NODE,NODE_CLIENTS

ROOT=Path(__file__).resolve().parents[1]

def supplemental_lane(version):
    lane=VanillaLane(version)
    lane.server_dir=lane.server_dir.with_name('supplemental-'+version)
    lane.world_dir=lane.server_dir/lane.world_name
    return lane

def subset(version,module,bundle=None):
    if bundle is None:output=build(version,[module]);lane=supplemental_lane(version)
    else:
        from universal_lab import ZipLane
        output=ROOT/('build/java-'+version+'-'+module);lane=ZipLane(version,bundle)
        lane.server_dir=lane.server_dir.with_name('universal-subset-'+version+'-'+module);lane.world_dir=lane.server_dir/lane.world_name
    lane.pack=output/'datapack'
    result={'minecraft':version,'scope':'single selected module on official vanilla server'+('; production only from combined ZIP' if bundle is not None else ''),'module':module}
    if bundle is not None:result['combined_zip_sha256']=sha(lane.archive)
    try:
        lane.download_server();lane.start();lane.start_player()
        result['datapack_sha256']={p.relative_to(lane.pack).as_posix():sha(p) for p in lane.pack.rglob('*') if p.is_file()}
        lane.player_function('tarot:give/'+module);lane.client_action('hold',slot=0)
        count={'rider':78,'numbers':12}[module]
        state=lane.wait_state(lambda s:deck_item(s,module) is not None,'selected module')
        original=card_keys(deck_item(state,module))
        if len(original)!=count:raise AssertionError('Wrong selected deck size')
        lane.client_action('use');state=lane.wait_state(lambda s:len(card_keys(deck_item(s,module)))==count-1 and len(card_items(s,module))==1,'subset native draw')
        if len(card_keys(deck_item(state,module)))!=count-1 or len(card_items(state,module))!=1:raise AssertionError('Subset draw failed')
        before=card_keys(deck_item(state,module));changed=False
        for _ in range(3):
            state=lane.client_action('chat',text='/trigger tarot.action set 2')['snapshot']
            after=card_keys(deck_item(state,module))
            if sorted(after)!=sorted(before):raise AssertionError('Subset shuffle changed membership')
            if after!=before:changed=True;break
        if not changed:raise AssertionError('Subset shuffle did not permute')
        card=card_items(state,module)[0][0];slot=card['slot']
        source='hotbar.'+str(slot-36) if slot>=36 else 'inventory.'+str(slot-9)
        lane.rcon(f'item replace entity TarotLab weapon.offhand from entity TarotLab {source}')
        lane.rcon(f'item replace entity TarotLab {source} with minecraft:air')
        lane.client_action('chat',text='/trigger tarot.action set 3');state=lane.wait_state(lambda s:not s.get('offhand') and len(card_keys(deck_item(s,module)))==count,'subset native return')
        if sorted(card_keys(deck_item(state,module)))!=sorted(original) or state.get('offhand'):raise AssertionError('Subset return failed')
        other=({'rider','numbers'}-{module}).pop()
        absent=lane.rcon('function tarot:give/'+other)
        if 'Unknown function' not in absent:raise AssertionError('Omitted module still available: '+absent)
        result['checks']=[{'name':'selected_module_draw_shuffle_return','passed':True,'cards':count},{'name':'omitted_module_absent_in_engine','passed':True}];result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines
        write_json(ROOT/'evidence'/f'{"universal-" if bundle is not None else ""}subset-{version}-{module}.json',result)

def crowd(pressure=False):
    lane=supplemental_lane('1.21.11');result={'minecraft':lane.version,'scope':'nine actual protocol players; continuous shuffle requests; fixture resets cooldown to maximize pressure','pressure':pressure};client=None
    try:
        lane.download_server();lane.start()
        result['datapack_sha256']={p.relative_to(lane.pack).as_posix():sha(p) for p in lane.pack.rglob('*') if p.is_file()}
        script=lane.server_dir/'crowd-player.cjs'
        script.write_text('''const mf=require('mineflayer');const bots=[];function unwrap(v){if(v&&typeof v==='object'){if('type'in v&&'value'in v)return unwrap(v.value);if(Array.isArray(v))return v.map(unwrap);return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,unwrap(x)]));}return v;}function data(item){const c=item?.components?.find(c=>String(c.type).endsWith('custom_data'));return c?unwrap(c.data):{};}async function main(){for(let i=0;i<9;i++){const b=mf.createBot({host:'127.0.0.1',port:Number(process.argv[2]),username:'TarotCrowd'+i,version:'1.21.11',auth:'offline'});bots.push(b);b.on('error',e=>{console.error(e);process.exitCode=1});await new Promise((r,j)=>{b.once('spawn',r);b.once('kicked',j);b.once('error',j)});}console.log('READY');}main().catch(e=>{console.error(e);process.exit(1)});process.stdin.on('data',async raw=>{if(String(raw).trim()==='snapshot'){await bots[0].waitForTicks(2);console.log('SNAPSHOT '+JSON.stringify(bots.map(b=>({name:b.username,keys:(b.heldItem?.components?.find(c=>String(c.type)==='charged_projectiles')?.data?.projectiles||[]).map(c=>data(c)?.tarot?.key),serials:b.inventory.items().map(i=>data(i).pressure_serial).filter(x=>Number.isInteger(x))}))));return;}for(const b of bots)b.quit();setTimeout(()=>process.exit(0),500)});''',encoding='utf-8')
        env=os.environ.copy();env['NODE_PATH']=str(NODE_CLIENTS/'node_modules')
        client=subprocess.Popen([NODE,str(script),str(lane.game_port)],cwd=NODE_CLIENTS,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        import queue,threading
        lines=queue.Queue()
        def reader():
            for line in client.stdout:lines.put(line.rstrip())
        threading.Thread(target=reader,daemon=True).start()
        tape=[];deadline=time.monotonic()+100
        while True:
            if time.monotonic()>deadline:raise TimeoutError('Nine clients did not connect: '+str(tape[-10:]))
            try:line=lines.get(timeout=.5)
            except queue.Empty:continue
            tape.append(line)
            if line=='READY':break
        result['protocol_lines']=tape
        lane.rcon('scoreboard objectives add tarot_lab dummy')
        dp=lane.world_dir/'datapacks/tarot';fixture=dp/'data/tarot_lab/function';fixture.mkdir(parents=True)
        if pressure:
            from runtime import printed_item
            catalogue=json.loads((lane.pack.parent/'catalogue.json').read_text());paper=printed_item(next(c for c in catalogue['cards'] if c['key']=='numbers/number-33'),lane.version)
            deck=json.loads((lane.pack/'data/tarot/recipe/rider_deck.json').read_text())['result']['components'];rows=deck['minecraft:charged_projectiles'];rows.extend(rows[:50])
            encoded=','.join(k if k.startswith('!') else k+'='+json.dumps(v,separators=(',',':')) for k,v in deck.items())
            (fixture/'give128.mcfunction').write_text('give @s minecraft:carrot_on_a_stick['+encoded+'] 1\n')
            spawn=['fill -5 -60 -5 5 -60 5 minecraft:oak_planks','tp @a 0.5 -59 0.5']
            for serial in range(144):
                item=json.loads(json.dumps(paper));item['components']['minecraft:custom_data']['pressure_serial']=serial
                spawn.append('summon minecraft:item_display '+str(-3.6+.65*(serial%12))+' -58.979 '+str(-3.6+.65*(serial//12))+' '+json.dumps({'Tags':['tarot.placed','pressure.fixture'],'item':item},separators=(',',':')))
            (fixture/'spawn144.mcfunction').write_text('\n'.join(spawn)+'\n');lane.rcon('reload');time.sleep(.5);lane.rcon('function tarot_lab:spawn144')
        for i in range(9):
            name='TarotCrowd'+str(i)
            lane.rcon(f'execute as {name} run function '+('tarot_lab:give128' if pressure else 'tarot:give/rider'))
            lane.rcon(f'execute store result score #fixture_size tarot_lab run data get entity {name} SelectedItem.components."minecraft:charged_projectiles"')
            if f'has {128 if pressure else 78} ' not in lane.rcon('scoreboard players get #fixture_size tarot_lab'):raise AssertionError('Crowd participant did not receive a complete actual deck: '+name)
            lane.rcon(f'scoreboard players set {name} tarot_lab 0')
        lane.rcon('scoreboard players set #ticks tarot_lab 0');lane.rcon('scoreboard players set #max tarot_lab 0');lane.rcon('scoreboard players set #run tarot_lab 0')
        pulse=['execute unless score #run tarot_lab matches 1 run return 0','scoreboard players set @a tarot.cool 0','scoreboard players set @a tarot.action 2']
        observe=['execute unless score #run tarot_lab matches 1 run return 0','scoreboard players add #ticks tarot_lab 1','scoreboard players set #served tarot_lab 0','execute as @a[scores={tarot.cool=2}] run scoreboard players add #served tarot_lab 1','scoreboard players add @a[scores={tarot.cool=2}] tarot_lab 1','execute if score #served tarot_lab > #max tarot_lab run scoreboard players operation #max tarot_lab = #served tarot_lab','execute if score #ticks tarot_lab matches 80.. run scoreboard players set #run tarot_lab 0']
        if pressure:
            pulse.insert(1,'execute if score #ticks tarot_lab matches 0 run fill -5 -60 -5 5 -60 5 minecraft:air')
            observe[2:2]=['execute store result score #roots_left tarot_lab run execute if entity @e[tag=pressure.fixture]','scoreboard players operation #fell tarot_lab = #previous_roots tarot_lab','scoreboard players operation #fell tarot_lab -= #roots_left tarot_lab','scoreboard players operation #max_fall tarot_lab > #fell tarot_lab','scoreboard players operation #previous_roots tarot_lab = #roots_left tarot_lab']
            lane.rcon('scoreboard players set #previous_roots tarot_lab 144');lane.rcon('scoreboard players set #max_fall tarot_lab 0')
        (fixture/'pulse.mcfunction').write_text('\n'.join(pulse)+'\n');(fixture/'observe.mcfunction').write_text('\n'.join(observe)+'\n')
        tag=dp/'data/minecraft/tags/function/tick.json';tag.write_text(json.dumps({'values':['tarot_lab:pulse','tarot:tick','tarot_lab:observe']}))
        result['fixture']={'pulse':pulse,'observe':observe,'tick_order':['tarot_lab:pulse','tarot:tick','tarot_lab:observe']}
        lane.rcon('reload');time.sleep(1)
        if pressure:
            # Wait until bounded registration has assigned all legacy fixture IDs.
            deadline=time.monotonic()+30
            while 'Test passed' in lane.rcon('execute if entity @e[tag=pressure.fixture,tag=!tarot.registered]'):
                if time.monotonic()>deadline:raise TimeoutError('Pressure roots not registered')
                time.sleep(.2)
        began=time.monotonic();lane.rcon('scoreboard players set #run tarot_lab 1')
        deadline=time.monotonic()+90
        while 'has 0 ' not in lane.rcon('scoreboard players get #run tarot_lab'):
            if time.monotonic()>deadline:raise TimeoutError('Queue stress did not finish')
            time.sleep(.5)
        result['elapsed_until_80_ticks_observed_seconds']=round(time.monotonic()-began,3)
        result['server_tick_query']=lane.rcon('tick query')
        import re
        def score(name):
            response=lane.rcon(f'scoreboard players get {name} tarot_lab');match=re.search(r'has (-?\d+) ',response)
            if not match:raise AssertionError(response)
            return int(match.group(1))
        counts={f'TarotCrowd{i}':score(f'TarotCrowd{i}') for i in range(9)};maximum=score('#max');ticks=score('#ticks')
        if min(counts.values())<10 or max(counts.values())-min(counts.values())>2 or maximum!=2 or ticks!=80:raise AssertionError({'counts':counts,'max':maximum,'ticks':ticks})
        # Read actual protocol inventories, not nested-key regex matches.
        client.stdin.write('snapshot\n');client.stdin.flush();snapshot=None;deadline=time.monotonic()+20
        while snapshot is None:
            if time.monotonic()>deadline:raise TimeoutError('Crowd inventory receipt missing')
            try:line=lines.get(timeout=.5)
            except queue.Empty:continue
            tape.append(line)
            if line.startswith('SNAPSHOT '):snapshot=json.loads(line[len('SNAPSHOT '):])
        sizes={};expected=[c['key'] for c in json.loads((lane.pack.parent/'catalogue.json').read_text())['cards'] if c['module']=='rider']
        if pressure:expected+=expected[:50]
        for player in snapshot:
            keys=player['keys'];sizes[player['name']]=len(keys)
            if sorted(keys)!=sorted(expected) or keys==expected:raise AssertionError('Crowd deck lost membership or never shuffled: '+player['name'])
        if set(sizes.values())!={128 if pressure else 78}:raise AssertionError(sizes)
        lane.check_log(Path(lane.starts[0]['log']).read_text(encoding='utf-8',errors='replace'))
        result['checks']=[{'name':'nine_player_continuous_queue_fairness','passed':True,'turns_by_player':counts,'ticks':ticks,'max_actions_per_tick':maximum},{'name':'nine_shuffled_decks_keep_instances','passed':True,'sizes':sizes,'exact_membership_and_changed_order':True}]
        if pressure:
            from collections import Counter
            world=lane.rcon('execute as @e[type=minecraft:item] run data get entity @s Item')
            serials=[n for player in snapshot for n in player['serials']]+[int(x) for x in re.findall(r'pressure_serial: (\d+)',world)]
            if Counter(serials)!=Counter(range(144)):raise AssertionError('Pressure item conservation failed: '+str(Counter(serials)))
            if 'Test passed' in lane.rcon('execute if entity @e[tag=pressure.fixture]'):raise AssertionError('Surface queue did not drain')
            max_fall=score('#max_fall')
            if not 1<=max_fall<=8:raise AssertionError('Surface maintenance exceeded8 transfers per tick')
            result['checks'].append({'name':'144_falling_instances_conserved_during_nine_full_stack_shuffles','passed':True,'unique_items':144,'max_falling_transfers_per_tick':max_fall,'counts':dict(Counter(serials))})
        result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        if client and client.poll() is None:
            client.stdin.write('stop\n');client.stdin.flush()
            try:client.wait(timeout=10)
            except subprocess.TimeoutExpired:client.kill();client.wait()
        lane.stop();result['commands']=lane.commands
        write_json(ROOT/'evidence'/('pressure-1.21.11.json' if pressure else 'crowd-1.21.11.json'),result)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--pressure',action='store_true');args=parser.parse_args()
    if args.pressure:crowd(True)
    else:subset('1.20.6','rider');subset('1.21.11','numbers');crowd()
