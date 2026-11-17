"""Parallel test controllers must not claim the same not-yet-listening port."""
import json,pathlib,subprocess,sys,tempfile,unittest
from game_lab import RUNTIME

class LabEnvironment(unittest.TestCase):
    def test_parallel_port_leases_are_distinct_and_release_at_exit(self):
        root=RUNTIME/'environment-tests';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix='owned-') as temporary:
            folder=pathlib.Path(temporary).resolve()
            if not folder.is_relative_to(root.resolve()):raise ValueError('Unexpected test root')
            code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from lab_environment import reserve_port;print(json.dumps([reserve_port(Path(sys.argv[2])) for _ in range(300)]),flush=True);input()'
            processes=[]
            try:
                for _ in range(2):processes.append(subprocess.Popen([sys.executable,'-B','-c',code,str(pathlib.Path(__file__).resolve().parent),str(folder)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
                groups=[json.loads(p.stdout.readline()) for p in processes]
                ports=[p for group in groups for p in group]
                self.assertEqual(len(set(ports)),600)
                self.assertTrue(all(20000<=p<30000 for p in ports))
                self.assertEqual(len(list((folder/'port-leases').glob('*.lease'))),600)
                for process in processes:
                    _,errors=process.communicate('\n',timeout=15)
                    self.assertEqual(process.returncode,0,errors)
                self.assertEqual(list((folder/'port-leases').glob('*.lease')),[])
            finally:
                for process in processes:
                    if process.poll() is None:process.kill();process.wait(timeout=10)

if __name__=='__main__':unittest.main()
