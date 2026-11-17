"""Focused native-server regression after the customization-preservation change."""
import argparse,json
from pathlib import Path
from profiles import PROFILES
from game_lab import VanillaLane,write_json,sha
from customization_scenarios import run_customizations

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',choices=PROFILES,required=True);a=p.parse_args()
    lane=VanillaLane(a.version);result={'minecraft':a.version,'scope':'final factory-card return guard; canonical positives and customized-card preservation'}
    try:
        lane.download_server();lane.start();lane.start_player()
        result['datapack_sha256']={f.relative_to(lane.pack).as_posix():sha(f) for f in lane.pack.rglob('*') if f.is_file()}
        result['checks']=run_customizations(lane);result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines
        write_json(lane.pack.parents[2]/'evidence'/('returns-'+a.version+'.json'),result)
