"""Check lab dependencies; optionally install the locked observer and official clients."""
import argparse,json,os,pathlib,shutil,subprocess
from lab_environment import java_runtime
from profiles import PROFILES,profile

def main(versions,check=False,clients=False):
    from game_lab import NODE_CLIENTS
    for major in sorted({profile(v)['java'] for v in versions}):print('Java',major,java_runtime(major),flush=True)
    if not shutil.which('node'):raise RuntimeError('Install Node.js (with npm) and put it on PATH.')
    pins=pathlib.Path(__file__).with_name('protocol-observer')
    if not check:
        NODE_CLIENTS.mkdir(parents=True,exist_ok=True)
        for name in ['package.json','package-lock.json']:shutil.copyfile(pins/name,NODE_CLIENTS/name)
        npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
        if not npm:raise RuntimeError('npm is required to install the locked protocol observer.')
        subprocess.run([npm,'ci','--ignore-scripts','--no-audit','--no-fund'],cwd=NODE_CLIENTS,check=True)
    if not (NODE_CLIENTS/'package-lock.json').is_file() or (NODE_CLIENTS/'package-lock.json').read_bytes()!=(pins/'package-lock.json').read_bytes():raise RuntimeError('Observer lock is missing or differs. Run bootstrap_lab.py without --check.')
    subprocess.run([shutil.which('node'),'-e',"require('mineflayer');require('minecraft-protocol');console.log('Locked protocol observer ready')"],cwd=NODE_CLIENTS,check=True)
    if clients:
        if check:raise ValueError('--clients prepares downloads; omit --check.')
        from visual_client import prepare
        for version in versions:prepare(version)
    print(json.dumps({'passed':True,'versions':versions,'clients_prepared':clients}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--versions',nargs='+',choices=PROFILES,default=['1.20.6','1.21.11','26.1.2','26.3']);p.add_argument('--check',action='store_true');p.add_argument('--clients',action='store_true');a=p.parse_args();main(a.versions,a.check,a.clients)
