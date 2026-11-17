"""Connect the original 26.3 backend checks to the owned stock-client session."""
from test_engine import FinalZipLane
import native_backend_lab
import time
from test_engine import game_lab


def run_backend(version, rcon, work):
    lane = FinalZipLane(version, work/'server/world/datapacks/Tabletop-Tarot.zip', work/'backend')
    lane.server_dir = work/'server'
    lane.world_dir = lane.server_dir/'world'
    fixture = lane.world_dir/'datapacks/tarot'
    fixture.mkdir()
    (fixture/'pack.mcmeta').write_bytes((lane.pack/'pack.mcmeta').read_bytes())
    captured = []
    writer = native_backend_lab.write_json

    def command(text):
        reply = rcon.cmd(text)
        lane.commands.append({'via':'rcon','command':text,'response':reply})
        return reply

    def receipt(path, result):
        writer(path, result)
        captured.append(result)

    lane.rcon = command
    native_backend_lab.write_json = receipt
    command('tp Bob 10.5 -60 -8.5')
    native_backend_lab.main(version, universal_lane=lane)
    assert captured and captured[0]['passed'] and len(captured[0]['checks'])==15
    from native_validation import run as native_cases
    def action(number):
        command(f'scoreboard players set TarotVisual tarot.action {number}')
        deadline = time.monotonic()+8
        while 'has 0 ' not in command('scoreboard players get TarotVisual tarot.action'):
            if time.monotonic() >= deadline:
                raise AssertionError('Native backend action did not drain')
            time.sleep(.025)
    start = len(lane.commands)
    checks = native_cases(lane, player='TarotVisual', action=action)
    assert len(checks) == 8 and all(c['passed'] for c in checks)
    lane.check_fixtures()
    game_lab.write_json(work/'evidence/native-validation-26.3.json',
        {'minecraft':version,'archive_sha256':lane.archive_sha256,'passed':True,'checks':checks,
         'commands':lane.commands[start:],'scope':'Stock client context with RCON-driven queued actions and exact live ItemStack preservation controls'})
    from optimization_scenarios import run as optimization_cases
    start=len(lane.commands)
    checks=optimization_cases(lane,player='TarotVisual',action=action)
    assert len(checks)==4 and all(c['passed'] for c in checks)
    lane.check_fixtures()
    game_lab.write_json(work/'evidence/optimization-controls-26.3.json',
        {'minecraft':version,'archive_sha256':lane.archive_sha256,'passed':True,'checks':checks,
         'commands':lane.commands[start:],'scope':'Stock client context; scratch-fault controls and queued boundary shuffles through unchanged production functions'})
