#!/usr/bin/env python3
"""Static and multi-version headless dedicated-server verifier for Tabletop Tarot."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CACHE_ROOT = Path(os.environ.get("TAROT_MC_CACHE", str(Path.home() / ".gradle/caches/fabric-loom")))
FLAT_WORLD_SETTINGS = json.dumps({
    "layers": [
        {"block": "minecraft:bedrock", "height": 1},
        {"block": "minecraft:dirt", "height": 2},
        {"block": "minecraft:grass_block", "height": 1},
    ],
    "biome": "minecraft:plains", "structure_overrides": [], "lakes": False, "features": False,
}, separators=(",", ":"))


def java_for(major: int) -> str:
    override = os.environ.get(f"TAROT_JAVA{major}")
    if override:
        return override
    installed = sorted((Path.home() / ".local/share/mise/installs/java").glob(f"temurin-{major}*/bin/java"))
    return str(installed[-1]) if installed else "java"


JDK21, JDK25 = java_for(21), java_for(25)

# Map MC version -> expected data overlay dir and resource overlay dir
VERSION_MAP = {
    "1.20.6": ("data_41_0", "resource_32_0", True),
    "1.21.1": ("data_48_0", "resource_34_0", False),
    "1.21.3": ("data_57_0", "resource_42_0", False),
    "1.21.4": ("data_61_0", "resource_46_0", False),
    "1.21.5": ("data_71_0", "resource_55_0", False),
    "1.21.6": ("data_80_0", "resource_63_0", False),
    "1.21.8": ("data_81_0", "resource_64_0", False),
    "1.21.10": ("data_88_0", "resource_69_0", False),
    "1.21.11": ("data_94_1", "resource_75_0", False),
    "26.1.2": ("data_101_1", "resource_84_0", False),
    "26.3": ("data_121_0", "resource_97_1", False),
}

FN_RE = re.compile(r"\bfunction tarot:([a-z0-9_./-]+)")
PRED_RE = re.compile(r"\bpredicate tarot:([a-z0-9_./-]+)")
MOD_RE = re.compile(r"\btarot:([a-z0-9_./-]+)")
LOOT_RE = re.compile(r"\bloot tarot:([a-z0-9_./-]+)")
TAG_BLK_RE = re.compile(r"#tarot:([a-z0-9_./-]+)")


class RconClient:
    def __init__(self, host: str, port: int, password: str) -> None:
        self.sock = socket.create_connection((host, port), timeout=15)
        self.req_id = 0
        self._send(3, password)
        rid, _, _ = self._recv()
        if rid == -1:
            raise RuntimeError("RCON authentication failed")

    def _send(self, ptype: int, payload: str) -> int:
        self.req_id += 1
        data = struct.pack("<ii", self.req_id, ptype) + payload.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(data)) + data)
        return self.req_id

    def _recv(self) -> tuple[int, int, str]:
        (length,) = struct.unpack("<i", self._read_exact(4))
        body = self._read_exact(length)
        rid, rtype = struct.unpack("<ii", body[:8])
        return rid, rtype, body[8:-2].decode("utf-8", errors="replace")

    def _read_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("RCON disconnected")
            buf.extend(chunk)
        return bytes(buf)

    def cmd(self, text: str) -> str:
        cmd_id = self._send(2, text)
        if text == 'stop':
            return self._recv()[2]
        # A page-list query spans many RCON replies. Keep its continuations
        # together using an inert, separately numbered response as a delimiter.
        rid, _, body = self._recv()
        if rid != cmd_id:
            raise ValueError(f'Unexpected RCON response {rid}, expected {cmd_id}')
        parts = [body]
        # Vanilla's reader expects a request frame per read, so wait for the
        # first reply before sending the delimiter; never pipeline requests.
        end_id = self._send(2, 'list')
        while True:
            rid, _, body = self._recv()
            if rid == end_id:
                return ''.join(parts)
            if rid != cmd_id:
                raise ValueError(f'Unexpected RCON response {rid}, expected {cmd_id}')
            parts.append(body)

    def score(self, holder: str, obj: str) -> int:
        out = self.cmd(f'scoreboard players get {holder} {obj}')
        if 'has ' in out:
            return int(out.split('has ', 1)[1].split(' ', 1)[0])
        raise AssertionError(f'Unexpected scoreboard output for {holder} {obj}: {out}')

    def close(self) -> None:
        self.sock.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def verify_static(zip_path: Path) -> list[str]:
    errors: list[str] = []
    if not zip_path.exists():
        return [f"Missing archive: {zip_path}"]

    rider = json.loads((ROOT / "vendor/commonground-server/content/tarot/modules/rider/pack.json").read_text(encoding="utf-8"))
    numbers = json.loads((ROOT / "vendor/commonground-server/content/tarot/modules/numbers/pack.json").read_text(encoding="utf-8"))
    expected_cards = {f"rider/{c['id']}" for c in rider["cards"]} | {
        f"numbers/{c['id']}" for c in numbers["cards"]
    }
    if len(expected_cards) != 90:
        errors.append(f"Expected 90 cards in catalog, found {len(expected_cards)}")

    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        names = set(members)
        if len(names) != len(members):
            return ["Archive contains duplicate ZIP members"]
        # Parse all JSON / mcmeta
        for n in sorted(names):
            if n.endswith((".json", ".mcmeta")):
                try:
                    json.loads(zf.read(n).decode("utf-8"))
                except Exception as exc:
                    errors.append(f"Invalid JSON in {n}: {exc}")

        mcmeta = json.loads(zf.read("pack.mcmeta").decode("utf-8"))
        entries = mcmeta.get("overlays", {}).get("entries", [])
        from build import make_pack_mcmeta
        expected_entries = make_pack_mcmeta(include_data=True)["overlays"]["entries"]
        if entries != expected_entries:
            errors.append("Overlay matrix does not match all 11 supported data/resource formats")
        data_overlays = [e["directory"] for e in entries if e["directory"].startswith("data_")]
        res_overlays = [e["directory"] for e in entries if e["directory"].startswith("resource_")]

        for d_ov in data_overlays:
            plural = (d_ov == "data_41_0")
            fn_dir = "functions" if plural else "function"
            pred_dir = "predicates" if plural else "predicate"
            mod_dir = "item_modifiers" if plural else "item_modifier"
            loot_dir = "loot_tables" if plural else "loot_table"
            t_blk_dir = "tags/blocks" if plural else "tags/block"
            t_itm_dir = "tags/items" if plural else "tags/item"
            t_fn_dir = "tags/functions" if plural else "tags/function"

            prefix = f"{d_ov}/data/tarot/"
            fns = {n[len(prefix + fn_dir + "/") : -11] for n in names if n.startswith(prefix + fn_dir + "/") and n.endswith(".mcfunction")}
            preds = {n[len(prefix + pred_dir + "/") : -5] for n in names if n.startswith(prefix + pred_dir + "/") and n.endswith(".json")}
            mods = {n[len(prefix + mod_dir + "/") : -5] for n in names if n.startswith(prefix + mod_dir + "/") and n.endswith(".json")}
            loots = {n[len(prefix + loot_dir + "/") : -5] for n in names if n.startswith(prefix + loot_dir + "/") and n.endswith(".json")}
            blk_tags = {n[len(prefix + t_blk_dir + "/") : -5] for n in names if n.startswith(prefix + t_blk_dir + "/") and n.endswith(".json")}
            itm_tags = {n[len(prefix + t_itm_dir + "/") : -5] for n in names if n.startswith(prefix + t_itm_dir + "/") and n.endswith(".json")}

            for req_tag in ("load", "tick"):
                if f"{d_ov}/data/minecraft/{t_fn_dir}/{req_tag}.json" not in names:
                    errors.append(f"{d_ov}: missing minecraft {t_fn_dir}/{req_tag}.json")

            for fn_name in sorted(fns):
                txt = zf.read(f"{prefix}{fn_dir}/{fn_name}.mcfunction").decode("utf-8")
                for line_no, raw in enumerate(txt.splitlines(), 1):
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    for m in FN_RE.finditer(line):
                        ref = m.group(1)
                        if line == '$function tarot:stack/shuffle_step/$(size)':
                            # This one macro has a finite, checked dispatch domain.
                            # Validate every target instead of accepting a prefix.
                            for size in range(2,129):
                                if f'stack/shuffle_step/{size}' not in fns:
                                    errors.append(f'{d_ov}: missing shuffle step {size}')
                            continue
                        if ref not in fns:
                            errors.append(f"{d_ov} {fn_name}:{line_no}: missing function tarot:{ref}")
                    for m in PRED_RE.finditer(line):
                        ref = m.group(1)
                        if ref not in preds:
                            errors.append(f"{d_ov} {fn_name}:{line_no}: missing predicate tarot:{ref}")
                    for m in LOOT_RE.finditer(line):
                        ref = m.group(1)
                        if ref not in loots:
                            errors.append(f"{d_ov} {fn_name}:{line_no}: missing loot_table tarot:{ref}")
                    if "item modify " in line:
                        for m in MOD_RE.finditer(line):
                            ref = m.group(1)
                            if ref not in mods:
                                errors.append(f"{d_ov} {fn_name}:{line_no}: missing item_modifier tarot:{ref}")
                    for m in TAG_BLK_RE.finditer(line):
                        ref = m.group(1)
                        if ref not in blk_tags and ref not in itm_tags:
                            errors.append(f"{d_ov} {fn_name}:{line_no}: missing tag #tarot:{ref}")

                    # Guard against leftover modern component syntax in early overlays
                    if d_ov in ("data_41_0", "data_48_0", "data_57_0", "data_61_0"):
                        if "equipment." in line or "entity @s equipment" in line:
                            errors.append(f"{d_ov} {fn_name}:{line_no}: leftover 'equipment' in early overlay")
                        if '"minecraft:unbreakable" set value {}' in line:
                            errors.append(f"{d_ov} {fn_name}:{line_no}: modern unbreakable syntax in early overlay")

        # Verify shared assets textures exist for every model
        shared_models = [n for n in names if n.startswith("assets/tarot/models/") and n.endswith(".json")]
        for mn in shared_models:
            mobj = json.loads(zf.read(mn).decode("utf-8"))
            for tkey, tval in mobj.get("textures", {}).items():
                if isinstance(tval, str) and tval.startswith("tarot:"):
                    tpath = f"assets/tarot/textures/{tval.split(':', 1)[1]}.png"
                    if tpath not in names:
                        errors.append(f"{mn}: missing texture {tpath} for {tkey}")

        for r_ov in res_overlays:
            items_prefix = f"{r_ov}/assets/tarot/items/"
            if any(n.startswith(items_prefix) for n in names):
                for key in expected_cards:
                    ip = f"{items_prefix}card/{key}.json"
                    if ip not in names:
                        errors.append(f"{r_ov}: missing item def {ip}")

    return errors


def verify_server_version(zip_path: Path, mc_ver: str) -> list[str]:
    server_jar = CACHE_ROOT / mc_ver / "minecraft-server.jar"
    if not server_jar.exists():
        return [f"{mc_ver}: cached server jar missing at {server_jar}"]

    major_minor = tuple(int(x) for x in mc_ver.split(".")[:2])
    java_bin = JDK25 if major_minor >= (26, 0) else JDK21
    errs: list[str] = []

    with tempfile.TemporaryDirectory(prefix=f"tarot_srv_{mc_ver}_") as tmp:
        srv_dir = Path(tmp)
        (srv_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        dp_dir = srv_dir / "world/datapacks"
        dp_dir.mkdir(parents=True)
        shutil.copy2(zip_path, dp_dir / "Tabletop-Tarot.zip")

        gport = free_port()
        rport = free_port()
        (srv_dir / "server.properties").write_text(
            f"online-mode=false\n"
            f"server-ip=127.0.0.1\n"
            f"server-port={gport}\n"
            f"enable-rcon=true\n"
            f"rcon.port={rport}\n"
            f"rcon.password=tarot\n"
            f"level-type=minecraft\\:flat\n"
            f"generator-settings={FLAT_WORLD_SETTINGS}\n"
            f"spawn-protection=0\n"
            f"white-list=false\n"
            f"enforce-whitelist=false\n"
            f"enforce-secure-profile=false\n"
            f"max-tick-time=-1\n"
            f"pause-when-empty-seconds=0\n",
            encoding="utf-8",
        )

        log_path = srv_dir / "server.log"
        with open(log_path, "w", encoding="utf-8") as logf:
            proc = subprocess.Popen(
                [java_bin, "-Xmx768M", "-jar", str(server_jar), "nogui"],
                cwd=srv_dir,
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
            )
            rcon = None
            try:
                started = False
                for _ in range(180):
                    if proc.poll() is not None:
                        break
                    txt = log_path.read_text(encoding="utf-8", errors="replace")
                    if "Done (" in txt:
                        started = True
                        break
                    time.sleep(0.5)
                if not started:
                    errs.append(f"{mc_ver}: server failed to start\n" + log_path.read_text(errors="replace")[-1500:])
                    return errs

                rcon = RconClient("127.0.0.1", rport, "tarot")
                dplist = rcon.cmd("datapack list enabled")
                if "Tabletop-Tarot.zip" not in dplist:
                    errs.append(f"{mc_ver}: datapack not enabled in `datapack list enabled`: {dplist}")

                reload_out = rcon.cmd("reload")
                time.sleep(0.8)
                if "Reloading!" not in reload_out and reload_out:
                    pass  # reload prints asynchronously on some versions

                setup_out = rcon.cmd("function tarot:setup")
                if "Unknown function" in setup_out or "Failed" in setup_out:
                    errs.append(f"{mc_ver}: function tarot:setup failed: {setup_out}")

                cat_out = rcon.cmd("function tarot:catalogue/load")
                if "Unknown function" in cat_out or "Error" in cat_out:
                    errs.append(f"{mc_ver}: catalogue/load failed: {cat_out}")

                ready = rcon.cmd("scoreboard players get #catalogue_ready tarot.sys")
                if "has 1 " not in ready:
                    errs.append(f"{mc_ver}: #catalogue_ready unexpected: {ready}")

                # Smoke test deck loot; gameplay coverage lives in tests/test_live.py.
                loot_check = rcon.cmd("execute summon minecraft:armor_stand run loot replace entity @s weapon.mainhand loot tarot:decks/rider")
                if "Error" in loot_check or "Unknown" in loot_check:
                    errs.append(f"{mc_ver}: loot decks/rider failed: {loot_check}")
                rcon.cmd("kill @e[type=minecraft:armor_stand]")

                rcon.cmd("forceload add 0 0")
                for _ in range(100):
                    if "passed" in rcon.cmd("execute if loaded 0 0 0").lower():
                        break
                    time.sleep(0.1)
                else:
                    errs.append(f"{mc_ver}: fixture chunk did not finish loading")
                    return errs
                floor = rcon.cmd("execute if block 0 -61 0 minecraft:grass_block if block 0 -64 0 minecraft:bedrock")
                if "passed" not in floor.lower():
                    errs.append(f"{mc_ver}: flat fixture floor differs from its declared layers: {floor}")
                    return errs
                # Exercise each native book codec, not only JSON parsing. The
                # inventory NBT schema changed alongside text objects in 1.21.5.
                modern_equipment = tuple(int(x) for x in mc_ver.split('.')) >= (1,21,5)
                hand = 'equipment.mainhand' if modern_equipment else 'HandItems[0]'
                with zipfile.ZipFile(zip_path) as guide_archive:
                    guide_prefix=VERSION_MAP[mc_ver][0]
                    recipe_folder='recipes' if VERSION_MAP[mc_ver][2] else 'recipe'
                    expected_guide_pages={identity:len(json.loads(guide_archive.read(
                        f'{guide_prefix}/data/tarot/{recipe_folder}/{identity}.json'))['result']['components']['minecraft:written_book_content']['pages'])
                        for identity in ['guidebook','guidebook_alex']}
                rcon.cmd('summon minecraft:armor_stand 0 -60 0 {Tags:["peer.guide_fixture"]}')
                for identity,author in [('guidebook','Steve'),('guidebook_alex','Alex')]:
                    rcon.cmd(f'loot replace entity @e[tag=peer.guide_fixture,limit=1] weapon.mainhand loot tarot:{identity}')
                    path=hand+'.components."minecraft:written_book_content"'
                    result=rcon.cmd(f'execute if data entity @e[tag=peer.guide_fixture,limit=1] {path}{{author:"{author}"}}')
                    if 'passed' not in result.lower():
                        errs.append(f'{mc_ver}: {author} book did not survive its native item codec: {result}')
                    rcon.cmd('scoreboard players set #guide_pages tarot.sys 0')
                    rcon.cmd(f'execute store result score #guide_pages tarot.sys run data get entity @e[tag=peer.guide_fixture,limit=1] {path}.pages')
                    expected_pages=expected_guide_pages[identity]
                    result=rcon.cmd(f'execute if score #guide_pages tarot.sys matches {expected_pages}')
                    if 'passed' not in result.lower():
                        errs.append(f'{mc_ver}: {author} book lost pages in its native item codec: {result}')
                rcon.cmd('kill @e[tag=peer.guide_fixture]')
                # Saved pre-review cards have no layer score and may already sit at
                # .0012/.0024/.0036. Reserve those heights while allocating a neighbor.
                spawn_result = rcon.cmd('summon item_display 0 0 0 {Tags:["tarot.placed","peer.layer_fixture"]}')
                if "summoned" not in spawn_result.lower():
                    errs.append(f"{mc_ver}: fixture summon failed: {spawn_result}")
                    return errs
                for layer in range(1, 10):
                    rcon.cmd('summon item_display 0 0 0 {Tags:["tarot.placed","peer.layer_fixture","peer.slot"]}')
                    rcon.cmd(f'scoreboard players set @e[tag=peer.slot,limit=1] tarot.layer {layer}')
                    rcon.cmd('tag @e[tag=peer.slot] remove peer.slot')
                rcon.cmd('summon item_display 0 0 0 {Tags:["tarot.placed","tarot.new","peer.layer_fixture","peer.layer_new"]}')
                rcon.cmd('execute as @e[tag=peer.layer_new,limit=1] at @s run function tarot:table/micro_lift')
                layer_out = rcon.cmd('scoreboard players get @e[tag=peer.layer_new,limit=1] tarot.layer')
                if "has 11 " not in layer_out:
                    errs.append(f"{mc_ver}: legacy neighbor height collision: {layer_out}")
                rcon.cmd('execute as @e[tag=peer.layer_fixture] run scoreboard players reset @s tarot.layer')
                rcon.cmd('kill @e[tag=peer.layer_fixture]')
                # Budget deferral retains the input but advances fairness to the next entity.
                # A normal tick replenishes this allowance. Hold the fixture's tick
                # steady across RCON round trips so it really tests exhaustion.
                rcon.cmd('tick freeze')
                try:
                    rcon.cmd('summon interaction 0 1 0 {Tags:["peer.defer"],attack:{player:[I;0,0,0,0],timestamp:0L}}')
                    initial = rcon.cmd('execute if data entity @e[tag=peer.defer,limit=1] attack')
                    if "passed" not in initial.lower():
                        raise AssertionError(f"{mc_ver}: deferred attack fixture was not created: {initial}")
                    rcon.cmd('scoreboard players set @e[tag=peer.defer,limit=1] tarot.id 12345')
                    rcon.cmd('scoreboard players set #heavy_left tarot.sys 0')
                    rcon.cmd('scoreboard players set #cursor tarot.sys 0')
                    rcon.cmd('execute as @e[tag=peer.defer,limit=1] at @s run function tarot:queue/touch_serve')
                    cursor_out = rcon.cmd('scoreboard players get #cursor tarot.sys')
                    retained = rcon.cmd('execute if data entity @e[tag=peer.defer,limit=1] attack')
                    if "has 12345 " not in cursor_out or "passed" not in retained.lower():
                        errs.append(f"{mc_ver}: deferred touch lost input or fairness: {cursor_out}; {retained}")
                    rcon.cmd('execute as @e[tag=peer.defer] run scoreboard players reset @s tarot.id')
                    rcon.cmd('kill @e[tag=peer.defer]')
                finally:
                    rcon.cmd('tick unfreeze')
                rcon.cmd('forceload remove 0 0')

                log_txt = log_path.read_text(encoding="utf-8", errors="replace")
                bad_lines = []
                for line in log_txt.splitlines():
                    low = line.lower()
                    if any(tok in low for tok in ("tarot", "datapack", "tabletop")):
                        if any(lvl in low for lvl in ("error", "exception", "failed to load", "couldn't parse", "unknown tag", "unknown function", "invalid")):
                            bad_lines.append(line)
                    elif "failed to load function" in low or "couldn't parse data" in low or "missing or invalid" in low:
                        bad_lines.append(line)
                if bad_lines:
                    errs.append(f"{mc_ver}: log errors found:\n" + "\n".join(bad_lines[:20]))
            finally:
                if rcon:
                    try:
                        rcon.cmd("stop")
                        rcon.close()
                    except Exception:
                        pass
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
    return errs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=None, help="Path to built combined zip (defaults to latest dist/Tabletop-Tarot-*.zip excluding -resourcepack.zip)")
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--versions", nargs="*", default=list(VERSION_MAP.keys()))
    args = parser.parse_args()

    zip_path = args.zip
    if zip_path is None:
        cands = sorted(p for p in (ROOT / "dist").glob("Tabletop-Tarot-*.zip") if not p.name.endswith("-resourcepack.zip"))
        if not cands:
            print("No built zip found in dist/; run tools/build.py first.", file=sys.stderr)
            return 2
        zip_path = cands[-1]

    print(f"Verifying archive: {zip_path}")
    static_errors = verify_static(zip_path)
    if static_errors:
        print(f"STATIC VERIFICATION FAILED ({len(static_errors)} errors):")
        for e in static_errors[:40]:
            print("  -", e)
        return 1
    print("Static verification: PASS")

    if args.static_only:
        return 0

    all_srv_errors: list[str] = []
    for mc_ver in args.versions:
        print(f"Booting & verifying dedicated server {mc_ver}...")
        errs = verify_server_version(zip_path, mc_ver)
        if errs:
            print(f"  FAIL {mc_ver}:")
            for e in errs:
                print("   ", e)
            all_srv_errors.extend(errs)
        else:
            print(f"  PASS {mc_ver}")

    if all_srv_errors:
        print(f"\nSERVER VERIFICATION FAILED ({len(all_srv_errors)} issues)")
        return 1
    print("\nAll server versions verified cleanly!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
