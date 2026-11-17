"""Build and exercise explicit versions, with bounded owned server concurrency."""
from pathlib import Path
import argparse,concurrent.futures,json,subprocess,sys,time,os,hashlib,uuid,threading,traceback
from profiles import PROFILES
from build import build

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CACHE=ROOT.parents[2]/'commonground-microvoxels-runtime/tarot/matrix'
HARNESS_LOCK=threading.Lock()

def freeze_observer(frozen,sources):
    # Windows cannot replace a file while another lane is importing/reading it.
    # Publish once, under the controller lock, and never rewrite identical files.
    with HARNESS_LOCK:
        (frozen/'tools').mkdir(parents=True,exist_ok=True)
        for name,data in sources.items():
            target=frozen/name if name=='profiles.json' else frozen/'tools'/name
            if target.exists():
                if target.read_bytes()!=data:raise ValueError('Observer snapshot collision')
                continue
            temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
            temporary.write_bytes(data);temporary.replace(target)

def run(version,suite="full"):
    CACHE.mkdir(parents=True,exist_ok=True)
    if (CACHE/'STOP').exists():return {'version':version,'status':'cancelled_for_harness_update'}
    build(version)
    if version=='26.3':
        return {'version':version,'status':'requires_native_client','reason':'Pinned protocol client does not implement protocol 777; never substitute an older protocol'}
    # Execute an immutable observer snapshot; source edits cannot change late imports.
    sources={p.name:p.read_bytes() for p in HERE.glob('*.py')}
    sources['profiles.json']=(ROOT/'profiles.json').read_bytes()
    digest=hashlib.sha256(b''.join(name.encode()+b'\0'+data for name,data in sorted(sources.items()))).hexdigest()
    frozen=CACHE/'harness'/digest
    freeze_observer(frozen,sources)
    env=os.environ.copy();env['TAROT_PROJECT_ROOT']=str(ROOT.parents[1]);env['TAROT_HARNESS_SHA256']=digest
    log=CACHE/(version+'-'+str(time.time_ns())+'.log')
    with log.open('wb') as out:
        result=subprocess.run([sys.executable,'-u','-B',str(frozen/'tools'/{'returns':'return_lab.py','full':'game_lab.py','shuffle':'shuffle_lab.py'}[suite]),'--version',version],stdout=out,stderr=subprocess.STDOUT,env=env)
    receipt=ROOT/'evidence'/({'returns':'returns-','full':'game-','shuffle':'shuffle-'}[suite]+version+'.json')
    data=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {}
    return {'version':version,'status':'passed' if result.returncode==0 and data.get('passed') else 'failed','checks':len(data.get('checks',[])),'error':data.get('error'),'log':str(log),'receipt':receipt.name,'receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest() if receipt.exists() else None,'full_receipt':data.get('full_receipt')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--versions',nargs='+',choices=PROFILES,default=list(PROFILES));p.add_argument('--suite',choices=['full','returns','shuffle'],default='full');p.add_argument('--workers',type=int,choices=[1,2],default=1);a=p.parse_args()
    results=[];run_id=str(time.time_ns())
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(run,v,a.suite):v for v in a.versions}
        for f in concurrent.futures.as_completed(futures):
            try:r=f.result()
            except Exception as e:r={'version':futures[f],'status':'failed','error':repr(e),'traceback':traceback.format_exc()}
            results.append(r);print(json.dumps(r),flush=True)
    report=json.dumps({'scope':'one invocation; use compatibility.json for accepted current deliverables','suite':a.suite,'requested_versions':a.versions,'results':results},indent=2)+'\n'
    (ROOT/'evidence'/('matrix-'+a.suite+'-'+run_id+'.json')).write_text(report,encoding='utf-8')
    (ROOT/'evidence'/('matrix-'+a.suite+'-run.json')).write_text(report,encoding='utf-8')
    if any(r['status']!='passed' for r in results):sys.exit(1)
