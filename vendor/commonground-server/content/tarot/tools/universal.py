"""One vanilla ZIP, used as both datapack and resource pack, across exact tested targets."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,uuid,zipfile,tempfile
from build import ROOT,build,pack_zip,write,pack_description
from check import check,require,safe_relative
from profiles import PROFILES
from module_registry import load as load_modules,select as select_modules,suffix as module_suffix

PLANNER=ROOT/'tools/mycelium-overlays'
IMPORT_MARKER='data/tabletop_tarot/README.txt'
IMPORT_NOTICE=b'Tabletop Tarot datapack. Runtime content is selected from version overlays. This file is inert.\n'
def digest(data):return hashlib.sha256(data).hexdigest()
def files(folder):return {p.relative_to(folder).as_posix():p.read_bytes() for p in sorted(folder.rglob('*')) if p.is_file()}
def hashes(values):return {n:digest(d) for n,d in values.items()}
def pair(value):return tuple(value) if isinstance(value,list) else (value,0)
def selected(entry,fmt,modern=True):
    if modern:return pair(entry['min_format'])<=pair(fmt)<=pair(entry['max_format'])
    old=entry['formats'];return old==pair(fmt)[0] if isinstance(old,int) else old[0]<=pair(fmt)[0]<=old[1]
def resolve(values,kind,fmt,modern=True):
    prefix={'data':'data/','resource':'assets/'}[kind]
    result={n:d for n,d in values.items() if n.startswith(prefix) and n!=IMPORT_MARKER}
    metadata=json.loads(values['pack.mcmeta'])
    for entry in metadata['overlays']['entries']:
        if selected(entry,fmt,modern):
            directory=entry['directory']+'/'
            result.update({n[len(directory):]:d for n,d in values.items() if n.startswith(directory+prefix)})
    return result
def validate(folder):
    manifest=json.loads((folder/'build.json').read_text(encoding='utf-8'));values=files(folder/'pack')
    require(hashes(values)==manifest['pack_sha256'],'Expanded combined pack changed')
    with zipfile.ZipFile(folder/'Tabletop-Tarot-Universal.zip') as archive:
        require(len(archive.namelist())==len(set(archive.namelist())),'Duplicate ZIP member')
        require({n:archive.read(n) for n in archive.namelist()}==values,'Combined ZIP differs from expanded pack')
    plan=json.loads((folder/'overlay-plan.json').read_text(encoding='utf-8'))
    require(json.loads(values['pack.mcmeta'])==plan['pack_mcmeta'],'Combined overlay metadata changed')
    require(not any(n.startswith('data/') and n!=IMPORT_MARKER for n in values),'Unselected runtime leaked into common root')
    if IMPORT_MARKER in values:require(values[IMPORT_MARKER]==IMPORT_NOTICE,'Changed importer marker')
    for target in plan['targets']:
        version=target['minecraft']
        for kind in ['data','resource']:
            expected=manifest['effective_sha256'][version][kind]
            require(hashes(resolve(values,kind,target[kind]))==expected,'Effective combined content mismatch: '+version+' '+kind)
            # Older engines read formats; their selected content must also agree.
            if not isinstance(PROFILES[version][kind],list):
                require(hashes(resolve(values,kind,target[kind],False))==expected,'Legacy selection mismatch: '+version+' '+kind)
    require(digest((folder/'Tabletop-Tarot-Universal.zip').read_bytes())==manifest['zip_sha256'],'Combined ZIP digest changed')
    require(hashlib.sha1((folder/'Tabletop-Tarot-Universal.zip').read_bytes()).hexdigest()==manifest['zip_sha1'],'Server resource-pack SHA-1 changed')
    return {'passed':True,'targets':len(plan['targets']),'cards':manifest['cards'],'zip_sha256':manifest['zip_sha256']}

def compile_pack(modules=None,rebuild=True):
    lock=json.loads((PLANNER/'source-lock.json').read_text(encoding='utf-8'))
    for name,expected in lock['files'].items():require(digest((PLANNER/safe_relative(name)).read_bytes())==expected,'Pinned Mycelium compiler changed: '+name)
    registry,identities=load_modules(ROOT);modules=select_modules(modules,registry)
    build_root=(ROOT/'build').resolve();build_root.mkdir(exist_ok=True)
    suffix=module_suffix(modules,registry)
    final=build_root/('universal'+suffix)
    with tempfile.TemporaryDirectory(prefix='.stage-universal-',dir=build_root) as temporary:
        stage=pathlib.Path(temporary).resolve()
        require(stage.parent==build_root,'Unsafe combined staging directory')
        outputs={}
        for version in PROFILES:
            output=build(version,modules) if rebuild else build_root/('java-'+version+suffix)
            check(output,quiet=True,source_root=ROOT);outputs[version]=output
        write(stage/'declaration.json',{'schema':1,'description':pack_description(modules),'targets':list(PROFILES)})
        subprocess.run([os.environ.get('TAROT_BUILD_JAVA','java'),'-cp',str(PLANNER/'planner.jar'),'dev.woflo.mycelium.gradle.PackOverlayPlan',str(PLANNER),str(stage/'declaration.json'),str(stage/'overlay-plan.json')],check=True)
        plan=json.loads((stage/'overlay-plan.json').read_text(encoding='utf-8'));content={};effective={}
        for row in plan['targets']:
            for kind in ['data','resource']:require(pair(row[kind])==pair(PROFILES[row['minecraft']][kind]),'Mycelium/official target format drift: '+row['minecraft']+' '+kind)
        for version,output in outputs.items():
            effective[version]={}
            for kind,subfolder,prefix in [('data','datapack','data/'),('resource','resourcepack','assets/')]:
                values={n:d for n,d in files(output/subfolder).items() if n.startswith(prefix)}
                content[version,kind]=values;effective[version][kind]=hashes(values)
        # Only assets identical and present on EVERY target may live in the root.
        common=dict(content[next(iter(PROFILES)),'resource'])
        for version in PROFILES:common={n:d for n,d in common.items() if content[version,'resource'].get(n)==d}
        packed=dict(common)
        # Modrinth checks root data/ before assets/ and does not inspect overlays.
        # A text marker changes classification without loading any Minecraft data.
        packed[IMPORT_MARKER]=IMPORT_NOTICE
        from presentation import release_files
        packed.update(release_files(modules,root=ROOT))
        for directory in plan.get('empty_overlays',[]):
            packed[safe_relative(directory)+'/README.txt']=b'Metadata compatibility bridge. No data or assets live here.\n'
        for group in plan['overlays']:
            targets=group['targets'];kind=group['kind'];values=content[targets[0],kind]
            require(all(content[v,kind]==values for v in targets),'Equal pack formats require different contents; overlays cannot distinguish them: '+str(targets))
            for name,data in values.items():
                if kind=='resource' and name in common:continue
                packed[group['directory']+'/'+name]=data
        packed['pack.mcmeta']=(json.dumps(plan['pack_mcmeta'],ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        for name,data in packed.items():
            destination=stage/'pack'/safe_relative(name);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
        pack_zip(stage/'pack',stage/'Tabletop-Tarot-Universal.zip')
        (stage/'Tabletop-Tarot-Universal.zip.sha1').write_text(hashlib.sha1((stage/'Tabletop-Tarot-Universal.zip').read_bytes()).hexdigest()+'  Tabletop-Tarot-Universal.zip\n',encoding='ascii')
        write(stage/'build.json',{'modules':modules,'cards':sum(registry[m]['count'] for m in modules),'scope':'Only exact listed tested Java releases; install this same ZIP in datapacks and resourcepacks. Native card items follow vanilla forward world upgrades; legacy opaque data requires conversion on its original encoding host.','targets':list(PROFILES),'planner_lock_sha256':digest((PLANNER/'source-lock.json').read_bytes()),'pack_sha256':hashes(packed),'effective_sha256':effective,'zip_sha256':digest((stage/'Tabletop-Tarot-Universal.zip').read_bytes()),'zip_sha1':hashlib.sha1((stage/'Tabletop-Tarot-Universal.zip').read_bytes()).hexdigest()})
        validate(stage)
        previous=build_root/('.previous-universal-'+uuid.uuid4().hex)
        if final.exists():
            require(not final.is_symlink() and final.resolve().parent==build_root,'Unsafe previous combined output');final.rename(previous)
        try:stage.rename(final)
        except Exception:
            if previous.exists():previous.rename(final)
            raise
        if previous.exists():
            require(previous.resolve().parent==build_root,'Unsafe retired combined output');shutil.rmtree(previous)
        print(json.dumps({'output':str(final),'zip':str(final/'Tabletop-Tarot-Universal.zip'),**validate(final)}))
        return final
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--modules',nargs='+',choices=load_modules()[0]);parser.add_argument('--reuse-builds',action='store_true');parser.add_argument('--check',type=pathlib.Path);args=parser.parse_args()
    if args.check:print(json.dumps(validate(args.check)))
    else:compile_pack(args.modules,not args.reuse_builds)
