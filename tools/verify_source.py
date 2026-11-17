#!/usr/bin/env python3
"""Verify original-source provenance and compare effective pack content, not ZIP formatting."""
from __future__ import annotations
import argparse, hashlib, io, json, zipfile
from PIL import Image
from pathlib import Path
from build import ROOT, ORIGINAL, TARGETS, verify_upstream


def canonical(name: str, data: bytes):
    if name.endswith(('.json','.mcmeta')):
        return json.loads(data)
    if name.endswith('.png'):
        image = Image.open(io.BytesIO(data))
        return image.size, image.convert('RGBA').tobytes(), image.info.get('gamma'), image.info.get('icc_profile')
    if name.endswith('.mcfunction'):
        return data.decode('utf-8').splitlines()
    return data


def compare_maps(expected: dict, actual: dict, label: str) -> list[str]:
    errors = []
    for name in sorted(expected.keys() | actual.keys()):
        if name not in expected:
            errors.append(f'{label}: unexpected {name}')
        elif name not in actual:
            errors.append(f'{label}: missing {name}')
        elif canonical(name,expected[name]) != canonical(name,actual[name]):
            errors.append(f'{label}: changed {name}')
    return errors


def baseline_parity(archive: Path) -> list[str]:
    errors=[]
    archive_files(archive)  # Reject ambiguous member authority before comparing effective overlays.
    with zipfile.ZipFile(archive) as zf:
        for target in TARGETS:
            output = ORIGINAL / 'build' / ('java-' + target.mc_version)
            for directory, prefix, kind in [('datapack',target.data_dir,'data/'),('resourcepack',target.res_dir,'assets/')]:
                expected={n[len(prefix)+1:]:zf.read(n) for n in zf.namelist() if n.startswith(prefix+'/'+kind)}
                if kind=='assets/':
                    expected.update({n:zf.read(n) for n in zf.namelist() if n.startswith('assets/')})
                actual={p.relative_to(output/directory).as_posix():p.read_bytes() for p in (output/directory/kind).rglob('*') if p.is_file()}
                errors.extend(compare_maps(expected,actual,target.mc_version+' '+kind))
    return errors


def archive_files(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        seen = set()
        for name in names:
            if name in seen:
                raise ValueError(f'Duplicate ZIP member: {name}')
            seen.add(name)
        return {name:archive.read(name) for name in names}


def archive_parity(reference: Path, candidate: Path) -> list[str]:
    return compare_maps(archive_files(reference), archive_files(candidate), '1.1.0')


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,help='Released 1.0.0 combined ZIP; original builds must already exist')
    parser.add_argument('--reference',type=Path,help='Pre-import reviewed 1.1.0 combined ZIP')
    parser.add_argument('--candidate',type=Path,default=ROOT/'dist/Tabletop-Tarot-1.1.0.zip')
    parser.add_argument('--report',type=Path,default=ROOT/'build/source-parity.json')
    args=parser.parse_args()
    lock=verify_upstream();errors=[]
    archive_files(args.candidate)  # A receipt must never bind to an ambiguous candidate, even in baseline-only mode.
    if args.baseline:
        digest=hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        if digest != lock['release_archive_sha256']:
            raise ValueError('Baseline ZIP does not match the pinned released archive')
        errors.extend(baseline_parity(args.baseline))
    if args.reference:
        errors.extend(archive_parity(args.reference,args.candidate))
    report={'upstream_commit':lock['commit'],'original_files_verified':len(lock['files']),
        'baseline_targets_compared':len(TARGETS) if args.baseline else 0,'reviewed_1_1_0_compared':bool(args.reference),
        'baseline_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None,
        'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest() if args.reference else None,
        'comparison':'Parsed JSON, function lines, decoded PNG pixels/color profiles, and exact bytes for other files. ZIP metadata, JSON formatting, CRLF and PNG compression are not runtime changes.',
        'candidate_sha256':hashlib.sha256(args.candidate.read_bytes()).hexdigest(),'errors':errors,'passed':not errors}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({**report,"errors":errors[:20],"error_count":len(errors)},indent=2))
    return 1 if errors else 0


if __name__=='__main__':
    raise SystemExit(main())
