"""Own a normal-terrain vanilla photo world and capture unedited native frames."""
import argparse,json,math,os,pathlib,re,shutil,subprocess,sys,time
from game_lab import ROOT,RUNTIME,sha
from universal_lab import ZipLane
from promo_client import prepare,send

def main():
    root=RUNTIME/'promotion'/('session-'+str(time.time_ns()));root.mkdir(parents=True)
    lane=ZipLane('26.3');lane.server_dir=root/'server';lane.world_dir=lane.server_dir/lane.world_name
    lane.property_overrides={'level-type':'minecraft:normal','generator-settings':'{}','generate-structures':'true','level-seed':'20261108','view-distance':10,'simulation-distance':4,'motd':'Tabletop Tarot photography'};lane.server_heap='3072M'
    client=None;record={'scope':'Actual Minecraft 26.3 native Screenshot.grab, vanilla natural terrain and blocks, shipped card pack; no render replacement or edited screenshots','artifact_sha256':sha(lane.archive),'run':str(root),'shots':[],'commands':[]}
    try:
        lane.download_server();lane.start();command,control,agent=prepare(root);record['camera_bridge']=agent
        game=root/'client';game.mkdir();resources=game/'resourcepacks';resources.mkdir();shutil.copyfile(lane.archive,resources/lane.archive.name)
        from profiles import profile
        version=json.loads((RUNTIME/'client-26.3/version.json').read_text())
        import zipfile
        with zipfile.ZipFile(RUNTIME/'client-26.3/client.jar') as jar:options_version=json.loads(jar.read('version.json'))['world_version']
        (game/'options.txt').write_text('version:'+str(options_version)+'\nresourcePacks:["vanilla","file/Tabletop-Tarot-Universal.zip"]\nincompatibleResourcePacks:[]\nonboardAccessibility:false\nskipMultiplayerWarning:true\npauseOnLostFocus:false\ntutorialStep:none\nrenderDistance:12\nsimulationDistance:4\nmaxFps:40\nenableVsync:false\npreferredGraphicsBackend:"opengl"\nguiScale:2\nsoundCategory_master:0.0\n',encoding='utf-8')
        command[command.index('--username')+1]='CardCamera';command[command.index('--gameDir')+1]=str(game)
        command[command.index('--width')+1]='1920';command[command.index('--height')+1]='1080'
        command += ['--quickPlayMultiplayer','127.0.0.1:'+str(lane.game_port)]
        log=root/'client.log';startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=4
        with log.open('wb') as output:client=subprocess.Popen(command,cwd=game,stdout=output,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
        until=time.monotonic()+300
        while 'CardCamera' not in lane.rcon('list'):
            if client.poll() is not None:raise RuntimeError('Photo client exited: '+str(log))
            if time.monotonic()>until:raise TimeoutError('Photo client login')
            time.sleep(.5)
        lane.rcon('op CardCamera');lane.rcon('gamemode spectator CardCamera');send(control,'prepare')
        record['game']=str(game);record['control']=str(control);record['pid']=client.pid
        (RUNTIME/'promotion/active.json').write_text(json.dumps({'root':str(root),'server_dir':str(lane.server_dir),'world':str(lane.world_dir),'game':str(game),'control':str(control),'client_pid':client.pid},indent=2)+'\n')
        print('PHOTO_READY '+json.dumps({'root':str(root),'probe':send(control,'probe')}),flush=True)
        for line in sys.stdin:
            if not line.strip():continue
            try:
                data=json.loads(line);verb=data['verb']
                if verb=='stop':break
                if verb=='rcon':answer=lane.rcon(data['command'])
                elif verb=='client':answer=send(control,data['action'],**data.get('args',{}))
                elif verb=='batch':answer=[lane.rcon(command) for command in data['commands']]
                elif verb=='camera':
                    x,y,z=data['feet'];fx,fy,fz=data['focus'];yaw=math.degrees(math.atan2(-(fx-x),fz-z));pitch=math.degrees(math.atan2(y+1.62-fy,math.hypot(fx-x,fz-z)))
                    lane.rcon(f'tp CardCamera {x} {y} {z} {yaw} {pitch}');send(control,'fov',value=data.get('fov',55));time.sleep(data.get('settle',2));answer=send(control,'probe')
                elif verb=='shot':
                    answer=send(control,'shot',name=data['name']);path=pathlib.Path(answer['path'])
                    until=time.monotonic()+20
                    while not path.exists():
                        if time.monotonic()>until:raise TimeoutError('Native PNG not written')
                        time.sleep(.1)
                    record['shots'].append({'name':data['name'],'path':str(path),'sha256':sha(path),'edited':False});answer['sha256']=sha(path)
                else:raise ValueError(verb)
                print(json.dumps({'verb':verb,'result':answer},ensure_ascii=True),flush=True)
            except Exception as error:print(json.dumps({'error':repr(error)}),flush=True)
    finally:
        lane.stop()
        if client is not None and client.poll() is None:
            client.terminate()
            try:client.wait(timeout=20)
            except subprocess.TimeoutExpired:client.kill();client.wait(timeout=10)
        record['commands']=lane.commands;(root/'capture.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

if __name__=='__main__':main()
