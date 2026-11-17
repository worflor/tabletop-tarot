"""Authoring contract: stable item identities, explicit modules and collision-free recipes."""
import json,os,re
from pathlib import Path

DEFAULT_ROOT=Path(os.environ.get('TAROT_PROJECT_ROOT',str(Path(__file__).resolve().parents[3])))/'content/tarot'
BANDS=('deck_empty','deck_one','deck_few','deck_small','deck_medium','deck')

def load(root=None):
    root=Path(root or DEFAULT_ROOT)
    document=json.loads((root/'core/modules.json').read_text(encoding='utf-8'))
    contract=json.loads((root/'core/item-identities.json').read_text(encoding='utf-8'))
    if type(document.get('schema'))is not int or document['schema']!=1 or type(contract.get('schema'))is not int or contract['schema']!=1:raise ValueError('Unsupported module/identity contract schema')
    modules=document.get('modules');identities=contract.get('models')
    if not isinstance(modules,dict) or not modules or not isinstance(identities,dict):raise ValueError('Empty or malformed module/identity contract')
    if any(not re.fullmatch(r'[a-z0-9_-]+/[a-z0-9_-]+',key) or type(value)is not int or not 1<=value<16777216 for key,value in identities.items()):raise ValueError('Model identity must be a stable key and exact legacy/float integer')
    if len(set(identities.values()))!=len(identities):raise ValueError('Duplicate persistent model identity; retired IDs must never be reused')
    from profiles import PROFILES
    vanilla=json.loads((root/'core/vanilla-recipe-ingredients.json').read_text(encoding='utf-8'))
    if vanilla.get('schema')!=1 or set(vanilla.get('sources',{}))!=set(PROFILES) or any(vanilla['sources'][v].get('server_sha1')!=p['server_sha1'] for v,p in PROFILES.items()):raise ValueError('Regenerate the official recipe-item contract for these Minecraft targets')
    common_ingredients=set(vanilla['ingredients'])
    ingredients=set();result={}
    for module,spec in modules.items():
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}',module) or not isinstance(spec,dict):raise ValueError('Invalid module ID/descriptor')
        ingredient=spec.get('ingredient')
        if not isinstance(ingredient,str) or not re.fullmatch(r'minecraft:[a-z0-9_]+',ingredient) or ingredient in ingredients:raise ValueError('Each module needs a distinct vanilla crafting ingredient')
        if ingredient in {'minecraft:air','minecraft:carrot_on_a_stick'}:raise ValueError('Recipe ingredients must not consume card carriers or use air')
        if ingredient not in common_ingredients:raise ValueError('Recipe ingredient is unavailable on a supported Minecraft target: '+ingredient)
        ingredients.add(ingredient)
        if type(spec.get('default',True)) is not bool:raise ValueError('Module default must be boolean')
        source=root/'modules'/module
        pack=json.loads((source/'pack.json').read_text(encoding='utf-8'));side=json.loads((source/'deck.json').read_text(encoding='utf-8'))
        cards=pack.get('cards',[])
        if not isinstance(cards,list) or not 1<=len(cards)<=128 or any(not isinstance(c,dict) for c in cards):raise ValueError('Module needs 1–128 card records: '+module)
        ids=[c.get('id') for c in cards]
        if any(not isinstance(key,str) or not re.fullmatch(r'[a-z0-9_-]{1,64}',key) or key in (*BANDS,'back') for key in ids):raise ValueError('Invalid/reserved card path: '+module)
        if len(set(ids))!=len(ids):raise ValueError('Duplicate card identity: '+module)
        if any(not isinstance(c.get('canonicalName'),str) or not c['canonicalName'] or any(ord(ch)<32 for ch in c['canonicalName']) or 'structureRef' not in c for c in cards):raise ValueError('Card needs a single-line canonical name and structureRef: '+module)
        required={module+'/'+key for key in ids+list(BANDS)}
        if not required<=identities.keys():raise ValueError('New cards/bands need persistent model allocations: '+str(sorted(required-identities.keys())))
        grid=side.get('grid')
        if not isinstance(grid,list) or len(grid)!=2 or any(type(v)is not int or not 1<=v<=128 for v in grid):raise ValueError('Plate grid must fit 128×128 without resampling: '+module)
        if grid[0]*16/grid[1]+.24>48:raise ValueError('Plate aspect exceeds vanilla model bounds: '+module)
        if not re.fullmatch(r'[a-z0-9_-]+\.png',str(side.get('back',''))):raise ValueError('Unsafe card back path: '+module)
        if spec.get('icon') not in ids:raise ValueError('Module icon must name one of its cards: '+module)
        result[module]={**spec,'default':spec.get('default',True),'count':len(cards)}
    if not any(m['default'] for m in result.values()):raise ValueError('At least one module must be included by default')
    if sum(m['count'] for m in result.values())>1024:raise ValueError('Catalogue exceeds the tested 1024-card command-work bound')
    # Unused allocations intentionally remain reserved: deleting content must
    # never make another card inherit its old art on a saved item.
    return result,identities

def select(requested=None,modules=None):
    modules=modules or load()[0]
    chosen=[m for m,s in modules.items() if s['default']] if requested is None else list(requested)
    if not chosen or len(chosen)!=len(set(chosen)) or set(chosen)-modules.keys():raise ValueError('Select registered card modules without duplicates')
    return [m for m in modules if m in chosen]

def suffix(selected,modules):
    return '' if selected==select(None,modules) else '-'+ '+'.join(selected)
