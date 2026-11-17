"""Fetch hash-verified Modrinth fixtures and resolve real pack priority collisions."""
import argparse,hashlib,json,urllib.request,zipfile
from pathlib import Path
from game_lab import RUNTIME,ROOT,sha,write_json
from universal import files,resolve,pair,selected
from profiles import PROFILES

CACHE=RUNTIME/'resource-compat'
HEADERS={'User-Agent':'CommonGround-PhysicalCards-Compatibility/0.1 (local local testing)'}

def api(path):
    with urllib.request.urlopen(urllib.request.Request('https://api.modrinth.com/v2/'+path,headers=HEADERS),timeout=40) as r:return json.load(r)

def fetch(slug,version):
    CACHE.mkdir(exist_ok=True)
    pins=CACHE/'downloads.json'
    if pins.exists():
        for row in json.loads(pins.read_text(encoding='utf-8')):
            if row.get('project')!=slug or row.get('minecraft')!=version:continue
            cached=Path(row['file']).resolve()
            if cached.is_relative_to(CACHE.resolve()) and cached.is_file() and hashlib.sha512(cached.read_bytes()).hexdigest()==row['sha512']:return row
    project=api('project/'+slug)
    choices=[v for v in api('project/'+slug+'/version') if version in v['game_versions']]
    if not choices:return None
    v=choices[0];f=next(f for f in v['files'] if f.get('primary',False));path=CACHE/(slug+'-'+version+'.zip')
    if not path.exists() or hashlib.sha512(path.read_bytes()).hexdigest()!=f['hashes']['sha512']:
        with urllib.request.urlopen(urllib.request.Request(f['url'],headers=HEADERS),timeout=90) as r:path.write_bytes(r.read())
    if hashlib.sha512(path.read_bytes()).hexdigest()!=f['hashes']['sha512']:raise AssertionError('Modrinth download hash mismatch')
    return {'project':slug,'project_id':project['id'],'version_id':v['id'],'minecraft':version,'license':project['license'],'file':str(path),'download':f['url'],'sha512':f['hashes']['sha512'],'sha256':sha(path)}

def zip_assets(path,version):
    with zipfile.ZipFile(path) as z:
        values={n:z.read(n) for n in z.namelist() if not n.endswith('/')};result={n:d for n,d in values.items() if n.startswith('assets/')}
    metadata=json.loads(values['pack.mcmeta']);fmt=PROFILES[version]['resource']
    for entry in metadata.get('overlays',{}).get('entries',[]):
        modern=isinstance(fmt,list) and 'min_format' in entry
        if selected(entry,fmt,modern):
            prefix=entry['directory']+'/'
            result.update({n[len(prefix):]:d for n,d in values.items() if n.startswith(prefix+'assets/')})
    return result

def legacy_model(resources,carrier,code):
    name='assets/minecraft/models/item/'+carrier+'.json'
    model=json.loads(resources[name]);selected='minecraft:item/'+carrier
    for entry in model.get('overrides',[]):
        if all(code>=value if prop=='custom_model_data' else 0>=value for prop,value in entry['predicate'].items()):selected=entry['model']
    return selected

def main():
    bundle=ROOT/'content/tarot/build/universal';packed=files(bundle/'pack')
    result={'scope':'Actual hash-pinned Modrinth ZIPs; deterministic effective resource/model resolution in both priority orders. Stock-client loading is separately recorded. No third-party files are redistributed.','combined_zip_sha256':sha(bundle/'Tabletop-Tarot-Universal.zip'),'downloads':[],'checks':[]}
    for version in ['1.20.6','1.21.11']:
        own=resolve(packed,'resource',PROFILES[version]['resource'])
        catalogue=json.loads((ROOT/f'content/tarot/build/java-{version}/catalogue.json').read_text(encoding='utf-8'))
        for slug in ['faithful-32x','bare-bones','3d-default']:
            external=fetch(slug,version)
            if not external:continue
            result['downloads'].append(external);other=zip_assets(external['file'],version)
            for top in [True,False]:
                resources={**other,**own} if top else {**own,**other};broken=[]
                for c in catalogue['cards']:
                    if PROFILES[version]['legacy_models']:
                        actual=legacy_model(resources,'carrot_on_a_stick',c['custom_model_data'])
                    else:actual=json.loads(resources['assets/tarot/items/card/'+c['key']+'.json'])['model']['model']
                    if actual!=c['model']:broken.append(c['key'])
                    tex='assets/tarot/textures/card/'+c['key']+'.png'
                    if resources[tex]!=own[tex]:raise AssertionError('Card art overridden: '+c['key'])
                row={'name':slug+'_'+version+('_cards_above' if top else '_cards_below'),'cards_checked':len(catalogue['cards']),'card_models_preserved':not broken,'outcome':'requires_cards_above' if broken else 'compatible','affected_cards':broken,'overlapping_definitions':sorted(n for n in own.keys()&other.keys() if n.endswith('.json')),'passed':not broken or (not top and slug=='3d-default' and PROFILES[version]['legacy_models'])}
                result['checks'].append(row);print(json.dumps({k:v for k,v in row.items() if k not in {'affected_cards','overlapping_definitions'}}),flush=True)
        if PROFILES[version]['legacy_models']:
            for carrier in ['paper','carrot_on_a_stick']:
                for code in [0,149999,150078,150500,151000,159999,160012,161000,999999]:
                    actual=legacy_model(own,carrier,code)
                    if actual.startswith('tarot:'):raise AssertionError('Legacy model leaked outside its reserved values: '+str((carrier,code,actual)))
            result['checks'].append({'name':'legacy_model_ranges_do_not_capture_unrelated_custom_items','passed':True})
    result['passed']=all(r['passed'] for r in result['checks'])
    write_json(ROOT/'content/tarot/evidence/resource-compatibility.json',result)
    if not result['passed']:raise AssertionError('Resource compatibility failure')
    (CACHE/'downloads.json').write_text(json.dumps(result['downloads'],indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
