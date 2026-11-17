#!/usr/bin/env python3
"""Run the pinned original engine labs against the final, unchanged release ZIP.

The imported labs remain read-only. Their catalogue and fixture metadata come from
the original build; production functions are loaded only from the frozen ZIP.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import zipfile

if not __debug__:
    raise SystemExit("Engine verification requires assertions; remove Python optimization.")

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "vendor/commonground-server/content/tarot"
for major in (21, 25):
    if os.environ.get(f"TAROT_JAVA{major}"):
        os.environ.setdefault(f"TAROT_JAVA_{major}", os.environ[f"TAROT_JAVA{major}"])
    candidates = sorted((Path.home()/".local/share/mise/installs/java").glob(f"temurin-{major}*/bin/java"))
    if candidates:
        os.environ.setdefault(f"TAROT_JAVA_{major}", str(candidates[-1]))
sys.path.insert(0, str(ORIGINAL / "tools"))
import game_lab
from profiles import PROFILES, profile
game_lab.PLAYER_CLIENT = (ROOT/'tests/protocol_compat.cjs').read_text()+'\n'+game_lab.PLAYER_CLIENT


class FinalZipLane(game_lab.VanillaLane):
    def __init__(self, version, archive, folder):
        super().__init__(version)
        # Upstream peer observers write their runner here without starting a second server.
        self.server_dir.mkdir(parents=True, exist_ok=True)
        self.archive = archive
        self.archive_sha256 = game_lab.sha(archive)
        self.server_dir = folder / "server"
        self.world_dir = self.server_dir / self.world_name
        self.server_heap = "1024M"
        self.pack = folder / "adapter/datapack"
        self.pack.mkdir(parents=True)
        original = ORIGINAL / "build" / ("java-" + version)
        shutil.copyfile(original / "datapack/pack.mcmeta", self.pack / "pack.mcmeta")
        shutil.copyfile(original / "catalogue.json", self.pack.parent / "catalogue.json")
        fmt = profile(version)["data"]
        major, minor = fmt if isinstance(fmt, list) else (fmt, 0)
        prefix = f"data_{major}_{minor}/"
        self.production = set()
        with zipfile.ZipFile(archive) as source:
            for name in source.namelist():
                if name.startswith(prefix + "data/") and not name.endswith("/"):
                    relative = name[len(prefix):]
                    self.production.add(relative)
                    output = self.pack / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(source.read(name))

    def stage_pack(self, staged):
        staged.mkdir()
        shutil.copyfile(self.pack / "pack.mcmeta", staged / "pack.mcmeta")
        target = staged.parent / "Tabletop-Tarot.zip"
        shutil.copyfile(self.archive, target)
        if game_lab.sha(target) != self.archive_sha256:
            raise AssertionError("Production archive changed during staging")

    def check_fixtures(self, pressure=False):
        if game_lab.sha(self.world_dir / "datapacks/Tabletop-Tarot.zip") != self.archive_sha256:
            raise AssertionError("Staged production ZIP changed")
        for path in (self.world_dir / "datapacks/tarot").rglob("*"):
            if not path.is_file() or path.name == "pack.mcmeta":
                continue
            relative = path.relative_to(self.world_dir / "datapacks/tarot").as_posix()
            if pressure and relative == "data/minecraft/tags/function/tick.json":
                if json.loads(path.read_text()) != {"replace": True, "values": ["tarot_lab:pulse", "tarot:tick", "tarot_lab:observe"]}:
                    raise AssertionError("Unexpected pressure instrumentation")
                continue
            if relative in self.production:
                raise AssertionError("Observer overrides a production file: " + relative)

    def download_server(self):
        cache = Path(os.environ.get("TAROT_MC_CACHE", str(Path.home()/".gradle/caches/fabric-loom")))
        cached = cache / self.version / "minecraft-server.jar"
        target = game_lab.RUNTIME / f"server-{self.version}.jar"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() and cached.is_file():
            shutil.copyfile(cached, target)
        super().download_server()


def run(version, suite, archive, folder, seed, steps):
    folder.mkdir(parents=True, exist_ok=True)
    lane = FinalZipLane(version, archive, folder)
    peer = None
    result = {"minecraft": version, "suite": suite, "archive_sha256": lane.archive_sha256,
              "scope": "Official vanilla server and real protocol players; production loaded only from the frozen final ZIP",
              "checks": [], "completed_phases": [], "passed": False}
    if version=='1.20.6':
        result['observer_adapter']='Correct the pinned recipe serializer registry against Mojang 1.20.6; all recipes and component payloads remain fully decoded'
    if suite == "pressure":
        if version != "1.21.11":
            raise ValueError("The pinned nine-player pressure fixture targets 1.21.11")
        return pressure(lane, folder)
    try:
        if suite == 'dimensions':
            lane.property_overrides = {'allow-nether':'true'}
        lane.download_server(); lane.start(); lane.start_player()
        if suite == "broad":
            from deck_scenarios import run_extra
            from hardening_scenarios import run_hardening
            from multiplayer_scenarios import run_multiplayer
            from customization_scenarios import run_customizations
            from physical_lab import run_physical
            from shuffle_lab import run as shuffle
            for name, action in [("base", game_lab.run_scenarios), ("decks", run_extra),
                                 ("hardening", run_hardening), ("multiplayer", run_multiplayer),
                                 ("customizations", run_customizations)]:
                result["checks"].extend(action(lane)); result["completed_phases"].append(name)
                print(version, name, "passed", flush=True)
            run_physical(lane, result["checks"])
            result["completed_phases"].append("physical")
            result["checks"].extend(shuffle(lane, baseline=False))
            if len(result["checks"]) != 52:
                raise AssertionError("Incomplete broad suite: " + str(len(result["checks"])))
        elif suite == "fuzz":
            from fuzz_lab import run as fuzz
            peer = game_lab.VanillaLane(version)
            peer.game_port, peer.rcon_port, peer.password = lane.game_port, lane.rcon_port, lane.password
            peer.start_player("TarotPeer")
            result.update(seed=seed, steps_requested=steps, trace=[], operations=collections.Counter(),
                          transitions=collections.Counter(), audits=0)
            fuzz(lane, peer, seed, steps, result)
        else:
            module = __import__({"quiet": "quiet_scenarios", "refinement": "refinement_lab", "payload": "payload_lab", "dimensions":"dimension_scenarios", "native":"native_validation", "optimization":"optimization_scenarios"}[suite])
            result["checks"].extend(module.run(lane))
            if suite == "payload":
                result.update(seed=seed, malformed_cases_requested=96)
                result["checks"].extend(module.fuzz(lane, seed, 96))
                # A rejected batch must leave the normal action path usable.
                lane.rcon('clear TarotLab')
                lane.rcon('scoreboard players set TarotLab tarot.cool 0')
                lane.rcon('execute as TarotLab run function tarot:give/numbers')
                lane.client_action('hold', slot=0)
                lane.client_action('chat', text='/trigger tarot.action set 1')
                state = lane.wait_state(lambda s: len(game_lab.card_items(s)) == 1 and
                    len(game_lab.card_keys(game_lab.deck_item(s, 'numbers'))) == 11, 'valid draw after malformed batch')
                if game_lab.card_items(state)[0][1]['key'] != 'numbers/number-1':
                    raise AssertionError('Recovery draw changed the top card')
                result['checks'].append({'name':'valid_draw_after_malformed_batch', 'passed':True})
        lane.check_fixtures()
        log = Path(lane.starts[-1]["log"]).read_text(errors="replace")
        if suite == 'payload':
            from codec_diagnostics import split_payload_diagnostics
            log, result['expected_codec_rejections'] = split_payload_diagnostics(log, lane.world_name, seed, 96)
        lane.check_log(log)
        nonpassing = [c for c in result["checks"] if c.get("passed") is not True]
        if nonpassing:
            raise AssertionError("Unproven checks: " + json.dumps(nonpassing))
        result["passed"] = True
    except Exception as error:
        result["error"] = repr(error)
        result["traceback"] = traceback.format_exc()
        print(version, suite, "FAIL", repr(error), flush=True)
    finally:
        if peer:
            peer.stop()
        lane.stop()
        result["commands"] = lane.commands + (peer.commands if peer else [])
        result["protocol_lines"] = lane.client_lines + (peer.client_lines if peer else [])
        result["processes"] = lane.starts
        game_lab.write_json(folder / "result.json", result)
    print(version, suite, "PASS" if result["passed"] else "FAIL", len(result["checks"]), "checks", flush=True)
    return result["passed"]


def pressure(lane, folder):
    import supplemental_lab
    captured = []
    original_rcon = lane.rcon
    original_stage = lane.stage_pack

    def stage(staged):
        original_stage(staged)
        (staged/"data/minecraft/tags/function").mkdir(parents=True)

    def rcon(command):
        if command == "reload":
            tick = lane.world_dir/"datapacks/tarot/data/minecraft/tags/function/tick.json"
            if tick.exists():
                tag = json.loads(tick.read_text())
                if tag.get("values") != ["tarot_lab:pulse", "tarot:tick", "tarot_lab:observe"]:
                    raise AssertionError("Unknown pressure tick controller")
                # A separate observer pack brackets the unchanged production tick.
                # Replace the merged global tag so its existing entry cannot move
                # ahead of the input pulse or execute twice.
                tag["replace"] = True
                tick.write_text(json.dumps(tag))
        return original_rcon(command)

    def receipt(_path, result):
        result.update(archive_sha256=lane.archive_sha256,
                      scope="Nine real protocol players; final ZIP production functions unchanged; observer tick tag brackets tarot:tick for per-tick budget measurements")
        try:
            lane.check_fixtures(pressure=True)
        except Exception as error:
            result.update(passed=False, fixture_error=repr(error))
        game_lab.write_json(folder/"result.json", result)
        captured.append(result)

    lane.rcon = rcon
    lane.stage_pack = stage
    supplemental_lab.supplemental_lane = lambda _version: lane
    supplemental_lab.write_json = receipt
    try:
        supplemental_lab.crowd(pressure=True)
    except Exception:
        traceback.print_exc()
        return False
    return bool(captured and captured[0].get("passed"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=ROOT/"dist/Tabletop-Tarot-1.1.0.zip")
    parser.add_argument("--versions", nargs="+", choices=[v for v in PROFILES if v != "26.3"], required=True)
    parser.add_argument("--suite", choices=["broad", "quiet", "refinement", "payload", "fuzz", "pressure", "dimensions", "native", "optimization"], default="broad")
    parser.add_argument("--prepare", action="store_true", help="Install/check the pinned protocol observer without running a suite")
    parser.add_argument("--seed", type=int, default=671083)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT/"tests/artifacts/final-global/engine")
    args = parser.parse_args()
    if args.prepare:
        from bootstrap_lab import main as prepare
        prepare(args.versions)
        return 0
    output = args.artifacts_dir.resolve()/str(time.time_ns()); output.mkdir(parents=True)
    frozen = output/"Tabletop-Tarot.zip"; shutil.copyfile(args.zip, frozen)
    game_lab.RUNTIME = output
    results = [run(v, args.suite, frozen, output/v, args.seed, args.steps) for v in args.versions]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
