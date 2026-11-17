"""Set up and observe real stock-client Use keys; never simulate the checked action."""
import argparse,json,pathlib,time,shutil
from game_lab import ROOT,RUNTIME,VanillaLane,sha,write_json

def main(version,ready_path,phase):
    ready=json.loads(ready_path.read_text(encoding='utf-8'));server=pathlib.Path(ready['server_dir']).resolve()
    if not server.is_relative_to(RUNTIME.resolve()):raise ValueError('Expected an owned lab server')
    props=dict(line.split('=',1) for line in (server/'server.properties').read_text().splitlines() if '=' in line)
    lane=VanillaLane(version);lane.rcon_port=int(props['rcon.port']);lane.password=props['rcon.password']
    cache=RUNTIME/f'native-refinement-{ready["pid"]}.json';archive=ROOT/'content/tarot/build/universal/Tabletop-Tarot-Universal.zip'
    state=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {'minecraft':version,'scope':'Unmodified stock client; actual Use binding R, observed through RCON; vanilla block/offhand input priority included','combined_zip_sha256':sha(archive),'checks':[],'commands':[]}
    if state['combined_zip_sha256']!=sha(archive):raise ValueError('Native session belongs to a different archive')
    state.setdefault('started_at',time.time())
    def cmd(command):return lane.rcon(command)
    try:
        if phase.startswith('setup-'):
            cmd('kill @e[type=minecraft:item_display,tag=tarot.placed]');cmd('kill @e[type=minecraft:interaction,tag=tarot.touch]')
            cmd('fill -2 -59 1 2 -57 3 minecraft:air');cmd('function tarot:native_lab/visual_fixture')
            cmd('scoreboard players set TarotVisual tarot.cool 0');cmd('tp TarotVisual 0.5 -60 0.5 0 20')
            if phase=='setup-torch':cmd('item replace entity TarotVisual weapon.offhand with minecraft:torch 64')
            cmd('data modify storage tarot_lab:native_refinement expected set from entity TarotVisual SelectedItem')
            state['setup']=phase;state['setup_at']=time.time()
            print('Ready for the stock client Use key: '+phase,flush=True)
        elif phase.startswith('check-'):
            expected='setup-'+phase.removeprefix('check-')
            if state.get('setup')!=expected:raise ValueError('Missing matching native setup')
            display='@e[type=minecraft:item_display,tag=tarot.placed,limit=1]'
            if phase=='check-clear':
                if 'Test passed' not in cmd('execute if entity '+display):raise AssertionError('Native Use did not place a card')
                if 'No items' not in cmd('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0'):raise AssertionError('Placed card also remained in inventory')
                source='entity '+display+' item'
            else:
                if 'Test passed' in cmd('execute if entity '+display):raise AssertionError('Occupied offhand also placed the card')
                if 'Test passed' not in cmd('execute if block 0 -59 2 minecraft:torch'):raise AssertionError('Vanilla offhand torch placement was not exercised')
                source='entity TarotVisual SelectedItem'
            cmd('data modify storage tarot_lab:native_refinement compare set from storage tarot_lab:native_refinement expected.components')
            cmd('execute store success score #native_changed tarot.sys run data modify storage tarot_lab:native_refinement compare set from '+source+'.components')
            if 'has 0 ' not in cmd('scoreboard players get #native_changed tarot.sys'):raise AssertionError('Native interaction changed card components')
            name='stock_client_use_places_one_exact_card' if phase=='check-clear' else 'stock_client_offhand_torch_places_normally_without_also_placing_card'
            state['checks'].append({'name':name,'passed':True});print(name,flush=True)
        elif phase=='finish':
            if {c['name'] for c in state['checks']}!={'stock_client_use_places_one_exact_card','stock_client_offhand_torch_places_normally_without_also_placing_card'}:raise AssertionError('Incomplete native input checks')
            state['screenshots']=[]
            for source in sorted((pathlib.Path(ready['game'])/'screenshots').glob('*.png')):
                if source.stat().st_mtime<state['started_at']:continue
                evidence=ROOT/'content/tarot/evidence';destination=evidence/'captures'/(sha(source)+'.png');destination.parent.mkdir(exist_ok=True)
                if not destination.exists():shutil.copyfile(source,destination)
                if sha(destination)!=sha(source):raise ValueError('Native capture blob differs from its content address')
                state['screenshots'].append({'path':destination.relative_to(evidence).as_posix(),'sha256':sha(destination),'source':'Minecraft F2 during this exact stock-client session'})
            state['passed']=True;state['commands'].extend(lane.commands);lane.commands=[]
            write_json(ROOT/f'content/tarot/evidence/native-refinement-{version}.json',state)
            pathlib.Path(ready['finish']).touch()
    finally:
        state['commands'].extend(lane.commands);cache.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='1.21.11');p.add_argument('--ready',type=pathlib.Path,required=True);p.add_argument('--phase',choices=['setup-clear','check-clear','setup-torch','check-torch','finish'],required=True);a=p.parse_args();main(a.version,a.ready,a.phase)
