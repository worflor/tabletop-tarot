"""Adversarial CLI checks, including optimized Python and last-good-build safety."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest,zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
RUNTIME=ROOT.parents[2]/'commonground-microvoxels-runtime/tarot/integrity-tests'

class BuildIntegrity(unittest.TestCase):
    def setUp(self):
        RUNTIME.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='owned-',dir=RUNTIME)
        self.base=Path(self.temp.name).resolve()
        if not self.base.is_relative_to(RUNTIME.resolve()):raise ValueError('Unsafe temporary root')
        self.output=self.base/'build';shutil.copytree(ROOT/'build/java-1.21.11',self.output)
    def tearDown(self):self.temp.cleanup()
    def cli(self,optimized=True):
        args=[sys.executable,'-B']+(['-O'] if optimized else [])+[str(HERE/'check.py'),str(self.output)]
        return subprocess.run(args,text=True,capture_output=True)
    def test_valid_output_with_optimization(self):
        result=self.cli();self.assertEqual(result.returncode,0,result.stderr)
    def test_duplicate_identity_rejected_optimized(self):
        p=self.output/'catalogue.json';d=json.loads(p.read_text());d['cards'][1]['key']=d['cards'][0]['key'];p.write_text(json.dumps(d))
        result=self.cli();self.assertNotEqual(result.returncode,0);self.assertIn('Duplicate card identity',result.stderr)
    def test_crc_valid_but_missing_zip_members_rejected(self):
        p=self.output/'Tabletop-Tarot-1.21.11-datapack.zip'
        with zipfile.ZipFile(p,'w') as z:z.write(self.output/'datapack/pack.mcmeta','pack.mcmeta')
        result=self.cli();self.assertNotEqual(result.returncode,0);self.assertIn('ZIP/expanded file set differs',result.stderr)
    def test_expanded_bytes_cannot_disagree_with_installable_zip(self):
        p=self.output/'datapack/data/tarot/function/load.mcfunction';p.write_text(p.read_text()+'# corruption fixture\n')
        result=self.cli();self.assertNotEqual(result.returncode,0);self.assertIn('ZIP/expanded bytes differ',result.stderr)
    def test_build_manifest_corruption_rejected(self):
        p=self.output/'build.json';d=json.loads(p.read_text());d['files'][0]['sha256']='0'*64;p.write_text(json.dumps(d))
        result=self.cli();self.assertNotEqual(result.returncode,0);self.assertIn('Build hash differs',result.stderr)
    def test_failed_source_preflight_keeps_previous_output(self):
        source=self.base/'source';source.mkdir()
        for part in ['core','modules']:shutil.copytree(ROOT/part,source/part)
        shutil.copyfile(ROOT/'source-lock.json',source/'source-lock.json')
        old=source/'build/java-1.21.11';old.mkdir(parents=True);marker=old/'last-good';marker.write_text('keep')
        p=source/'modules/rider/major-0.png';p.write_bytes(p.read_bytes()+b'changed')
        code='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import build;build.ROOT=Path(sys.argv[2]);build.build("1.21.11")'
        r=subprocess.run([sys.executable,'-O','-B','-c',code,str(HERE),str(source)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('Imported source changed',r.stderr);self.assertEqual(marker.read_text(),'keep')

if __name__=='__main__':unittest.main()
