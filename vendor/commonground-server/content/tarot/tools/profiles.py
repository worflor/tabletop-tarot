"""Explicit adapters; format/Java pins are taken from official server metadata."""
import json
from pathlib import Path

PROFILES = json.loads((Path(__file__).resolve().parents[1]/'profiles.json').read_text(encoding='utf-8'))

def profile(version):
    if version not in PROFILES:
        raise ValueError(f'Unsupported target: {version!r}')
    return PROFILES[version]

def model_components(card, version):
    if profile(version)['legacy_models']:
        return {'minecraft:custom_model_data':card['custom_model_data']}
    return {'minecraft:item_model':card['model']}

# Small deliberate silhouette steps remain legible at Minecraft's scale.
STACK_MODELS=[('empty',0,0,.8,990),('one',1,1,1.0,991),('few',2,8,1.4,992),('small',9,32,1.9,993),('medium',33,64,2.4,994),('full',65,128,3.0,999)]

def stack_model_components(module,count,version,identities=None):
    label,_,_,_,number=next(row for row in STACK_MODELS if row[1]<=count<=row[2])
    model=f'tarot:card/{module}/deck'+('' if label=='full' else '_'+label)
    if identities is None:
        from module_registry import load
        identities=load()[1]
    return model_components({'model':model,'custom_model_data':identities[module+'/deck'+('' if label=='full' else '_'+label)]},version)
