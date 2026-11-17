"""Prepare an isolated official vanilla client; never touch an installed profile."""
from pathlib import Path
import concurrent.futures,hashlib,json,os,shutil,subprocess,urllib.request,zipfile,time,argparse,re,platform
from profiles import PROFILES,profile
from lab_environment import java_runtime
ROOT=Path(__file__).resolve().parents[3]
CACHE=ROOT.parent/'commonground-microvoxels-runtime'
R=CACHE/'tarot/client'
def get(url,path,sha):
    path=Path(path)
    if path.exists() and hashlib.sha1(path.read_bytes()).hexdigest()==sha:return path
    if 'resources.download.minecraft.net' in url:
        for cache in [Path.home()/'.gradle/caches/fabric-loom/assets/objects',Path.home()/'.gradle/caches/minecraft/assets/objects']:
            candidate=cache/sha[:2]/sha
            if candidate.is_file() and hashlib.sha1(candidate.read_bytes()).hexdigest()==sha:
                path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(candidate,path);return path
    for attempt in range(4):
        try:
            data=urllib.request.urlopen(url+('?' if '?' not in url else '&')+'tarot_retry='+str(attempt),timeout=60).read();break
        except Exception:
            if attempt==3:raise
            time.sleep(1)

    if hashlib.sha1(data).hexdigest()!=sha:raise ValueError('Official artifact hash mismatch: '+url)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path
def prepare(version='1.21.4'):
    global R
    if platform.system()!='Windows':raise RuntimeError('The stock-client preparation lane currently supports Windows. Protocol/server tests are separate.')
    spec=profile(version);R=CACHE/('tarot/client-'+version);R.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(get(spec['manifest_url'],R/'version.json',spec['manifest_sha1']).read_text(encoding='utf-8'))
    jobs=[];classpath=[]
    for lib in manifest['libraries']:
        allowed=not lib.get('rules')
        for rule in lib.get('rules',[]):
            name=rule.get('os',{}).get('name')
            arch=rule.get('os',{}).get('arch')
            if (name is None or name=='windows') and (not arch or re.fullmatch(arch,'amd64')):allowed=rule['action']=='allow'
        if not allowed:continue
        a=lib.get('downloads',{}).get('artifact')
        if a:
            path=R/'libraries'/a['path'];jobs.append((a['url'],path,a['sha1']));classpath.append(path)
    a=manifest['downloads']['client'];jobs.append((a['url'],R/'client.jar',a['sha1']));classpath.append(R/'client.jar')
    asset=manifest['assetIndex'];assets=CACHE/'assets'
    ai=json.loads(get(asset['url'],assets/'indexes'/(asset['id']+'.json'),asset['sha1']).read_text())
    for a in ai['objects'].values():
        h=a['hash'];jobs.append(('https://resources.download.minecraft.net/'+h[:2]+'/'+h,assets/'objects'/h[:2]/h,h))
    print('Verifying/downloading official client artifacts:',len(jobs),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for i,_ in enumerate(pool.map(lambda args:get(*args),jobs)):
            if i%1000==0:print('Artifacts checked:',i,flush=True)
    natives=R/'natives';natives.mkdir(exist_ok=True)
    for p in classpath[:-1]:
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if name.endswith('.dll'):(natives/Path(name).name).write_bytes(z.read(name))
    game=R/'game';game.mkdir(exist_ok=True);packs=game/'resourcepacks';packs.mkdir(exist_ok=True)
    source_pack=ROOT/f'content/tarot/build/java-{version}/Tabletop-Tarot-{version}-resources.zip';pack_order=['vanilla']
    if source_pack.is_file():
        shutil.copyfile(source_pack,packs/'Tabletop-Tarot.zip');pack_order.append('file/Tabletop-Tarot.zip')
    with zipfile.ZipFile(R/'client.jar') as client_jar:options_version=json.loads(client_jar.read('version.json'))['world_version']
    (game/'options.txt').write_text('version:'+str(options_version)+'\nresourcePacks:'+json.dumps(pack_order)+'\nincompatibleResourcePacks:[]\nonboardAccessibility:false\npauseOnLostFocus:false\nrenderDistance:4\nsimulationDistance:5\nmaxFps:60\nenableVsync:false\nguiScale:2\nfullscreen:false\nautoJump:false\n',encoding='utf-8')
    java=java_runtime(spec['java'])
    command=[str(java),'-Xmx1024M',f'-Djava.library.path={natives}','-cp',os.pathsep.join(map(str,classpath)),manifest['mainClass'],'--username','TarotVisual','--version',version,'--gameDir',str(game),'--assetsDir',str(assets),'--assetIndex',asset['id'],'--accessToken','0','--width','1000','--height','700']
    (R/'launch.json').write_text(json.dumps(command,indent=2));print('Client prepared',flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=PROFILES,default='1.21.4');a=parser.parse_args();prepare(a.version)
