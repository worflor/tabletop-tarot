"""Validate pinned art and exact archives; checks remain active under python -O."""
from pathlib import Path, PurePosixPath
import hashlib,json,sys,zipfile
from PIL import Image
from profiles import profile
from module_registry import load as load_modules
ROOT=Path(__file__).resolve().parents[1]
def require(condition,reason):
    if not condition:raise ValueError(reason)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def safe_relative(value):
    require('\\' not in value,'Backslash in manifest path: '+value)
    p=PurePosixPath(value)
    require(not p.is_absolute() and bool(p.parts) and not any(s in {'..','.'} or ':' in s for s in p.parts),'Unsafe manifest path: '+value)
    return p.as_posix()
def check(output,quiet=False,source_root=None):
    ROOT=Path(source_root or globals()['ROOT']);registry,identities=load_modules(ROOT)
    output=Path(output);catalog=read(output/'catalogue.json');cards=catalog['cards'];selected=set(catalog['modules']);spec=profile(catalog['target'])
    require(bool(selected) and selected<=registry.keys(),'Invalid selected modules')
    require(len({c['key'] for c in cards})==len(cards),'Duplicate card identity')
    require(len(cards)==sum(registry[m]['count'] for m in selected),'Wrong card count')
    recipe_folder='recipes' if spec['plural_paths'] else 'recipe'
    for module in selected:
        deck=read(output/f'datapack/data/tarot/{recipe_folder}/{module}_deck.json')['result']['components']
        require(deck['minecraft:custom_data']['tarot'].get('storage')=='native-v1','Factory deck does not use upgradeable native storage')
        require('cards' not in deck['minecraft:custom_data']['tarot'],'Duplicate opaque card authority in factory deck')
        require([c['components']['minecraft:custom_data']['tarot']['key'] for c in deck['minecraft:charged_projectiles']]==[c['key'] for c in cards if c['module']==module],'Wrong native factory order/items')
        require(all(c['id']=='minecraft:carrot_on_a_stick' for c in deck['minecraft:charged_projectiles']),'Factory cards can still substitute for vanilla paper')
        require('!minecraft:max_damage' in deck and all('!minecraft:max_damage' in c['components'] for c in deck['minecraft:charged_projectiles']),'Factory cards/bands can enter vanilla tool repair')
        advancement_folder='advancements' if spec['plural_paths'] else 'advancement'
        unlock=read(output/f'datapack/data/tarot/{advancement_folder}/recipes/{module}_deck.json')
        require('display' not in unlock and unlock['rewards']['recipes']==[f'tarot:{module}_deck'],'Recipe discovery is not quiet and native')
    for folder in ['datapack','resourcepack']:
        require(Image.open(output/folder/'pack.png').size==(128,128),'Missing or invalid pack icon')
        require(all((output/folder/name).is_file() for name in ['INSTALL.txt','CREDITS.txt']),'Missing release instructions/credits')
    for entry in read(ROOT/'source-lock.json')['files']:
        p=ROOT/safe_relative(entry['destination']);require(hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'Changed imported source: '+str(p))
    for card in cards:
        require(card['custom_model_data']==identities[card['key']],'Persistent model identity changed')
        module=card['module'];name=card['source_id'];require(module in selected,'Unselected card leaked')
        original=Image.open(ROOT/f'modules/{module}/{name}.png').convert('RGBA');padded=Image.open(output/f'resourcepack/assets/tarot/textures/card/{module}/{name}.png').convert('RGBA')
        require(padded.size==(128,128),'Wrong padded texture dimensions')
        require(original.tobytes()==padded.crop((0,0,*original.size)).tobytes(),'Changed original pixels: '+card['key'])
        if not spec['legacy_models']:
            item=read(output/f'resourcepack/assets/tarot/items/card/{module}/{name}.json');require(item['model']['model']==card['model'],'Wrong item model')
        else:
            item=read(output/'resourcepack/assets/minecraft/models/item/paper.json');require({'predicate':{'custom_model_data':card['custom_model_data']},'model':card['model']} in item['overrides'],'Missing legacy model override')
        model=read(output/f'resourcepack/assets/tarot/models/card/{module}/{name}.json');elem=model['elements'][0]
        require(abs((elem['to'][0]-elem['from'][0])/16-original.width/original.height)<1e-9,'Wrong aspect ratio')
        require(elem['to'][2]-elem['from'][2]==1,'Wrong card thickness')
        require(set(elem['faces'])=={'north','south','up','down','east','west'},'Incomplete physical card')
        require(all(elem['faces'][f]['uv']==[0,0,original.width/8,original.height/8] for f in ['north','south']),'Wrong front/back UV crop')
    for p in (output/'resourcepack/assets/tarot/models').rglob('*.json'):
        for ref in read(p)['textures'].values():
            if ref.startswith('tarot:'):require((output/'resourcepack/assets/tarot/textures'/(ref.split(':')[1]+'.png')).is_file(),'Missing texture: '+ref)
    for p in output.rglob('*.json'):read(p)
    for module in registry.keys()-selected:
        require(not (output/f'resourcepack/assets/tarot/textures/card/{module}').exists(),'Unselected art leaked')
        fn='functions' if spec['plural_paths'] else 'function';require(not (output/f'datapack/data/tarot/{fn}/give/{module}.mcfunction').exists(),'Unselected runtime leaked')
    for label,source in [('datapack','datapack'),('resources','resourcepack')]:
        archive=output/f'Tabletop-Tarot-{catalog["target"]}-{label}.zip';expanded=output/source;expected={p.relative_to(expanded).as_posix():p for p in expanded.rglob('*') if p.is_file()}
        with zipfile.ZipFile(archive) as z:
            names=z.namelist();require(len(names)==len(set(names)),'Duplicate ZIP member');require(set(names)==set(expected) and 'pack.mcmeta' in names,'ZIP/expanded file set differs');require(z.testzip() is None,'Corrupt ZIP')
            for name in names:safe_relative(name);require(z.read(name)==expected[name].read_bytes(),'ZIP/expanded bytes differ: '+name)
    manifest=read(output/'build.json');expected_files={safe_relative(e['path']):e['sha256'] for e in manifest['files']};actual={p.relative_to(output).as_posix():p for p in output.rglob('*') if p.is_file() and p!=output/'build.json'}
    require(set(expected_files)==set(actual),'Build manifest file set differs')
    for name,p in actual.items():require(hashlib.sha256(p.read_bytes()).hexdigest()==expected_files[name],'Build hash differs: '+name)
    result={'passed':True,'cards':len(cards),'modules':sorted(selected),'target':catalog['target'],'scope':'pinned source bytes, exact pixels, identities, geometry, references, module boundaries, hashes and ZIP/expanded equality; not a game-render claim'}
    if not quiet:print(json.dumps(result))
    return result
if __name__=='__main__':check(sys.argv[1])
