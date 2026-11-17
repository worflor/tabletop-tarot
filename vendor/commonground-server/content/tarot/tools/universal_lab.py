"""Run the unchanged broad suite with the actual combined ZIP supplying every production function."""
import argparse,json,shutil,time,os
from game_lab import VanillaLane,ROOT,RUNTIME,write_json,sha,run_scenarios
from profiles import PROFILES
from universal import validate

class ZipLane(VanillaLane):
    def __init__(self,version,bundle=None):
        super().__init__(version)
        self.bundle=bundle or ROOT/'content/tarot/build/universal'
        self.archive=self.bundle/'Tabletop-Tarot-Universal.zip'
        self.archive_sha256=sha(self.archive)
        self.server_dir=RUNTIME/('universal-server-'+version)
        self.world_dir=self.server_dir/self.world_name
    def stage_pack(self,staged):
        # The loose pack contains ONLY observer fixtures. All production files come from the shipped ZIP.
        staged.mkdir();shutil.copyfile(self.pack/'pack.mcmeta',staged/'pack.mcmeta')
        shutil.copyfile(self.archive,staged.parent/'Tabletop-Tarot-Universal.zip')
        if sha(staged.parent/'Tabletop-Tarot-Universal.zip')!=self.archive_sha256:raise AssertionError('Production archive changed during staging')
    def check_fixtures(self):
        staged=self.world_dir/'datapacks/tarot'
        for path in staged.rglob('*'):
            if not path.is_file() or path.name=='pack.mcmeta':continue
            relative=path.relative_to(staged).as_posix()
            allowed=('/lab/','/physical_lab/','/native_lab/')
            if not any(piece in relative for piece in allowed):raise AssertionError('Observer fixture overrides production: '+relative)

def main(version):
    lane=ZipLane(version)
    verified={'passed':True,'zip_sha256':lane.archive_sha256,'scope':'Complete artifact validation performed once by the matrix controller; this lane independently pins and checks its staged ZIP'} if os.environ.get('TAROT_VALIDATED_ZIP_SHA256')==lane.archive_sha256 else validate(lane.bundle)
    result={'minecraft':version,'scope':'Unmodified vanilla engine and native protocol players; production loaded ONLY from the same combined ZIP; separate non-production observer fixtures','checks':[],'combined_zip_sha256':lane.archive_sha256,'artifact_validation':verified}
    try:
        lane.download_server();lane.start();lane.start_player()
        listing=lane.rcon('datapack list enabled')
        if 'Tabletop-Tarot-Universal.zip' not in listing:raise AssertionError('Combined archive not enabled: '+listing)
        result['datapack_list']=listing;result['reload']=lane.refresh_pack()
        result['checks']=run_scenarios(lane)
        from deck_scenarios import run_extra
        from hardening_scenarios import run_hardening
        from multiplayer_scenarios import run_multiplayer
        from customization_scenarios import run_customizations
        from physical_lab import run_physical
        result['checks']+=run_extra(lane)+run_hardening(lane)+run_multiplayer(lane)+run_customizations(lane)
        run_physical(lane,result['checks'])
        from shuffle_lab import run as focused_shuffle
        result['focused_shuffle']=focused_shuffle(lane,baseline=False)
        lane.check_fixtures();lane.check_log(__import__('pathlib').Path(lane.starts[-1]['log']).read_text(encoding='utf-8',errors='replace'))
        result['passed']=len(result['checks'])==50 and len(result['focused_shuffle'])==2 and all(c.get('passed') is not False for c in result['checks']+result['focused_shuffle'])
        if not result['passed']:raise AssertionError('Incomplete/failed combined archive suite')
    except Exception as error:result['passed']=False;result['error']=repr(error);raise
    finally:
        lane.stop();result['commands']=lane.commands;result['protocol_lines']=lane.client_lines;result['processes']=lane.starts
        write_json(ROOT/'content/tarot/evidence'/('universal-'+version+'.json'),result)
    print(json.dumps({'version':version,'passed':result['passed'],'checks':len(result['checks'])}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=PROFILES,required=True);main(parser.parse_args().version)
