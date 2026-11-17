#!/usr/bin/env python3
"""Build from the pinned original implementation plus explicit reviewed extensions."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'

@dataclass(frozen=True)
class VersionTarget:
    mc_version: str
    data_format: tuple[int,int]
    res_format: tuple[int,int]
    data_dir: str
    res_dir: str
    plural_folders: bool
    component_era: str
    modern_gamerule: bool

_PROFILES = json.loads((ROOT / 'vendor/commonground-server/content/tarot/profiles.json').read_text())
def _pair(value): return tuple(value) if isinstance(value,list) else (value,0)
TARGETS = [VersionTarget(v, _pair(p['data']), _pair(p['resource']),
    'data_%d_%d' % _pair(p['data']), 'resource_%d_%d' % _pair(p['resource']),
    p['plural_paths'], 'modern' if p['text_objects'] else 'early',
    p['command_rule']=='minecraft:max_command_sequence_length') for v,p in _PROFILES.items()]


def adapt_function_text(rel: str, text: str, target: VersionTarget) -> str:
    # Only the extension's captured offhand uses a version-dependent entity path.
    # Base carrier/codec adaptations belong to the original generators.
    if target.component_era == "early":
        text = text.replace('entity @s equipment.offhand', 'entity @s Inventory[{Slot:-106b}]')

    # Wall-only pale moss has no horizontal base and cannot support a card.
    if target.data_format[0] >= 61:
        if rel == "table/carpet.mcfunction":
            text = 'execute if block ~ ~ ~ minecraft:pale_moss_carpet[bottom=false] run return run function tarot:table/step\n' + text
        if rel == "table/support.mcfunction":
            text = text.replace('execute unless score #supported', 'execute positioned ~ ~-0.03 ~ if block ~ ~ ~ minecraft:pale_moss_carpet[bottom=false] run scoreboard players set #supported tarot.sys 0\nexecute unless score #supported')

    if not target.modern_gamerule:
        text = text.replace("gamerule minecraft:max_command_sequence_length", "gamerule maxCommandChainLength")

    return text

def make_pack_mcmeta(include_data: bool = True) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for t in TARGETS:
        if include_data:
            entries.append({
                "directory": t.data_dir,
                "min_format": list(t.data_format),
                "max_format": list(t.data_format),
                "formats": t.data_format[0],
            })
        entries.append({
            "directory": t.res_dir,
            "min_format": list(t.res_format),
            "max_format": list(t.res_format),
            "formats": t.res_format[0],
        })
    return {
        "pack": {
            "description": "Tabletop Tarot — 78+ illustrated cards to shuffle, draw, trade and lay on your own tables. You decide what they mean.",
            "min_format": [32, 0],
            "max_format": [121, 0],
            "pack_format": 32,
            "supported_formats": [32, 121],
        },
        "overlays": {"entries": entries},
    }

def zip_dir(folder: Path, dest_zip: Path) -> None:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                arc = str(p.relative_to(folder))
                info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, p.read_bytes())

# Original source remains byte-for-byte pinned; this layer owns only release packaging
# and the reviewed 1.1.0 extensions listed in src/overrides.json.
VENDOR = ROOT / 'vendor/commonground-server'
ORIGINAL = VENDOR / 'content/tarot'


def verify_upstream() -> dict:
    lock = json.loads((VENDOR / 'source-lock.json').read_text())
    for relative, expected in lock['files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f'Unsafe upstream path: {relative}')
        if hashlib.sha256((VENDOR / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Original source changed without updating its provenance: {relative}')
    return lock


def original_build(target: VersionTarget) -> Path:
    result = subprocess.run([sys.executable, str(ORIGINAL / 'tools/build.py'), '--target', target.mc_version],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'Original {target.mc_version} generator failed:\n{result.stdout}\n{result.stderr}')
    return ORIGINAL / 'build' / ('java-' + target.mc_version)


def replace_exact(text: str, before: str, after: str, path: str) -> str:
    if text.count(before) != 1:
        raise ValueError(f'Extension no longer matches the original generator: {path}: {before}')
    return text.replace(before, after, 1)


def extend_data(folder: Path, target: VersionTarget) -> dict:
    fn = folder / 'data/tarot' / ('functions' if target.plural_folders else 'function')
    manifest = json.loads((SRC / 'overrides.json').read_text())
    if manifest['upstream_commit'] != json.loads((VENDOR / 'source-lock.json').read_text())['commit']:
        raise ValueError('Extensions target a different original source revision')
    actual = {p.relative_to(SRC / 'functions').as_posix() for p in (SRC / 'functions').rglob('*.mcfunction')}
    if actual != set(manifest['functions']):
        raise ValueError('Function overrides differ from src/overrides.json')
    for relative in manifest['functions']:
        output = fn / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(adapt_function_text(relative, (SRC / 'functions' / relative).read_text(), target), encoding='utf-8', newline='\n')

    path = fn / 'table/place.mcfunction'
    text = path.read_text()
    text = replace_exact(text, 'scoreboard players set #ray tarot.sys 45',
                         'scoreboard players set #dealing tarot.sys 0\nscoreboard players set #ray tarot.sys 100', str(path))
    text = replace_exact(text, 'Aim at a clear tabletop or slab within reach.',
                         'Aim at a clear tabletop surface within reach.', str(path))
    path.write_text(text, encoding='utf-8', newline='\n')

    from optimizations import native_validation, descending_shuffle
    catalogue = json.loads((ORIGINAL/'build'/('java-'+target.mc_version)/'catalogue.json').read_text())
    (fn/'native/validate.mcfunction').write_text(native_validation(catalogue['cards'], _PROFILES[target.mc_version].get('implicit_nested_count', False)), encoding='utf-8', newline='\n')

    path = fn/'stack/sync.mcfunction'
    text = replace_exact(path.read_text(),
        'data modify storage tarot:runtime prepared set from entity @s SelectedItem',
        '\n'.join([
            '# Consume the fresh validated snapshot, never another player or prior tick.',
            'execute unless data storage tarot:transaction main.id run return 0',
            'data modify storage tarot:runtime prepared set from storage tarot:transaction main',
            'data remove storage tarot:transaction main',
        ]),str(path))
    path.write_text(text,encoding='utf-8',newline='\n')

    path = fn / 'native/stage.mcfunction'
    text = path.read_text()
    before = 'execute if score #promoted tarot.sys matches 0 if score #consume tarot.sys matches 0 run function tarot:native/verify_array'
    text = replace_exact(text, before, before.replace(' run function', ' unless score #returning tarot.sys matches 1 run function'), str(path))
    dispatch = []
    for i in range(128):
        dispatch.extend([
            f'execute if score #promoted tarot.sys matches 1 if score #size tarot.roll matches {i+1}.. run function tarot:native/codec_{i}',
            f'execute if score #promoted tarot.sys matches 0 if score #consume tarot.sys matches 1 if score #size tarot.roll matches {i+1}.. run function tarot:native/codec_{i}',
        ])
        codec = fn / f'native/codec_{i}.mcfunction'
        code = codec.read_text()
        before = 'execute if score #promoted tarot.sys matches 1 run function tarot:native/normalize_factory'
        code = replace_exact(code, before, before + '\nexecute if score #returning tarot.sys matches 1 run function tarot:native/normalize_factory', str(codec))
        codec.write_text(code, encoding='utf-8', newline='\n')
    # These transaction flags are constant throughout the item loop. Decide once.
    text = replace_exact(text, '\n'.join(dispatch), '\n'.join([
        'execute if score #promoted tarot.sys matches 1 run function tarot:native/verify_items',
        'execute if score #promoted tarot.sys matches 0 if score #consume tarot.sys matches 1 run function tarot:native/verify_items',
        'execute if score #promoted tarot.sys matches 0 if score #consume tarot.sys matches 0 if score #returning tarot.sys matches 1 run function tarot:native/verify_items',
    ]), str(path))
    (fn/'native/verify_items.mcfunction').write_text(''.join(
        f'execute if score #size tarot.roll matches {i+1}.. run function tarot:native/codec_{i}\n' for i in range(128)), encoding='utf-8', newline='\n')
    path.write_text(text, encoding='utf-8', newline='\n')

    path = fn / 'stack/shuffle.mcfunction'
    text = path.read_text()
    forward = []
    for i in range(127):
        guard = f'execute if score #size tarot.roll matches {i+2}..'
        forward.extend([
            guard+f' run scoreboard players set #i tarot.i {i}',
            guard+' run scoreboard players operation #max tarot.j = #size tarot.roll',
            guard+f' run scoreboard players remove #max tarot.j {i+1}',
            guard+' store result storage tarot:shuffle max int 1 run scoreboard players get #max tarot.j',
            guard+' run function tarot:stack/random with storage tarot:shuffle',
            guard+' run scoreboard players operation #j tarot.j += #i tarot.i',
            guard+' store result storage tarot:shuffle j int 1 run scoreboard players get #j tarot.j',
            guard+f' run function tarot:stack/swap_{i} with storage tarot:shuffle',
        ])
    text = replace_exact(text, '\n'.join(forward), '\n'.join([
        'execute store result storage tarot:shuffle size int 1 run scoreboard players get #size tarot.roll',
        'execute if score #size tarot.roll matches 2..128 run function tarot:stack/shuffle_start with storage tarot:shuffle',
    ]), str(path))
    for relative, source in descending_shuffle().items():
        output = fn/relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source, encoding='utf-8', newline='\n')
    text = replace_exact(text,
        'execute if score #size tarot.roll matches 2.. run function tarot:sound/shuffle',
        'execute if score #committed tarot.sys matches 1 if score #size tarot.roll matches 2.. run function tarot:sound/shuffle', str(path))
    path.write_text(text, encoding='utf-8', newline='\n')

    tags = folder / 'data/tarot/tags' / ('blocks' if target.plural_folders else 'block')
    for name in manifest['block_tags']:
        obj = json.loads((SRC / 'tags/block' / name).read_text())
        if name == 'table_surface.json':
            if target.data_format[0] >= 48:
                obj['values'].extend(['minecraft:polished_tuff','minecraft:tuff_bricks','minecraft:chiseled_tuff','minecraft:chiseled_tuff_bricks',
                    'minecraft:chiseled_copper','minecraft:exposed_chiseled_copper','minecraft:weathered_chiseled_copper','minecraft:oxidized_chiseled_copper',
                    'minecraft:waxed_chiseled_copper','minecraft:waxed_exposed_chiseled_copper','minecraft:waxed_weathered_chiseled_copper','minecraft:waxed_oxidized_chiseled_copper','minecraft:crafter'])
            if target.data_format[0] >= 61:
                obj['values'].extend(['minecraft:resin_bricks','minecraft:chiseled_resin_bricks'])
        elif name == 'carpets.json' and target.data_format[0] >= 61:
            obj['values'].append('minecraft:pale_moss_carpet')
        (tags / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

    advancements = folder / 'data/tarot' / ('advancements' if target.plural_folders else 'advancement')
    actual = {p.relative_to(SRC / 'advancements').as_posix() for p in (SRC / 'advancements').rglob('*.json')}
    if actual != set(manifest['advancements']):
        raise ValueError('Advancement extensions differ from src/overrides.json')
    for relative in manifest['advancements']:
        output = advancements / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes((SRC / 'advancements' / relative).read_bytes())

    from guidebook import write as write_guidebook
    guide=manifest['guidebook']
    return write_guidebook(folder,target,catalogue['cards'],_PROFILES[target.mc_version],
                          {edition:SRC/path for edition,path in guide['editions'].items()},guide['generated_json'])


def invalidate_stale_parity(out_dir: Path, archive: Path) -> None:
    """Keep a historical comparison visible, but never present it as proof of different bytes."""
    path = out_dir / 'source-parity.json'
    if not path.exists():
        return
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError:
        report = {}
    if not isinstance(report, dict):
        report = {}
    current = hashlib.sha256(archive.read_bytes()).hexdigest()
    if report.get('candidate_sha256') == current:
        return
    report.update(previously_passed=report.get('previously_passed', report.get('passed', False)), passed=False, stale=True,
                  superseded_by_sha256=current, reason='Archive changed or prior receipt is invalid; rerun source verification.')
    path.write_text(json.dumps(report, indent=2)+'\n')


def build(version: str = '1.1.0', out_dir: Path | None = None, staging_dir: Path | None = None) -> tuple[Path, Path]:
    lock = verify_upstream()
    out_dir = (out_dir or ROOT / 'dist').resolve()
    stage = (staging_dir or ROOT / 'build/staging').resolve()
    if stage.exists():
        shutil.rmtree(stage)
    combined, respack = stage / 'combined', stage / 'resourcepack'
    combined.mkdir(parents=True); respack.mkdir(parents=True)
    outputs = {}
    common = None
    book_index = None
    for target in TARGETS:
        print(f'Generating {target.mc_version} from original source...', flush=True)
        original = original_build(target)
        data = combined / target.data_dir
        shutil.copytree(original / 'datapack/data', data / 'data')
        index = extend_data(data, target)
        if book_index is None:book_index=index
        elif index != book_index:raise ValueError('Guidebook navigation differs across version adapters')
        assets = {p.relative_to(original / 'resourcepack').as_posix(): p.read_bytes()
                  for p in (original / 'resourcepack/assets').rglob('*') if p.is_file()}
        from guidebook_models import assets as guidebook_assets
        additions=guidebook_assets(_PROFILES[target.mc_version])
        if assets.keys() & additions.keys():raise ValueError('Guide assets would replace original card assets')
        assets.update(additions)
        # Custom texture directories must be declared to the vanilla atlas.
        # Extend the original source list rather than replacing card sprites.
        atlas_name='assets/minecraft/atlases/blocks.json'
        atlas=json.loads(assets[atlas_name])
        atlas['sources'].append({'type':'minecraft:directory','source':'guidebook','prefix':'guidebook/'})
        assets[atlas_name]=(json.dumps(atlas,indent=2)+'\n').encode()
        common = dict(assets) if common is None else {n:b for n,b in common.items() if assets.get(n) == b}
        outputs[target.mc_version] = assets
    for root in (combined, respack):
        for name, data in common.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        for target in TARGETS:
            for name, data in outputs[target.mc_version].items():
                if name in common: continue
                path = root / target.res_dir / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        for name in ('CREDITS.txt','LICENSE.md','pack.png'):
            shutil.copy2(ROOT / name, root / name)
        shutil.copytree(ROOT / 'licenses', root / 'licenses')
        (root / 'pack.mcmeta').write_text(json.dumps(make_pack_mcmeta(include_data=root==combined), indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    shutil.copy2(SRC / 'INSTALL.txt', combined / 'INSTALL.txt')
    marker = combined / 'data/tabletop_tarot/README.txt'; marker.parent.mkdir(parents=True)
    marker.write_text('Tabletop Tarot datapack. Runtime content is selected from version overlays. This file is inert.\n', encoding='utf-8')
    # Build everything before replacing the last installable archives.
    out_dir.mkdir(parents=True, exist_ok=True)
    names = (f'Tabletop-Tarot-{version}.zip', f'Tabletop-Tarot-{version}-resourcepack.zip')
    # Stage archives on the destination filesystem so replacements are atomic even with --out-dir.
    with tempfile.TemporaryDirectory(prefix='.tarot-archives-', dir=out_dir) as temporary:
        pending = Path(temporary)
        for folder, name in zip((combined,respack), names):
            zip_dir(folder, pending / name)
            for algo in ('sha1','sha256'):
                digest = hashlib.new(algo, (pending / name).read_bytes()).hexdigest()
                (pending / (name+'.'+algo)).write_text(f'{digest}  {name}\n', encoding='utf-8')
        for path in pending.iterdir():
            os.replace(path, out_dir / path.name)
    invalidate_stale_parity(out_dir, out_dir / names[0])
    (out_dir/'guidebook-index.json').write_text(json.dumps(book_index,indent=2)+'\n',encoding='utf-8')
    (out_dir / 'source-provenance.json').write_text(json.dumps({'upstream_commit':lock['commit'],
        'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'generators_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (Path(__file__), ROOT/'tools/optimizations.py', ROOT/'tools/guidebook.py', ROOT/'tools/guidebook_models.py')},
        'guidebook_index_sha256':hashlib.sha256((out_dir/'guidebook-index.json').read_bytes()).hexdigest(),
        'upstream_source_lock_sha256':hashlib.sha256((VENDOR/'source-lock.json').read_bytes()).hexdigest(),
        'extensions_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SRC.rglob('*')) if p.is_file()},
        'archives':{name:hashlib.sha256((out_dir/name).read_bytes()).hexdigest() for name in names}}, indent=2)+'\n')
    return tuple(out_dir / name for name in names)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', default='1.1.0')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    for archive in build(version=args.version, out_dir=args.out_dir):
        print(f'Built: {archive} ({archive.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
