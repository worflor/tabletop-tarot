"""Maintainer-only: freeze the small Mycelium overlay compiler and its complete sources."""
import argparse,hashlib,json,pathlib,subprocess,tempfile,zipfile,urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'tools/mycelium-overlays'
def sha(data):return hashlib.sha256(data).hexdigest()
def vendor(source):
    source=pathlib.Path(source).resolve();DEST.mkdir(parents=True,exist_ok=True)
    java=source/'gradle-plugin/src/main/java/dev/woflo/mycelium/gradle'
    gson=next((pathlib.Path.home()/'.gradle/caches/modules-2/files-2.1/com.google.code.gson/gson/2.11.0').rglob('gson-2.11.0.jar'))
    sources={f'src/dev/woflo/mycelium/gradle/{n}.java':(java/(n+'.java')).read_bytes() for n in ['Eras','PackOverlayPlan']}
    sources['eras/minecraft.json']=(source/'eras/minecraft.json').read_bytes()
    sources['LICENSE']=(source/'LICENSE').read_bytes()
    with tempfile.TemporaryDirectory(prefix='tarot-planner-') as temporary:
        folder=pathlib.Path(temporary)
        subprocess.run(['javac','--release','17','-cp',str(gson),'-d',str(folder),*[str(java/(n+'.java')) for n in ['Eras','PackOverlayPlan']]],check=True)
        entries={p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*.class')}
        with zipfile.ZipFile(gson) as archive:
            # Existing compiler dependency; retain its licence and omit signatures/module metadata.
            for name in archive.namelist():
                if name.startswith('com/google/gson/') and not name.endswith('/'):entries[name]=archive.read(name)
        for filename,files in [('planner.jar',entries),('planner-sources.zip',sources)]:
            with zipfile.ZipFile(DEST/filename,'w',zipfile.ZIP_DEFLATED) as archive:
                for name,data in sorted(files.items()):
                    info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,data)
    (DEST/'eras').mkdir(exist_ok=True);(DEST/'eras/minecraft.json').write_bytes(sources['eras/minecraft.json'])
    (DEST/'LICENSE-Mycelium.txt').write_bytes(sources['LICENSE'])
    (DEST/'LICENSE-Gson.txt').write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/google/gson/gson-parent-2.11.0/LICENSE',timeout=30).read())
    files={p.relative_to(DEST).as_posix():sha(p.read_bytes()) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='source-lock.json'}
    lock={'source':'https://github.com/worflor/mycelium','commit':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),'compiler_sources_sha256':{n:sha(d) for n,d in sources.items()},'gson':'2.11.0','gson_sha256':sha(gson.read_bytes()),'files':files}
    (DEST/'source-lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'vendored':str(DEST),'files':len(files)}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mycelium',required=True);vendor(parser.parse_args().mycelium)
