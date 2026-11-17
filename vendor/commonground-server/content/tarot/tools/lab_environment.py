"""Resolve explicit test prerequisites without relying on one developer's paths."""
import atexit,functools,os,pathlib,re,secrets,shutil,socket,subprocess,time

_leases={}

def _release_ports():
    for path,token in _leases.items():
        try:
            if path.read_text(encoding='ascii')==token:path.unlink()
        except FileNotFoundError:pass

atexit.register(_release_ports)

def reserve_port(runtime):
    """Coordinate parallel labs outside the usual TCP client ephemeral range."""
    folder=(runtime/'port-leases').resolve();folder.mkdir(parents=True,exist_ok=True)
    for _ in range(2000):
        number=20000+secrets.randbelow(10000);path=folder/(str(number)+'.lease')
        with socket.socket() as probe:
            try:probe.bind(('127.0.0.1',number))
            except OSError:continue
            # An abandoned lease never deletes another process's live bytes at
            # exit: cleanup also requires our exact random ownership token.
            if path.exists() and time.time()-path.stat().st_mtime>86400:path.unlink()
            token=str(os.getpid())+':'+secrets.token_hex(16)
            try:
                with path.open('x',encoding='ascii') as stream:stream.write(token)
            except FileExistsError:continue
            _leases[path]=token;return number
    raise RuntimeError('No free coordinated Minecraft lab port in 20000–29999')

@functools.lru_cache(maxsize=None)
def java_runtime(major):
    override=os.environ.get('TAROT_JAVA_'+str(major))
    candidates=[override] if override else [shutil.which('java')]
    if not override:
        if os.environ.get('JAVA_HOME'):candidates.append(str(pathlib.Path(os.environ['JAVA_HOME'])/'bin/java'))
        project=pathlib.Path(os.environ.get('TAROT_PROJECT_ROOT',str(pathlib.Path(__file__).resolve().parents[3])))
        roots=[(pathlib.Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Eclipse Adoptium','*/bin/java.exe'),(project.parent/'commonground-microvoxels-runtime','java*/**/bin/java.exe')]
        for root,pattern in roots:
            if root.exists():candidates.extend(str(p) for p in sorted(root.glob(pattern)))
    for candidate in dict.fromkeys(candidates):
        if not candidate:continue
        try:
            run=subprocess.run([candidate,'-version'],capture_output=True,text=True,timeout=15)
            match=re.search(r'version "(?:1\.)?(\d+)',run.stderr+run.stdout)
            if run.returncode==0 and match and int(match[1])==major:return pathlib.Path(candidate).resolve()
        except (OSError,subprocess.TimeoutExpired):pass
    raise RuntimeError(f'Java {major} is required for this lab. Set TAROT_JAVA_{major} to its java executable, then run bootstrap_lab.py --check.')
