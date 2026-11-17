"""Bind the renamed distribution to the tested 1.0.0 runtime without rewriting receipts."""
import hashlib,io,json,pathlib,subprocess,zipfile,urllib.request
from universal import ROOT,resolve,validate,IMPORT_MARKER,IMPORT_NOTICE
from check import require

BASE_COMMIT='ebbf48b'
BASE_PATH='staging/releases/physical-cards/1.0.0/Physical-Cards-1.0.0.zip'
BASE_SHA256='fe7354c77039a205b469b8006c848fd3290125b26d78a74341748b939a962054'
PARSER_COMMIT='f73010ae0809813120a16b733a3d0bfd23f76e24'

def sha(data):return hashlib.sha256(data).hexdigest()
def members(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(z.testzip() is None and len(z.namelist())==len(set(z.namelist())),'Invalid ZIP')
        return {n:z.read(n) for n in z.namelist()}

def main():
    folder=ROOT/'build/universal';validate(folder)
    old_raw=subprocess.check_output(['git','show',BASE_COMMIT+':'+BASE_PATH],cwd=ROOT)
    require(sha(old_raw)==BASE_SHA256,'Historical verified artifact changed')
    raw=(folder/'Tabletop-Tarot-Universal.zip').read_bytes();old=members(old_raw);new=members(raw)
    added=set(new)-set(old);removed=set(old)-set(new)
    require(added=={IMPORT_MARKER,'LICENSE.md','licenses/MIT.txt','licenses/CC-BY-4.0.txt'} and not removed,'Unexpected package membership change')
    changed={n for n in old if old[n]!=new[n]}
    require(changed=={'pack.mcmeta','INSTALL.txt','CREDITS.txt'},'Unexpected gameplay/art change')
    before=json.loads(old['pack.mcmeta']);after=json.loads(new['pack.mcmeta'])
    before['pack'].pop('description');after['pack'].pop('description')
    require(before==after,'Changed format ranges or overlay selection')
    require(new[IMPORT_MARKER]==IMPORT_NOTICE,'Importer marker changed')
    for name in ['LICENSE.md','licenses/MIT.txt','licenses/CC-BY-4.0.txt']:
        require(new[name]==(ROOT/name).read_bytes(),'Embedded license differs: '+name)
    plan=json.loads((folder/'overlay-plan.json').read_text(encoding='utf-8'));rows=[]
    for row in plan['targets']:
        for kind in ['data','resource']:
            require(resolve(old,kind,row[kind])==resolve(new,kind,row[kind]),'Effective content changed: '+row['minecraft']+' '+kind)
            if not isinstance(row[kind],list):
                require(resolve(old,kind,row[kind],False)==resolve(new,kind,row[kind],False),'Legacy selection changed')
        rows.append({'minecraft':row['minecraft'],'data_identical':True,'assets_identical':True})
    # Run the actual pinned Modrinth parser body. Only TypeScript annotations are
    # removed; unrelated version/filename helpers are stubbed for this classifier test.
    url='https://raw.githubusercontent.com/modrinth/code/'+PARSER_COMMIT+'/apps/frontend/src/helpers/infer/pack-parsers.ts'
    source=urllib.request.urlopen(url,timeout=30).read().decode('utf-8')
    require(sha(source.encode())=='40c17966389a1d81dce42dfc0626fa51a62a616253a24d809949d6f99f72965c','Pinned Modrinth parser changed')
    parser=source[source.index('export function createPackParser'):]
    for a,b in [('export function','function'),('project: Project, gameVersions: GameVersion[], rawFile: RawFile','project, gameVersions, rawFile'),('(file: string, zip: JSZip): Promise<InferredVersionInfo>','(file, zip)'),(' as any',''),('const loaders: string[]','const loaders'),('let newGameVersions: string[]','let newGameVersions')]:parser=parser.replace(a,b)
    script='const names=JSON.parse(process.argv[1]);const DATA_PACK_FORMATS={},RESOURCE_PACK_FORMATS={};const getGameVersionsFromPackMeta=()=>[];const extractVersionFromFilename=()=>null;const versionType=()=>"release";'+parser+';createPackParser({actualProjectType:"mod"},[],{name:"Tabletop-Tarot-1.0.0.zip"})("{\\"pack\\":{}}",{file:r=>names.filter(n=>r.test(n))}).then(x=>console.log(JSON.stringify(x.loaders)))'
    script=script.replace('JSON.parse(process.argv[1])','JSON.parse(require("fs").readFileSync(0,"utf8"))')
    def classify(names):return json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(list(names)),text=True))
    require(classify(old)==['minecraft'],'Baseline did not reproduce resource-pack misclassification')
    require(classify(new)==['datapack'],'Modrinth datapack detection failed')
    index=ROOT/'evidence/compatibility.json'
    baseline_index=subprocess.check_output(['git','show',BASE_COMMIT+':content/tarot/evidence/compatibility.json'],cwd=ROOT)
    require(index.read_bytes()==baseline_index,'Historical compatibility evidence was rewritten')
    require(json.loads(index.read_text())['combined_archive']['sha256']==BASE_SHA256,'Gameplay evidence baseline changed')
    result={'passed':True,'scope':'Packaging verification; effective runtime/art bytes identical to the fully verified baseline on all eleven targets. No new gameplay claims. Actual pinned Modrinth frontend classifier exercised with Node; no authenticated Modrinth upload performed.','baseline':{'commit':BASE_COMMIT,'path':BASE_PATH,'sha256':BASE_SHA256,'compatibility_index_sha256':sha(index.read_bytes())},'archive_sha256':sha(raw),'changed_members':sorted(changed),'added_members':sorted(added),'targets':rows,'modrinth':{'source':'https://github.com/modrinth/code/blob/'+PARSER_COMMIT+'/apps/frontend/src/helpers/infer/pack-parsers.ts','parser_sha256':sha(source.encode()),'before':['minecraft'],'after':['datapack']}}
    (ROOT/'evidence/tabletop-packaging.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'targets':len(rows),'archive_sha256':sha(raw),'modrinth_classifier':'datapack'}))
    return result

if __name__=='__main__':main()
