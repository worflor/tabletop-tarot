"""Build a modern-only combined fixture with the actual shared Mycelium compiler."""
import argparse,json,pathlib,subprocess,time,zipfile
from game_lab import ROOT,RUNTIME,sha
from universal import files

def build(mycelium):
    folder=RUNTIME/'metadata-probes'/str(time.time_ns());folder.mkdir(parents=True)
    request=folder/'request.json';request.write_text(json.dumps({'schema':1,'description':'Modern combined metadata probe','targets':['1.21.11','26.3']}),encoding='utf-8')
    gson=next((pathlib.Path.home()/'.gradle/caches/modules-2/files-2.1/com.google.code.gson/gson/2.11.0').rglob('gson-2.11.0.jar'))
    subprocess.run(['java','-cp',str(mycelium/'gradle-plugin/build/classes/java/main')+__import__('os').pathsep+str(gson),'dev.woflo.mycelium.gradle.PackOverlayPlan',str(mycelium),str(request),str(folder/'plan.json')],check=True)
    plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    if plan['pack_mcmeta']['pack']['min_format']!=[64,0] or len(plan['empty_overlays'])!=1:raise AssertionError('Typed metadata bridge not emitted')
    values={'pack.mcmeta':(json.dumps(plan['pack_mcmeta'],indent=2)+'\n').encode()}
    for directory in plan['empty_overlays']:values[directory+'/README.txt']=b'Metadata-only compatibility entry; no resources.\n'
    for group in plan['overlays']:
        version=group['targets'][0];kind=group['kind'];subfolder='datapack' if kind=='data' else 'resourcepack';prefix='data/' if kind=='data' else 'assets/'
        for name,data in files(ROOT/f'content/tarot/build/java-{version}/{subfolder}').items():
            if name.startswith(prefix):values[group['directory']+'/'+name]=data
    archive=folder/'Tabletop-Tarot-Universal.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
        for name,data in sorted(values.items()):output.writestr(name,data)
    index={'scope':'Modern-only combined metadata fixture; actual per-target production bytes, no translation','compiler':'Mycelium shared source','targets':['1.21.11','26.3'],'sha256':sha(archive),'bundle':str(folder),'plan':plan}
    (ROOT/'content/tarot/evidence/metadata-modern-fixture.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'bundle':str(folder),'sha256':sha(archive)}))
    return folder
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mycelium',type=pathlib.Path,required=True);build(p.parse_args().mycelium.resolve())
