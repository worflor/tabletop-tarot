"""Reproduce the quiet-integration and real resource-stack release checks."""
import argparse,json
from game_lab import ROOT,sha

def main(stage,native_ui=False):
    from pathlib import Path
    if stage=='resources':
        from universal_native_lab import main as native
        from resource_compat_lab import CACHE
        for version in ['1.20.6','1.21.11']:
            extra=[CACHE/(slug+'-'+version+'.zip') for slug in ['faithful-32x','bare-bones','3d-default']]
            for order in ['above','below']:native(version,resources_only=True,receipt_prefix='modrinth-'+order,extra_resources=extra,cards_below=order=='below',visual_hold=native_ui and version=='1.21.11' and order=='above')
        current=sha(ROOT/'content/tarot/build/universal/Tabletop-Tarot-Universal.zip')
        receipts=[ROOT/f'content/tarot/evidence/universal-{kind}-26.3.json' for kind in ['client','backend']]
        cached=[json.loads(p.read_text(encoding='utf-8')) if p.exists() else {} for p in receipts]
        if all(r.get('passed') and r.get('combined_zip_sha256')==current for r in cached) and len(cached[1].get('checks',[]))==15:
            print('Reusing the already-passed 26.3 stock-client checks for this exact ZIP.',flush=True)
        else:native('26.3')
    elif stage=='quiet':
        from quiet_lab import main as quiet
        for version in ['1.20.6','1.21.3','1.21.11','26.1.2']:quiet(version)
    elif stage=='refinement':
        from refinement_lab import main as refinement
        for version in ['1.20.6','1.21.11','26.1.2']:refinement(version)
    elif stage=='supplemental':
        from supplemental_lab import subset,crowd
        from upgrade_game_lab import main as upgrade
        import subprocess,sys
        subset('1.20.6','rider',ROOT/'content/tarot/build/universal-rider')
        subset('1.21.11','numbers',ROOT/'content/tarot/build/universal-numbers')
        crowd(True)
        subprocess.run([sys.executable,'-u','-B',str(Path(__file__).with_name('payload_lab.py')),'--version','1.21.11'],check=True)
        upgrade('1.20.6','1.21.11')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['quiet','resources','supplemental','refinement'],required=True);p.add_argument('--native-ui',action='store_true');a=p.parse_args()
    main(a.stage,a.native_ui)
