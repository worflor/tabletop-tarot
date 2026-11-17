"""Focused integration tests against the installed combined release ZIP."""
import argparse
from game_lab import ROOT,RUNTIME,write_json,VanillaLane,sha
from universal_lab import ZipLane
from quiet_scenarios import run,run_repair

def main(version,adapter=False,repair_only=False):
    lane=VanillaLane(version) if adapter else ZipLane(version)
    lane.server_dir=RUNTIME/('quiet-server-'+version);lane.world_dir=lane.server_dir/lane.world_name
    result={'minecraft':version,'scope':'Official vanilla engine and a non-operator Survival protocol player; real recipe discovery, crafting grid and use packets','checks':[]}
    if not adapter:result['combined_zip_sha256']=sha(lane.archive)
    try:
        lane.download_server();lane.start();lane.start_player()
        result['checks']=(run_repair if repair_only else run)(lane)
        if not adapter:lane.check_fixtures()
        result['passed']=all(c['passed'] for c in result['checks'])
        if not result['passed']:raise AssertionError('An integration check failed')
    except Exception as error:result['passed']=False;result['error']=repr(error);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines
        write_json(ROOT/f'content/tarot/evidence/quiet-{version}.json',result)
    print({'passed':result['passed'],'checks':len(result['checks'])})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='1.20.6');p.add_argument('--adapter',action='store_true');p.add_argument('--repair-only',action='store_true');a=p.parse_args();main(a.version,a.adapter,a.repair_only)
