"""Build a selected physical-card collection; no mod compiler or runtime required."""
from pathlib import Path
import argparse, hashlib, json, shutil, zipfile, uuid, re, tempfile
from PIL import Image
from runtime import generate

ROOT = Path(__file__).resolve().parents[1]
from profiles import PROFILES, profile,STACK_MODELS
from module_registry import load as load_modules,select as select_modules,suffix as module_suffix

def pack_description(modules):
    cards = '78+ illustrated cards' if 'rider' in modules else 'Illustrated cards'
    return 'Tabletop Tarot — ' + cards + ' to shuffle, draw, trade and lay on your own tables. You decide what they mean.'

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def pack_zip(source, target):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(source.rglob('*')):
            if p.is_file():
                info = zipfile.ZipInfo(p.relative_to(source).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())

def build(target='1.21.4', modules=None):
    registry,identities=load_modules(ROOT);modules=select_modules(modules,registry)
    spec=profile(target)
    from check import safe_relative
    lock=json.loads((ROOT/'source-lock.json').read_text(encoding='utf-8'))
    for entry in lock['files']:
        if hashlib.sha256((ROOT/safe_relative(entry['destination'])).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Imported source changed: '+entry['destination'])
    # Stage first: a failed build leaves the previous installable build intact.
    build_root=(ROOT/'build').resolve();build_root.mkdir(exist_ok=True)
    name='java-'+target+module_suffix(modules,registry)
    final=build_root/name
    with tempfile.TemporaryDirectory(prefix='.stage-'+name+'-',dir=build_root) as temporary:
        out=Path(temporary).resolve()
        if out.parent!=build_root:raise ValueError('Unsafe staging directory')
        dp=out/'datapack';rp=out/'resourcepack'
        df,rf=spec['data'],spec['resource']
        for folder,fmt in [(dp,df),(rp,rf)]:
            write(folder/'pack.mcmeta',{'pack':{**({'min_format':fmt,'max_format':fmt} if isinstance(fmt,list) else {'pack_format':fmt}),'description':pack_description(modules)}})
            from presentation import write_release
            write_release(folder,modules,root=ROOT)
        write(rp/'assets/minecraft/atlases/blocks.json',{'sources':[{'type':'minecraft:directory','source':'card','prefix':'card/'}]})
        display=json.loads((ROOT/'core/display-source.json').read_text(encoding='utf-8'))['display']
        textures=rp/'assets/tarot/textures/card';textures.mkdir(parents=True)
        shutil.copyfile(ROOT/'core/edge_vellum.png', textures/'edge.png')
        cards=[]; overrides={'paper':[], 'carrot_on_a_stick':[]}
        for module in modules:
            source=ROOT/'modules'/module
            pack=json.loads((source/'pack.json').read_text(encoding='utf-8'))
            side=json.loads((source/'deck.json').read_text(encoding='utf-8'))
            width,height=side['grid'];w=16*width/height
            if len(pack['cards'])!=registry[module]['count'] or len({c['id'] for c in pack['cards']})!=len(pack['cards']):
                raise ValueError('Invalid card identity count: '+module)
            if any(not re.fullmatch(r'[a-z0-9_-]+',c['id']) for c in pack['cards']):
                raise ValueError('Invalid card path: '+module)
            for name in [side['back']]+[c['id']+'.png' for c in pack['cards']]:
                original=Image.open(source/name).convert('RGBA')
                if original.size!=(width,height):raise ValueError('Wrong plate dimensions: '+name)
                # Pad without resampling, so the plate's actual pixels survive exactly.
                canvas=Image.new('RGBA',(128,128));canvas.paste(original,(0,0))
                dest=textures/module/name;dest.parent.mkdir(parents=True,exist_ok=True);canvas.save(dest)
            def model(name,front,thickness):
                faces={f:{'texture':'#edge','uv':[0,0,16,16]} for f in ['up','down','east','west']}
                faces.update(south={'texture':'#front','uv':[0,0,width/8,height/8]},north={'texture':'#back','uv':[0,0,width/8,height/8]})
                value={'gui_light':'front','ambientocclusion':False,'textures':{'front':f'tarot:card/{module}/{front}','back':f'tarot:card/{module}/back','edge':'tarot:card/edge','particle':f'tarot:card/{module}/back'},'elements':[{'from':[8-w/2,0,8-thickness/2],'to':[8+w/2,16,8+thickness/2],'faces':faces}],'display':display}
                write(rp/f'assets/tarot/models/card/{module}/{name}.json',value)
                if not spec['legacy_models']:
                    write(rp/f'assets/tarot/items/card/{module}/{name}.json',{'model':{'type':'minecraft:model','model':f'tarot:card/{module}/{name}'}})
            # A narrow plain paper band stays present even when the stack is empty.
            for label,lo,hi,thickness,number in STACK_MODELS:
                name='deck'+('' if label=='full' else '_'+label);model(name,'back',thickness)
                path=rp/f'assets/tarot/models/card/{module}/{name}.json';value=json.loads(path.read_text(encoding='utf-8'))
                if label=='empty':value['elements']=[]
                x0,x1=8-w/2-.12,8+w/2+.12;z0,z1=8-thickness/2-.12,8+thickness/2+.12
                edges=[([x0,2.8,z0],[x1,4.2,z0+.12]),([x0,2.8,z1-.12],[x1,4.2,z1]),([x0,2.8,z0],[x0+.12,4.2,z1]),([x1-.12,2.8,z0],[x1,4.2,z1])]
                for a,b in edges:value['elements'].append({'from':a,'to':b,'faces':{face:{'texture':'#edge','uv':[0,0,16,16]} for face in ['north','south','up','down','east','west']}})
                write(path,value)
                overrides['carrot_on_a_stick'].append({'predicate':{'custom_model_data':identities[module+'/'+name]},'model':f'tarot:card/{module}/{name}'})
            for c in pack['cards']:
                key=module+'/'+c['id']; model(c['id'],c['id'],1)
                overrides['paper'].append({'predicate':{'custom_model_data':identities[key]},'model':'tarot:card/'+key})
                overrides['carrot_on_a_stick'].append({'predicate':{'custom_model_data':identities[key]},'model':'tarot:card/'+key})
                cards.append({'key':key,'name':c['canonicalName'],'module':module,'model':'tarot:card/'+key,'slot':c['structureRef'],'source_id':c['id'],'custom_model_data':identities[key],'deck_name':pack['manifest']['name']+' Deck'})
            # Canonical metadata travels intact, with no spells or mod registries.
            write(dp/f'data/tarot/physical_cards/{module}.json',{'pack':pack,'presentation':side})
        if spec['legacy_models']:
            for item, entries in overrides.items():
                ordered=sorted(entries,key=lambda e:e['predicate']['custom_model_data']);bounded=[]
                # Legacy predicates are lower bounds, too. Stop our IDs spilling over
                # into unrelated custom items with a larger model number.
                for i,entry in enumerate(ordered):
                    bounded.append(entry);code=entry['predicate']['custom_model_data']
                    if i==len(ordered)-1 or ordered[i+1]['predicate']['custom_model_data']>code+1:
                        bounded.append({'predicate':{'custom_model_data':code+1},'model':'minecraft:item/'+item+'_tarot_fallback'})
                fallback={'parent':'minecraft:item/'+('generated' if item=='paper' else 'handheld_rod'),'textures':{'layer0':'minecraft:item/'+item}}
                write(rp/f'assets/minecraft/models/item/{item}_tarot_fallback.json',fallback)
                write(rp/f'assets/minecraft/models/item/{item}.json',{**fallback,'overrides':bounded})
        else:
            # Vanilla upgrades the old numeric CMD component, but cannot invent our item_model.
            # Keep old loose/table/container cards visible after a world upgrade, before any interaction.
            for item,entries in overrides.items():
                fallback={'type':'minecraft:model','model':'minecraft:item/'+item};ranges=[]
                ordered=sorted(entries,key=lambda e:e['predicate']['custom_model_data'])
                for i,entry in enumerate(ordered):
                    code=entry['predicate']['custom_model_data'];ranges.append({'threshold':code,'model':{'type':'minecraft:model','model':entry['model']}})
                    if i==len(ordered)-1 or ordered[i+1]['predicate']['custom_model_data']>code+1:ranges.append({'threshold':code+1,'model':fallback})
                write(rp/f'assets/minecraft/items/{item}.json',{'model':{'type':'minecraft:range_dispatch','property':'minecraft:custom_model_data','index':0,'fallback':fallback,'entries':ranges}})
        generate(dp,cards,modules,target,registry,identities)
        if spec['plural_paths']:
            for old,new in [('function','functions'),('recipe','recipes'),('predicate','predicates'),('item_modifier','item_modifiers'),('advancement','advancements'),('loot_table','loot_tables')]:
                p=dp/'data/tarot'/old
                if p.exists():p.rename(p.with_name(new))
            p=dp/'data/minecraft/tags/function'
            if p.exists():p.rename(p.with_name('functions'))
            p=dp/'data/tarot/tags/block'
            if p.exists():p.rename(p.with_name('blocks'))
            p=dp/'data/tarot/tags/item'
            if p.exists():p.rename(p.with_name('items'))
        write(out/'catalogue.json',{'modules':modules,'cards':cards,'target':target})
        for folder,label in [(dp,'datapack'),(rp,'resources')]:
            pack_zip(folder,out/f'Tabletop-Tarot-{target}-{label}.zip')
        write(out/'build.json',{'target':target,'modules':modules,'cards':len(cards),'source_ref':lock['verified_ref'],'files':[{'path':p.relative_to(out).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.rglob('*')) if p.is_file()]})
        from check import check
        check(out,quiet=True,source_root=ROOT)
        previous=build_root/('.previous-'+name+'-'+uuid.uuid4().hex)
        if final.exists():
            if final.is_symlink() or final.resolve().parent!=build_root:raise ValueError('Unsafe output path')
            final.rename(previous)
        try:out.rename(final)
        except Exception:
            if previous.exists():previous.rename(final)
            raise
        if previous.exists():
            if previous.resolve().parent!=build_root:raise ValueError('Unsafe previous build path')
            shutil.rmtree(previous)
        print(json.dumps({'target':target,'cards':len(cards),'modules':modules,'output':str(final)}))
        return final

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',choices=PROFILES,default='1.21.4');p.add_argument('--modules',nargs='+',choices=load_modules()[0]);a=p.parse_args();build(a.target,a.modules)
