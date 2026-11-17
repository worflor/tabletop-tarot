"""Compile compact book textures and vanilla cuboid models for every adapter.

Source artwork is preserved in src/guidebook/art. Atlas packing is deterministic:
nearest-neighbour 80x112 front/back art on a 256x128 texture, with no runtime work.
"""
from __future__ import annotations
import io,json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MODEL_IDS={'steve':170000,'alex':170001}


def appearance(author,spec):
    return ({'minecraft:custom_model_data':MODEL_IDS[author]} if spec['legacy_models'] else
            {'minecraft:item_model':'tarot:guidebook/'+author})


def book_model(author):
    cover=[0,0,5,14];back=[10,0,5,14];leather=[1,1.5,4.5,3.2];spine=[.01,0,.51,14]
    # Each material samples a quiet, opaque region of the packed cover texture.
    ribbon=[2.6,4.5,2.775,4.85] if author=='steve' else [2.2,5.1,2.375,5.45]
    def cube(start,end,material,uv,overrides=None):
        faces={side:{'texture':material,'uv':uv} for side in ['north','south','up','down','east','west']}
        faces.update(overrides or {})
        return {'from':start,'to':end,'faces':faces}
    elements=[
        cube([3.15,1.4,7.1],[12.85,14.6,8.9],'#pages',[0,0,16,16]),
        cube([2.8,1,8.9],[13.2,15,9.35],'#cover',leather,{'south':{'texture':'#cover','uv':cover}}),
        cube([2.8,1,6.65],[13.2,15,7.1],'#cover',leather,{'north':{'texture':'#cover','uv':back}}),
        cube([2.65,1,6.65],[3.45,15,9.35],'#cover',spine),
        cube([10.7,.05 if author=='steve' else -.45,8.65],[11.35,2.1,8.9],'#cover',ribbon),
    ]
    return {'gui_light':'front','ambientocclusion':False,
            'textures':{'cover':'tarot:guidebook/'+author,'pages':'tarot:card/edge','particle':'tarot:guidebook/'+author},
            'elements':elements,'display':{
                'gui':{'rotation':[12,-28,-6],'translation':[0,.2,0],'scale':[.97,.97,.97]},
                'ground':{'rotation':[0,0,0],'translation':[0,2,0],'scale':[.5,.5,.5]},
                'fixed':{'rotation':[0,180,0],'translation':[0,0,0],'scale':[.95,.95,.95]},
                'firstperson_righthand':{'rotation':[0,-25,0],'translation':[-.8,5.5,-.5],'scale':[.45,.45,.45]},
                'firstperson_lefthand':{'rotation':[0,25,0],'translation':[.8,5.5,-.5],'scale':[.45,.45,.45]},
                'thirdperson_righthand':{'rotation':[75,45,0],'translation':[0,2.5,.5],'scale':[.5,.5,.5]},
                'thirdperson_lefthand':{'rotation':[75,45,0],'translation':[0,2.5,.5],'scale':[.5,.5,.5]},
            }}


def assets(spec):
    def encoded(value):return (json.dumps(value,indent=2)+'\n').encode()
    out={}
    # Collision check against the pinned identity registry without modifying it.
    identities=json.loads((ROOT/'vendor/commonground-server/content/tarot/core/item-identities.json').read_text())['models']
    if set(MODEL_IDS.values()) & set(identities.values()):
        raise ValueError('Guide identities overlap card identities')
    for author in MODEL_IDS:
        atlas=Image.new('RGBA',(256,128))
        for face,x in [('cover',0),('back',80)]:
            with Image.open(ROOT/f'src/guidebook/art/{author}-{face}-source.png') as source:
                panel=source.convert('RGBA').resize((80,112),Image.Resampling.NEAREST)
            atlas.paste(panel,(x,0))
        buffer=io.BytesIO();atlas.save(buffer,format='PNG',optimize=True)
        out[f'assets/tarot/textures/guidebook/{author}.png']=buffer.getvalue()
        out[f'assets/tarot/models/guidebook/{author}.json']=encoded(book_model(author))
        if not spec['legacy_models']:
            out[f'assets/tarot/items/guidebook/{author}.json']=encoded({'model':{'type':'minecraft:model','model':'tarot:guidebook/'+author}})
    if spec['legacy_models']:
        out['assets/tarot/models/guidebook/vanilla.json']=encoded({
            'parent':'minecraft:item/generated','textures':{'layer0':'minecraft:item/written_book'}})
        out['assets/minecraft/models/item/written_book.json']=encoded({
            'parent':'minecraft:item/generated','textures':{'layer0':'minecraft:item/written_book'},
            'overrides':[{'predicate':{'custom_model_data':number},'model':'tarot:guidebook/'+author}
                         for author,number in MODEL_IDS.items()]+
                        [{'predicate':{'custom_model_data':max(MODEL_IDS.values())+1},'model':'tarot:guidebook/vanilla'}]})
    return out
