"""Narrow stock-client resource/backend proof where the pinned protocol observer has no implementation."""
import argparse,json,os,pathlib,shutil,subprocess,time,re,zipfile
from game_lab import RUNTIME,ROOT,sha,write_json
from universal_lab import ZipLane
from native_backend_lab import main as backend

def main(version,resources_only=False,bundle=None,receipt_prefix='universal',visual_hold=False,extra_resources=(),cards_below=False,use_probe=False):
    if use_probe and version!='26.3':raise ValueError('The reflection-only client dispatch probe currently covers 26.3')
    if not re.fullmatch(r'[a-z0-9-]+',receipt_prefix):raise ValueError('Unsafe receipt prefix')
    lane=ZipLane(version,bundle);client=None
    lane.server_dir=RUNTIME/(receipt_prefix+'-server-'+version);lane.world_dir=lane.server_dir/lane.world_name
    folder=RUNTIME/(receipt_prefix+'-client-'+version);game=folder/'game';game.mkdir(parents=True,exist_ok=True)
    resources=game/'resourcepacks';resources.mkdir(exist_ok=True);shutil.copyfile(lane.archive,resources/lane.archive.name)
    additional=[]
    for i,path in enumerate(extra_resources):
        path=pathlib.Path(path);name=f'external-{i}-'+path.name;shutil.copyfile(path,resources/name);additional.append('file/'+name)
    base=RUNTIME/('client-'+version)
    from visual_client import prepare
    prepare(version)
    with zipfile.ZipFile(base/'client.jar') as client_jar:options_version=json.loads(client_jar.read('version.json'))['world_version']
    command=json.loads((base/'launch.json').read_text(encoding='utf-8'))
    command[command.index('--username')+1]='TarotVisual'
    command=[value for value in command if not value.startswith('-XX:ActiveProcessorCount=')]
    command.insert(1,'-XX:ActiveProcessorCount=2')
    if use_probe:
        from client_dispatch_lab import prepare
        agent_argument,probe_control,probe_agent=prepare(folder);command.insert(1,agent_argument)
    for flag,value in [('--gameDir',str(game)),('--quickPlayMultiplayer','PLACEHOLDER')]:
        if flag in command:command[command.index(flag)+1]=value
        else:command += [flag,value]
    # These arguments are ignored by current vanilla clients, so don't imply that they select a renderer.
    for flag in ['--graphics-api','--userType']:
        if flag in command:
            i=command.index(flag);del command[i:i+2]
    pack_order=['vanilla']+(['file/Tabletop-Tarot-Universal.zip']+additional if cards_below else additional+['file/Tabletop-Tarot-Universal.zip'])
    (game/'options.txt').write_text('version:'+str(options_version)+'\nresourcePacks:'+json.dumps(pack_order)+'\nincompatibleResourcePacks:[]\npauseOnLostFocus:false\nonboardAccessibility:false\nrenderDistance:3\nsimulationDistance:3\nmaxFps:30\nsoundCategory_master:0.0\n',encoding='utf-8')
    if visual_hold:
        with (game/'options.txt').open('a',encoding='utf-8') as options:options.write('toggleCrouch:true\ntutorialStep:none\nkey_key.use:key.keyboard.r\nkey_key.attack:key.keyboard.g\n')
    log=folder/('client-'+str(time.time_ns())+'.log');result={'minecraft':version,'scope':'Unmodified stock client launched with the same combined ZIP enabled; RCON backend probes, no native input claim','combined_zip_sha256':sha(lane.archive),'checks':[]}
    if use_probe:
        result['scope']='Vanilla client with an isolated reflection-only test agent for main-thread Use dispatch; production pack bytes; no OS input claim'
        result['test_agent']=probe_agent
    result['resource_order']=pack_order;result['external_resources']=[{'file':str(p),'sha256':sha(pathlib.Path(p))} for p in extra_resources]
    try:
        lane.download_server();lane.start();command[command.index('--quickPlayMultiplayer')+1]='127.0.0.1:'+str(lane.game_port)
        startup=subprocess.STARTUPINFO() if os.name=='nt' else None
        if startup is not None:startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=4 if visual_hold or use_probe else 7
        with log.open('wb') as output:
            client=subprocess.Popen(command,cwd=game,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            result['owned_client_pid']=client.pid
            deadline=time.monotonic()+360
            while True:
                if client.poll() is not None:raise RuntimeError('Stock client exited: '+str(client.returncode))
                if 'TarotVisual' in lane.rcon('list'):break
                if time.monotonic()>deadline:raise TimeoutError('Stock client login; see '+str(log))
                time.sleep(.5)
            text=log.read_text(encoding='utf-8',errors='replace')
            if 'file/Tabletop-Tarot-Universal.zip' not in text:raise AssertionError('Combined resource archive not loaded')
            if any(name not in text for name in additional):raise AssertionError('External resource pack not loaded')
            result['checks'].append({'name':'stock_client_loaded_same_combined_zip_as_resources','passed':True})
            if resources_only:
                lane.rcon('gamemode creative TarotVisual')
                for module in ['rider','numbers']:
                    lane.rcon('clear TarotVisual');lane.rcon('execute as TarotVisual run function tarot:give/'+module)
                    lane.rcon('scoreboard players set TarotVisual tarot.action 1')
                    until=time.monotonic()+20
                    while 'Found 1 ' not in lane.rcon('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0'):
                        if time.monotonic()>until:raise TimeoutError('Stock player card delivery: '+module)
                        time.sleep(.1)
                    lane.rcon('summon minecraft:item_display 0 -58 2 {Tags:["tarot.resource_probe"]}')
                    lane.rcon('item replace entity @e[type=minecraft:item_display,tag=tarot.resource_probe,limit=1,sort=nearest] contents from entity TarotVisual hotbar.1')
                    lane.rcon('tp TarotVisual 0.5 -60 0.5 0 -15');time.sleep(2)
                result['checks'].append({'name':'both_modules_drawn_for_stock_client_resource_loading','passed':True})
            else:backend(version,universal_lane=lane)
            if use_probe:
                from client_dispatch_lab import run as probe_client_dispatch
                probe_client_dispatch(lane,probe_control,probe_agent)
                result['scope']='Vanilla client with an isolated reflection-only test agent for main-thread Use dispatch; resources and gameplay remain production bytes; no OS input claim'
            lane.check_fixtures()
            time.sleep(1);text=log.read_text(encoding='utf-8',errors='replace')
            bad=[line for line in text.splitlines() if any(word in line.lower() for word in ['couldn\'t load overlays','couldn\'t load pack metadata','failed to load pack metadata']) or ('tarot' in line.lower() and any(word in line.lower() for word in ['failed','missing','unable','error']))]
            if bad:raise AssertionError('Combined card resources failed: '+repr(bad))
            result['checks'].append({'name':'no_combined_pack_metadata_overlay_or_card_asset_errors','passed':True})
            if not resources_only:result['backend_receipt']='universal-backend-'+version+'.json'
            if visual_hold:
                # Use an actual factory-printed Sun from this installed ZIP,
                # with an empty offhand, ready for a native direct-placement check.
                fixture=lane.world_dir/'datapacks/tarot/data/tarot/function/native_lab/visual_fixture.mcfunction';fixture.parent.mkdir(parents=True,exist_ok=True)
                fixture.write_text('clear TarotVisual\nexecute as TarotVisual run function tarot:give/rider\ndata modify storage tarot:visual sun set from entity TarotVisual SelectedItem.components."minecraft:charged_projectiles"[19]\ndata modify storage tarot:visual sun.Slot set value 4b\nsetblock 4 -60 0 minecraft:chest\ndata modify block 4 -60 0 Items set value []\ndata modify block 4 -60 0 Items append from storage tarot:visual sun\nitem replace entity TarotVisual weapon.mainhand from block 4 -60 0 container.4\ndata modify block 4 -60 0 Items set value []\nsetblock 4 -60 0 minecraft:air\nitem replace entity TarotVisual weapon.offhand with minecraft:air\nfill -2 -60 1 2 -60 3 minecraft:oak_planks\n',encoding='utf-8')
                lane.rcon('reload');lane.rcon('kill @e[type=minecraft:item_display,tag=tarot.resource_probe]');lane.rcon('function tarot:native_lab/visual_fixture');lane.rcon('gamemode survival TarotVisual');lane.rcon('deop TarotVisual');lane.rcon('time set day');lane.rcon('tp TarotVisual 0.5 -60 0.5 0 20')
                finish=folder/('finish-visual-'+str(time.time_ns()))
                (folder/'visual-ready.json').write_text(json.dumps({'pid':client.pid,'server_dir':str(lane.server_dir),'finish':str(finish),'game':str(game)}),encoding='utf-8')
                print('VISUAL_READY '+str(folder/'visual-ready.json'),flush=True)
                until=time.monotonic()+1800
                while not finish.exists():
                    if client.poll() is not None:raise RuntimeError('Visual client closed')
                    if time.monotonic()>until:raise TimeoutError('Visual inspection handoff')
                    time.sleep(.25)
                result['visual_source']='Actual factory-printed Sun from this combined ZIP, prepared with no offhand item for native direct placement.'
            result['passed']=True
    except Exception as error:result['passed']=False;result['error']=repr(error);raise
    finally:
        lane.stop()
        if client is not None and client.poll() is None:
            client.terminate()
            try:client.wait(timeout=15)
            except subprocess.TimeoutExpired:client.kill();client.wait(timeout=10)
        result['commands']=lane.commands;result['processes']=lane.starts
        if log.exists():
            evidence=ROOT/'content/tarot/evidence';target=evidence/'logs'/(sha(log)+'.log');target.parent.mkdir(exist_ok=True)
            if not target.exists():shutil.copyfile(log,target)
            if sha(target)!=sha(log):raise ValueError('Client log blob differs from its content address')
            result['client_log']=target.relative_to(evidence).as_posix();result['client_log_sha256']=sha(target)
        write_json(ROOT/f'content/tarot/evidence/{receipt_prefix}-client-{version}.json',result)
    print(json.dumps({'minecraft':version,'passed':True}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',default='26.3');parser.add_argument('--resources-only',action='store_true');parser.add_argument('--bundle',type=pathlib.Path);parser.add_argument('--receipt-prefix',default='universal');parser.add_argument('--visual-hold',action='store_true');parser.add_argument('--resource-pack',type=pathlib.Path,action='append',default=[]);parser.add_argument('--cards-below',action='store_true');parser.add_argument('--client-use-probe',action='store_true');args=parser.parse_args();main(args.version,args.resources_only,args.bundle,args.receipt_prefix,args.visual_hold,args.resource_pack,args.cards_below,args.client_use_probe)
