"""Freeze observers, then test the SAME combined ZIP on exact official vanilla releases."""
import argparse,concurrent.futures,hashlib,json,os,pathlib,subprocess,sys,time
from game_lab import ROOT,RUNTIME,sha
from matrix import freeze_observer
from profiles import PROFILES
from universal import validate

def main(versions,workers):
    validation=validate(ROOT/'content/tarot/build/universal')
    here=pathlib.Path(__file__).resolve().parent
    sources={p.name:p.read_bytes() for p in here.glob('*.py')};sources['profiles.json']=(here.parent/'profiles.json').read_bytes()
    digest=hashlib.sha256(b''.join(n.encode()+b'\0'+d for n,d in sorted(sources.items()))).hexdigest()
    frozen=RUNTIME/'matrix/harness'/digest;freeze_observer(frozen,sources)
    env=os.environ.copy();env['TAROT_PROJECT_ROOT']=str(ROOT);env['TAROT_HARNESS_SHA256']=digest
    archive=ROOT/'content/tarot/build/universal/Tabletop-Tarot-Universal.zip';before=sha(archive)
    env['TAROT_VALIDATED_ZIP_SHA256']=before
    def run(version):
        if (RUNTIME/'matrix/STOP-UNIVERSAL').exists():return {'minecraft':version,'passed':False,'status':'cancelled_for_observer_update'}
        log=RUNTIME/f'matrix/universal-{version}-{time.time_ns()}.log'
        with log.open('wb') as output:
            process=subprocess.run([sys.executable,'-u','-B',str(frozen/'tools/universal_lab.py'),'--version',version],env=env,stdout=output,stderr=subprocess.STDOUT)
        receipt=ROOT/f'content/tarot/evidence/universal-{version}.json';result=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {}
        row={'minecraft':version,'passed':process.returncode==0 and result.get('passed') is True,'checks':len(result.get('checks',[])),'log':str(log),'error':result.get('error'),'receipt':receipt.name,'receipt_sha256':sha(receipt) if receipt.exists() else None}
        print(json.dumps(row),flush=True);return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:results=list(pool.map(run,versions))
    if sha(archive)!=before:raise AssertionError('Combined ZIP changed during matrix')
    report={'scope':'This invocation; exact listed vanilla Java releases, same combined production ZIP','artifact_validation':validation,'combined_zip_sha256':before,'harness_sha256':digest,'results':results}
    (ROOT/f'content/tarot/evidence/universal-matrix-{time.time_ns()}.json').write_text(json.dumps(report,indent=2)+'\n')
    if not all(r['passed'] for r in results):sys.exit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--versions',nargs='+',choices=[v for v in PROFILES if v!='26.3'],default=[v for v in PROFILES if v!='26.3']);p.add_argument('--workers',type=int,choices=[1,2],default=1);a=p.parse_args();main(a.versions,a.workers)
