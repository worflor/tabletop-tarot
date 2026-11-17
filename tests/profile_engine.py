"""Warm and profile the unchanged nine-player pressure workload on an owned server."""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from test_engine import ROOT, FinalZipLane, game_lab, pressure


def run(archive, folder, mode, warmups):
    folder.mkdir(parents=True)
    frozen = folder/'Tabletop-Tarot.zip'
    shutil.copyfile(archive, frozen)
    game_lab.RUNTIME = folder
    lane = FinalZipLane('1.21.11', frozen, folder/'lane')
    original_rcon = lane.rcon
    started = False
    recording = False
    measured_at = None
    metadata = {'archive_sha256': lane.archive_sha256, 'mode': mode, 'warmup_cycles': warmups,
                'scope':'Nine actual protocol players, unchanged final ZIP; warm cycles skip support removal, measured cycle includes the original 144-card support loss',
                'raw_fixture_elapsed_includes_warmups': True,
                'controller_poll_interval_seconds': .05,
                'timing_scope':'Minecraft rolling 100-tick mean queried promptly after the measured cycle; measured_cycle_elapsed_seconds excludes warmups and includes 50ms polling plus RCON round-trip delay'}

    def jcmd(*args):
        result = subprocess.run([str(lane.java.with_name('jcmd')), str(lane.process.pid), *args],
                                capture_output=True, text=True, check=True)
        metadata.setdefault('profiler_commands', []).append({'args':args, 'output':result.stdout})
        return result.stdout

    def finish():
        nonlocal recording
        if recording:
            if mode == 'jfr':
                jcmd('JFR.stop', 'name=tarot', 'filename='+str(folder/'profile.jfr'))
            elif mode == 'debug':
                metadata['debug_stop'] = original_rcon('debug stop')
            recording = False

    def rcon(command):
        nonlocal started, recording, measured_at
        measure_now=False
        if command == 'scoreboard players set #run tarot_lab 1' and not started:
            started = True
            for cycle in range(warmups):
                original_rcon('scoreboard players set #ticks tarot_lab 1')
                original_rcon(command)
                deadline = time.monotonic()+120
                while 'has 0 ' not in original_rcon('scoreboard players get #run tarot_lab'):
                    if time.monotonic() > deadline:
                        raise TimeoutError('Warmup did not complete')
                    time.sleep(.2)
                print('Warm cycle complete', cycle+1, flush=True)
            original_rcon('scoreboard players set #ticks tarot_lab 0')
            original_rcon('scoreboard players set #max tarot_lab 0')
            original_rcon('scoreboard players set #max_fall tarot_lab 0')
            original_rcon('scoreboard players set #previous_roots tarot_lab 144')
            for i in range(9):
                original_rcon(f'scoreboard players set TarotCrowd{i} tarot_lab 0')
            if mode == 'jfr':
                jcmd('JFR.start', 'name=tarot', 'settings=profile', 'filename='+str(folder/'profile.jfr'))
                recording = True
            elif mode == 'debug':
                metadata['debug_start'] = original_rcon('debug start')
                recording = True
            measured_at = time.monotonic()
            measure_now=True
        result = original_rcon(command)
        if measure_now:
            # Keep the original fixture and its 80-tick observer unchanged, but
            # observe completion here instead of its coarse 0.5-second loop.
            # This also keeps a random idle tail out of the rolling tick query.
            polls=0;deadline=time.monotonic()+120
            while True:
                polls+=1
                if 'has 0 ' in original_rcon('scoreboard players get #run tarot_lab'):
                    break
                if time.monotonic()>deadline:raise TimeoutError('Measured pressure cycle did not finish')
                time.sleep(.05)
            metadata['measured_cycle_elapsed_seconds']=round(time.monotonic()-measured_at,3)
            metadata['measured_observer_polls']=polls
        if command == 'scoreboard players get #run tarot_lab' and 'has 0 ' in result and measured_at is not None:
            metadata.setdefault('measured_cycle_elapsed_seconds', round(time.monotonic()-measured_at, 3))
        if command == 'tick query':
            metadata['tick_query'] = result
            finish()
        return result

    lane.rcon = rcon
    try:
        metadata['passed'] = pressure(lane, folder/'lane')
    finally:
        if recording and lane.process and lane.process.poll() is None:
            finish()
        (folder/'benchmark.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata['passed']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', type=Path, default=ROOT/'dist/Tabletop-Tarot-1.1.0.zip')
    parser.add_argument('--artifacts-dir', type=Path, default=ROOT/'tests/artifacts/performance')
    parser.add_argument('--label', required=True)
    parser.add_argument('--mode', choices=['jfr','debug','timing'], default='jfr')
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--repeats', type=int, default=1)
    args = parser.parse_args()
    for index in range(args.repeats):
        folder = args.artifacts_dir.resolve()/args.label/(str(time.time_ns())+'-'+str(index))
        if not run(args.zip, folder, args.mode, args.warmups):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
