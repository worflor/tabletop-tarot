"""Reject installable archives whose overlays select missing/wrong content, even under python -O."""
import hashlib,json,pathlib,shutil,subprocess,sys,tempfile,unittest,zipfile
from universal import ROOT,files,hashes

RUNTIME=ROOT.parents[2]/'commonground-microvoxels-runtime/tarot/universal-integrity'
class UniversalIntegrity(unittest.TestCase):
    def setUp(self):
        RUNTIME.mkdir(parents=True,exist_ok=True);self.temporary=tempfile.TemporaryDirectory(dir=RUNTIME,prefix='owned-')
        self.base=pathlib.Path(self.temporary.name).resolve()
        if not self.base.is_relative_to(RUNTIME.resolve()):raise ValueError('Unexpected owned test root')
        self.output=self.base/'bundle';self.output.mkdir()
        plan=json.loads((ROOT/'build/universal/overlay-plan.json').read_text(encoding='utf-8'))
        values={'pack.mcmeta':json.dumps(plan['pack_mcmeta']).encode(),'assets/probe/models/item/card.json':b'{"parent":"minecraft:item/generated"}'}
        effective={row['minecraft']:{'data':{},'resource':hashes({'assets/probe/models/item/card.json':values['assets/probe/models/item/card.json']})} for row in plan['targets']}
        for group in plan['overlays']:
            if group['kind']!='data':continue
            name='data/probe/function/ping.mcfunction';data=('# '+group['directory']+'\n').encode()
            values[group['directory']+'/'+name]=data
            for version in group['targets']:effective[version]['data']=hashes({name:data})
        for name,data in values.items():
            target=self.output/'pack'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        (self.output/'overlay-plan.json').write_text(json.dumps(plan),encoding='utf-8')
        (self.output/'build.json').write_text(json.dumps({'cards':90,'effective_sha256':effective}),encoding='utf-8');self.rewrite()
    def tearDown(self):self.temporary.cleanup()
    def check(self,output=None):
        return subprocess.run([sys.executable,'-B','-O',str(ROOT/'tools/universal.py'),'--check',str(output or self.output)],capture_output=True,text=True)
    def rewrite(self):
        with zipfile.ZipFile(self.output/'Tabletop-Tarot-Universal.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for name,data in files(self.output/'pack').items():archive.writestr(name,data)
        manifest=json.loads((self.output/'build.json').read_text(encoding='utf-8'));manifest['pack_sha256']=hashes(files(self.output/'pack'))
        raw=(self.output/'Tabletop-Tarot-Universal.zip').read_bytes();manifest['zip_sha256']=hashlib.sha256(raw).hexdigest();manifest['zip_sha1']=hashlib.sha1(raw).hexdigest()
        (self.output/'build.json').write_text(json.dumps(manifest),encoding='utf-8')
    def test_valid_combined_archive_optimized(self):
        result=self.check();self.assertEqual(result.returncode,0,result.stderr)
    def test_actual_checked_release_archive(self):
        result=self.check(ROOT/'build/universal');self.assertEqual(result.returncode,0,result.stderr)
    def test_import_marker_cannot_hide_root_runtime(self):
        path=self.output/'pack/data/probe/function/leak.mcfunction';path.parent.mkdir(parents=True);path.write_bytes(b'say leaked')
        self.rewrite();result=self.check();self.assertNotEqual(result.returncode,0);self.assertIn('Unselected runtime leaked',result.stderr)
    def test_import_marker_must_be_inert(self):
        from universal import IMPORT_MARKER
        path=self.output/'pack'/IMPORT_MARKER;path.parent.mkdir(parents=True);path.write_bytes(b'changed')
        self.rewrite();result=self.check();self.assertNotEqual(result.returncode,0);self.assertIn('Changed importer marker',result.stderr)
    def test_crc_valid_truncated_archive(self):
        with zipfile.ZipFile(self.output/'Tabletop-Tarot-Universal.zip','w') as archive:archive.write(self.output/'pack/pack.mcmeta','pack.mcmeta')
        result=self.check();self.assertNotEqual(result.returncode,0);self.assertIn('Combined ZIP differs',result.stderr)
    def test_duplicate_zip_member(self):
        with zipfile.ZipFile(self.output/'Tabletop-Tarot-Universal.zip','a') as archive:archive.writestr('pack.mcmeta',b'{}')
        result=self.check();self.assertNotEqual(result.returncode,0);self.assertIn('Duplicate ZIP member',result.stderr)
    def corrupt_range(self,legacy_only=False):
        path=self.output/'overlay-plan.json';plan=json.loads(path.read_text(encoding='utf-8'))
        entry=next(e for e in plan['pack_mcmeta']['overlays']['entries'] if e['directory']=='data_41_0')
        entry['formats']=42
        if not legacy_only:entry['min_format']=[42,0];entry['max_format']=[42,0]
        path.write_text(json.dumps(plan),encoding='utf-8');(self.output/'pack/pack.mcmeta').write_text(json.dumps(plan['pack_mcmeta']),encoding='utf-8');self.rewrite()
    def test_wrong_overlay_range_despite_consistent_hashes(self):
        self.corrupt_range();result=self.check();self.assertNotEqual(result.returncode,0);self.assertIn('Effective combined content mismatch',result.stderr)
    def test_old_and_new_range_schemas_must_agree(self):
        self.corrupt_range(True);result=self.check();self.assertNotEqual(result.returncode,0);self.assertIn('Legacy selection mismatch',result.stderr)
    def test_changed_compiler_pin_preserves_last_good(self):
        source=self.base/'source';old=source/'build/universal';old.mkdir(parents=True);(old/'last-good').write_text('keep')
        compiler=source/'compiler';shutil.copytree(ROOT/'tools/mycelium-overlays',compiler);(compiler/'planner.jar').write_bytes(b'changed')
        code='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import universal;universal.ROOT=Path(sys.argv[2]);universal.PLANNER=Path(sys.argv[3]);universal.compile_pack(rebuild=False)'
        result=subprocess.run([sys.executable,'-B','-O','-c',code,str(ROOT/'tools'),str(source),str(compiler)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Pinned Mycelium compiler changed',result.stderr);self.assertEqual((old/'last-good').read_text(),'keep')
if __name__=='__main__':unittest.main()
