#!/usr/bin/env python3
"""End-to-end stock-client verification across all supported Minecraft versions."""

from __future__ import annotations

import argparse
import functools
import glob
import hashlib
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

if not __debug__:
    print("Live verification requires assertions; remove -O or PYTHONOPTIMIZE.", file=sys.stderr)
    raise SystemExit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify import CACHE_ROOT, FLAT_WORLD_SETTINGS, JDK21, JDK25, VERSION_MAP, RconClient

print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def resolve_client_env(ver: str) -> dict:
    info = json.loads((CACHE_ROOT / ver / "mojang_minecraft_info.json").read_text(encoding="utf-8"))
    jars, natives = [], []
    for lib in info["libraries"]:
        rules = lib.get("rules", [])
        allow = True if not rules else False
        for r in rules:
            os_name = r.get("os", {}).get("name")
            if os_name is None or os_name == "linux":
                allow = (r["action"] == "allow")
        if not allow:
            continue
        parts = lib["name"].split(":")
        grp, art, v = parts[0], parts[1], parts[2]
        clf = parts[3] if len(parts) > 3 else ""
        suffix = ("-" + clf) if clf else ""
        gradle_home = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
        hits = glob.glob(str(gradle_home / f"caches/modules-2/files-2.1/{grp}/{art}/{v}/*/{art}-{v}{suffix}.jar"))
        if not hits and lib.get("downloads", {}).get("artifact"):
            local = CACHE_ROOT / ver / "libraries" / lib["downloads"]["artifact"]["path"]
            if local.is_file():
                assert hashlib.sha1(local.read_bytes()).hexdigest() == lib["downloads"]["artifact"]["sha1"], f"Changed official library: {local}"
                hits = [str(local)]
        if not hits:
            raise FileNotFoundError(lib["name"])
        (natives if "natives-linux" in clf else jars).append(hits[0])
    jars.append(str(CACHE_ROOT / ver / "minecraft-client.jar"))
    java_bin = JDK25 if info["javaVersion"]["majorVersion"] >= 25 else JDK21
    asset_index = info["assetIndex"]["id"]
    assets_dir = str(CACHE_ROOT / "assets")
    if not os.path.isfile(f"{assets_dir}/indexes/{asset_index}.json"):
        assets_dir = str(Path.home() / ".gradle/caches/neoformruntime/assets")
    with zipfile.ZipFile(CACHE_ROOT / ver / "minecraft-client.jar") as client:
        data_version = json.loads(client.read("version.json"))["world_version"]
    return {
        "java": java_bin,
        "main": info["mainClass"],
        "classpath": ":".join(jars),
        "natives": natives,
        "assets_dir": assets_dir,
        "asset_index": asset_index,
        "server_jar": str(CACHE_ROOT / ver / "minecraft-server.jar"),
        "options_ver": str(data_version),
    }


def start_http_server(directory: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def run_suite_for_version(ver: str, pack_zip: Path, artifacts_dir: Path, adversarial_only: bool = False, polish_only: bool = False, backend_only: bool = False, controls_only: bool = False, motion_only: bool = False, baseline_visual: bool = False, guidebook_only: bool = False) -> None:
    print(f"\n=== Live Multi-Client Test Suite: Minecraft {ver} ===")
    env_info = resolve_client_env(ver)
    pack_zip = pack_zip.resolve()
    artifacts_dir = artifacts_dir.resolve()
    work = artifacts_dir / f"live_{ver.replace('.', '_')}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    rp_zip = pack_zip.with_name(pack_zip.stem + "-resourcepack.zip")
    served_zip = rp_zip if rp_zip.is_file() else pack_zip

    http_dir = work / "http"
    http_dir.mkdir()
    shutil.copy2(served_zip, http_dir / "Tabletop-Tarot.zip")
    sha1 = hashlib.sha1(served_zip.read_bytes()).hexdigest()
    httpd, http_port = start_http_server(http_dir)

    srv_dir = work / "server"
    srv_dir.mkdir()
    (srv_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    dp_dir = srv_dir / "world/datapacks"
    dp_dir.mkdir(parents=True)
    shutil.copy2(pack_zip, dp_dir / "Tabletop-Tarot.zip")
    # Released loot fixtures exercise saved 1.0.0 items without shipping test content.
    fixture = ROOT / "tests/fixtures/1.0.0" / (VERSION_MAP[ver][0] + ".json")
    fixture_pack = dp_dir / "peer-fixtures"
    plural = VERSION_MAP[ver][2]
    loot_dir = fixture_pack / "data/peer" / ("loot_tables" if plural else "loot_table")
    loot_dir.mkdir(parents=True)
    shutil.copy2(fixture, loot_dir / "baseline.json")
    from build import TARGETS
    target = next(t for t in TARGETS if t.mc_version == ver)
    (fixture_pack / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": target.data_format[0], "min_format": list(target.data_format), "max_format": list(target.data_format), "description": "Peer review fixtures"}}))

    game_port = free_port()
    rcon_port = free_port()
    (srv_dir / "server.properties").write_text(
        f"online-mode=false\n"
        f"server-ip=127.0.0.1\n"
        f"server-port={game_port}\n"
        f"enable-rcon=true\n"
        f"rcon.port={rcon_port}\n"
        f"rcon.password=tarot\n"
        f"level-type=minecraft\\:flat\n"
        f"generator-settings={FLAT_WORLD_SETTINGS}\n"
        f"spawn-protection=0\n"
        f"pvp=false\n"
        f"difficulty=peaceful\n"
        f"white-list=false\n"
        f"enforce-whitelist=false\n"
        f"enforce-secure-profile=false\n"
        f"view-distance=6\n"
        f"max-tick-time=-1\n"
        f"pause-when-empty-seconds=0\n"
        f"resource-pack=http://127.0.0.1:{http_port}/Tabletop-Tarot.zip\n"
        f"resource-pack-sha1={sha1}\n",
        encoding="utf-8",
    )

    srv_log = open(work / "server.log", "w", encoding="utf-8")
    srv_proc = subprocess.Popen(
        [env_info["java"], "-Xmx1024M", "-jar", env_info["server_jar"], "nogui"],
        cwd=srv_dir,
        stdout=srv_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
    )

    clients = []
    rcon = None
    try:
        for _ in range(180):
            if "Done (" in (work / "server.log").read_text(errors="replace"):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"{ver} server timed out booting")

        rcon = RconClient("127.0.0.1", rcon_port, "tarot")
        rcon.cmd("gamerule doDaylightCycle false")
        rcon.cmd("gamerule doWeatherCycle false")
        rcon.cmd("time set 6000")
        rcon.cmd("setworldspawn 0 -60 0")
        rcon.cmd("gamerule sendCommandFeedback false")
        rcon.cmd("gamerule logAdminCommands false")

        def xdo(disp: str, *args: str) -> None:
            subprocess.run(["xdotool", *args], env={**os.environ, "DISPLAY": disp}, capture_output=True, check=True)
            if len(args) == 2 and args[0] == "key" and args[1] in "123456789":
                player = next((row[0] for row in clients if row[1] == disp), None)
                if player:
                    expected = int(args[1]) - 1
                    deadline = time.monotonic() + 5
                    while True:
                        rcon.cmd(f'execute store result score #input_slot tarot.sys run data get entity {player} SelectedItemSlot')
                        if rcon.score('#input_slot','tarot.sys') == expected:
                            break
                        if time.monotonic() >= deadline:
                            raise AssertionError(f'{player}: hotbar switch to {expected} did not reach the server')
                        time.sleep(0.05)

        def shot(disp: str, filename: str) -> None:
            subprocess.run(["import", "-window", "root", str(work / filename)], env={**os.environ, "DISPLAY": disp}, check=True)

        def count_placed(near: str | None = None) -> int:
            sel = f"@e[type=minecraft:item_display,tag=tarot.placed{',' + near if near else ''}]"
            rcon.cmd(f"execute store result score #tcnt tarot.sys if entity {sel}")
            return rcon.score("#tcnt", "tarot.sys")

        def deck_size(player: str, slot: int) -> int:
            rcon.cmd(f'execute store result score #dsz tarot.sys run data get entity {player} Inventory[{{Slot:{slot}b}}].components."minecraft:charged_projectiles"')
            return rcon.score("#dsz", "tarot.sys")

        def launch_and_join(name: str, disp: str) -> None:
            xvfb = subprocess.Popen(
                ["Xvfb", disp, "-screen", "0", "1280x720x24", "+extension", "GLX"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.4)
            cdir = work / f"client_{name}"
            cdir.mkdir()
            nat_dir = cdir / "natives"
            nat_dir.mkdir()
            for nj in env_info["natives"]:
                with zipfile.ZipFile(nj) as zf:
                    for m in zf.namelist():
                        if ".so" in m:
                            zf.extract(m, nat_dir)
            (cdir / "options.txt").write_text(
                f"version:{env_info['options_ver']}\n"
                "pauseOnLostFocus:false\n"
                "skipMultiplayerWarning:true\n"
                "joinedFirstServer:true\n"
                "onboardAccessibility:false\n"
                "tutorialStep:none\n"
                "fov:0.0\n"
                "renderDistance:4\n"
                "soundCategory_master:0.0\n"
                "guiScale:3\n"
                "autoJump:false\n"
                "rawMouseInput:false\n"
                "enableVsync:false\n",
                encoding="utf-8",
            )
            uid = str(uuid.UUID(bytes=hashlib.md5(f"OfflinePlayer:{name}".encode()).digest()[:16], version=3))
            clog = open(work / f"client_{name}.log", "w", encoding="utf-8")
            env = os.environ.copy()
            env["DISPLAY"] = disp
            env["SDL_VIDEODRIVER"] = "x11"
            env.pop("WAYLAND_DISPLAY", None)
            env["LIBGL_ALWAYS_SOFTWARE"] = "1"
            cproc = subprocess.Popen(
                [
                    env_info["java"],
                    "-Xmx1024M",
                    # Patchy's blocklist URLConnection otherwise has an unlimited wait.
                    "-Dsun.net.client.defaultConnectTimeout=10000",
                    "-Dsun.net.client.defaultReadTimeout=10000",
                    f"-Djava.library.path={nat_dir}",
                    f"-Dorg.lwjgl.librarypath={nat_dir}",
                    "-cp",
                    env_info["classpath"],
                    env_info["main"],
                    "--username",
                    name,
                    "--version",
                    ver,
                    "--gameDir",
                    str(cdir),
                    "--assetsDir",
                    env_info["assets_dir"],
                    "--assetIndex",
                    env_info["asset_index"],
                    "--uuid",
                    uid,
                    "--accessToken",
                    "0",
                    "--versionType",
                    "release",
                    "--width",
                    "1280",
                    "--height",
                    "720",
                    "--quickPlayMultiplayer",
                    f"127.0.0.1:{game_port}",
                ],
                cwd=cdir,
                env=env,
                stdout=clog,
                stderr=subprocess.STDOUT,
            )
            clients.append((name, disp, xvfb, cproc, cdir))

            conn_step = None
            for step in range(160):
                if cproc.poll() is not None:
                    raise AssertionError(f"{name} client exited early on {ver}: {(work / f'client_{name}.log').read_text(errors='replace')[-1800:]}")
                txt = (work / "server.log").read_text(errors="replace")
                if f"{name} joined the game" in txt:
                    print(f"  [join] {name} joined on {ver} (step {step})")
                    return
                clog_txt = (work / f"client_{name}.log").read_text(errors="replace")
                if "Connecting to 127.0.0.1" in clog_txt:
                    if conn_step is None:
                        conn_step = step
                    elif (step - conn_step) >= 2 and (step - conn_step) % 4 == 0:
                        xdo(disp, "mousemove", "420", "430", "click", "1")
                time.sleep(0.5)
            jcmd = Path(env_info["java"]).with_name("jcmd")
            if jcmd.is_file():
                try:
                    diagnostic = subprocess.run([str(jcmd), str(cproc.pid), "Thread.print"],
                                                capture_output=True, text=True, timeout=10)
                    (work / f"client_{name}.threads.txt").write_text(diagnostic.stdout + diagnostic.stderr)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    (work / f"client_{name}.threads.txt").write_text(str(exc))
            try:
                shot(disp, f"debug_{name.lower()}.png")
            except Exception:
                pass
            raise AssertionError(f"{name} failed to join on {ver}; client log tail:\n{(work / f'client_{name}.log').read_text(errors='replace')[-1500:]}")

        launch_and_join("TarotVisual" if backend_only else "Alice", ":91")
        launch_and_join("Bob", ":92")
        time.sleep(2.5)

        if guidebook_only:
            from guidebook_live import run_guidebook
            run_guidebook(ver,rcon,xdo,work,shot,pack_zip.parent/'guidebook-index.json')
            return

        if motion_only:
            from motion import run_motion
            run_motion(ver, rcon, xdo, work, shot, baseline_visual)
            return

        if backend_only:
            from backend import run_backend
            run_backend(ver, rcon, work)
            return

        if controls_only:
            from controls import run_controls
            run_controls(ver, rcon, xdo, work)
            return

        if polish_only:
            from polish import run_polish
            run_polish(ver, rcon, xdo, work)
            return

        if adversarial_only:
            from adversarial import run_adversarial
            run_adversarial(ver, rcon, xdo, count_placed, deck_size, work, shot)
            return

        # 1. Verify quiet join (empty inventories, zero join gifts/spam)
        for p in ("Alice", "Bob"):
            rcon.cmd(f"execute store result score #inv tarot.sys if data entity {p} Inventory[0]")
            assert rcon.score("#inv", "tarot.sys") == 0, f"{p} received unsolicited item on join!"
        for p in ("Alice", "Bob"):
            log = (work / f"client_{p}.log").read_text(errors="replace")
            chat = [line.split("[CHAT]", 1)[1].strip() for line in log.splitlines() if "[CHAT]" in line]
            assert all(msg in ("Alice joined the game", "Bob joined the game") for msg in chat), chat
            assert any("Reloading ResourceManager:" in line and "server/" in line for line in log.splitlines()), f"{p}: server resource pack not applied"
        print("  [1] Quiet join & empty starter inventory verified")

        rcon.cmd("gamemode survival Alice")
        rcon.cmd("gamemode survival Bob")
        rcon.cmd("fill -12 -61 -4 12 -61 12 grass_block")
        rcon.cmd("fill -12 -60 -4 12 -52 12 air")
        rcon.cmd("tp Bob 10.5 -60 -2.5 0 0")

        # 2. Recipe book advancement unlock
        rcon.cmd("clear Alice")
        rcon.cmd("give Alice minecraft:paper 8")
        rcon.cmd("give Alice minecraft:ink_sac 1")
        rcon.cmd("clear Bob")
        rcon.cmd("give Bob minecraft:paper 8")
        rcon.cmd("give Bob minecraft:lapis_lazuli 1")
        time.sleep(0.5)
        adv_a = rcon.cmd("advancement grant Alice only tarot:recipes/rider_deck")
        adv_b = rcon.cmd("advancement grant Bob only tarot:recipes/numbers_deck")
        # advancement grant replies "Nothing changed" if already earned organically!
        assert "already have it" in adv_a or "Nothing changed" in adv_a, adv_a
        assert "already have it" in adv_b or "Nothing changed" in adv_b, adv_b
        print("  [2] Survival recipe-book advancements unlocked organically")

        # 3. Cozy Surfaces Matrix (bottom/top slabs, red carpet, moss carpet, top/bottom closed trapdoors, upside-down stairs, bookshelf, chiseled_bookshelf, blackstone)
        surfaces = [
            ("oak_planks", "minecraft:oak_planks", 1.021, -8),
            ("bookshelf", "minecraft:bookshelf", 1.021, -7),
            ("chiseled_bookshelf", "minecraft:chiseled_bookshelf", 1.021, -6),
            ("blackstone", "minecraft:blackstone", 1.021, -5),
            ("slab_bottom", "minecraft:oak_slab[type=bottom]", 0.521, -4),
            ("slab_top", "minecraft:oak_slab[type=top]", 1.021, -3),
            ("stairs_top", "minecraft:oak_stairs[half=top]", 1.021, -2),
            ("trapdoor_top", "minecraft:oak_trapdoor[open=false,half=top]", 1.021, -1),
            ("trapdoor_low", "minecraft:oak_trapdoor[open=false,half=bottom]", 0.2085, 0),
            ("red_carpet", "minecraft:red_carpet", 0.0835, 1),
            ("moss_carpet", "minecraft:moss_carpet", 0.0835, 2),
        ]
        for label, blk, expected_dy, x in surfaces:
            sneak_place = "trapdoor" in label
            rcon.cmd(f"setblock {x} -60 4 {blk}")
            rcon.cmd("clear Alice")
            xdo(":91", "key", "1")
            time.sleep(0.1)
            rcon.cmd("loot replace entity Alice hotbar.0 loot tarot:decks/rider")
            time.sleep(0.15)
            rcon.cmd("execute as Alice run trigger tarot.action set 1")
            time.sleep(0.3)
            # Stand close & look dead-center at top of block (x+0.5, -60+top, 4.5)
            target_y = -60.0 + expected_dy - 0.021
            import math
            eye_y = -58.73 if sneak_place else -58.38
            dz = 4.5 - 2.6
            dy = eye_y - target_y
            pitch = math.degrees(math.atan2(dy, dz))
            rcon.cmd(f"tp Alice {x + 0.5} -60 2.6 0 {pitch:.2f}")
            time.sleep(0.2)
            if sneak_place:
                xdo(":91", "keydown", "Shift_L")
                time.sleep(0.15)
            xdo(":91", "key", "2")
            time.sleep(0.15)
            xdo(":91", "click", "3")
            time.sleep(0.4)
            if sneak_place:
                xdo(":91", "keyup", "Shift_L")
                time.sleep(0.1)
            pos_sel = f"x={x+0.5},y={-60.0 + expected_dy:.4f},z=4.5,distance=..0.6"
            n_here = count_placed(pos_sel)
            assert n_here == 1, f"{ver}: Failed to place on {label} ({blk}) at x={x}"
            rcon.cmd(f"execute as @e[type=minecraft:item_display,tag=tarot.placed,{pos_sel},limit=1] store result score #precise_y tarot.sys run data get entity @s Pos[1] 10000")
            assert abs(rcon.score("#precise_y", "tarot.sys") / 10000 - (-60.0 + expected_dy)) < 0.005, f"{ver}: Wrong card height on {label}"
            # Verify support survives a full maintenance pass (>4 ticks)
            time.sleep(0.35)
            assert count_placed(pos_sel) == 1, f"{ver}: Card dropped unexpectedly from {label}"
        print(f"  [3] All {len(surfaces)} cozy builder surfaces verified & supported")

        # Carpet stacked on top of oak_planks (steep vertical look check!)
        rcon.cmd("setblock 4 -60 4 oak_planks")
        rcon.cmd("setblock 4 -59 4 blue_carpet")
        rcon.cmd("setblock 4 -60 3 oak_planks")
        rcon.cmd("clear Alice")
        xdo(":91", "key", "1")
        time.sleep(0.1)
        rcon.cmd("loot replace entity Alice hotbar.0 loot tarot:decks/numbers")
        time.sleep(0.15)
        rcon.cmd("execute as Alice run trigger tarot.action set 1")
        time.sleep(0.3)
        rcon.cmd("tp Alice 4.5 -59 3.3 0 52.4")
        time.sleep(0.25)
        xdo(":91", "key", "2")
        time.sleep(0.15)
        xdo(":91", "click", "3")
        time.sleep(0.4)
        assert count_placed("x=4.5,y=-58.9165,z=4.5,distance=..0.6") == 1, f"{ver}: Carpet-on-plank steep raycast placement failed!"
        print("  [4] Steep look onto carpet-on-plank verified")

        # Trapdoor open drops card safely into item
        rcon.cmd("kill @e[type=minecraft:item]")
        rcon.cmd("setblock 0 -60 4 minecraft:oak_trapdoor[open=true,half=bottom]")
        time.sleep(0.6)
        assert count_placed("x=0.5,y=-59.8,z=4.5,distance=..1.0") == 0, f"{ver}: Card failed to drop when trapdoor opened!"
        rcon.cmd("execute store result score #itms tarot.sys if entity @e[type=minecraft:item,x=0.5,y=-59.8,z=4.5,distance=..1.5]")
        assert rcon.score("#itms", "tarot.sys") == 1, f"{ver}: Dropped item missing after trapdoor opened!"
        rcon.cmd("kill @e[type=minecraft:item]")
        print("  [5] Opening trapdoor releases placed card safely")

        # Clean table stage for tight 3-card spread, blind deal, cross-table multiplayer, return & scoop
        rcon.cmd("execute as @e[tag=tarot.placed] run kill @s")
        rcon.cmd("execute as @e[tag=tarot.touch] run kill @s")
        rcon.cmd("fill -12 -60 0 12 -52 12 air")
        rcon.cmd("fill -2 -60 5 2 -60 6 oak_planks")
        rcon.cmd("fill -1 -59 5 1 -59 5 purple_carpet")

        # Give Alice Rider Deck in slot 0, Bob Numbers Deck in slot 0
        rcon.cmd("clear Alice")
        rcon.cmd("clear Bob")
        rcon.cmd("loot replace entity Alice hotbar.0 loot tarot:decks/rider")
        rcon.cmd("loot replace entity Bob hotbar.0 loot tarot:decks/numbers")
        time.sleep(0.3)

        # 6. Blind deal 3 cards side-by-side onto purple_carpet (-0.42, 0.0, +0.42 around x=0.5, z=5.5) with trigger 5
        for idx, offset_x in enumerate((-0.42, 0.0, 0.42)):
            rcon.cmd(f"tp Alice {0.5 + offset_x:.2f} -60 3.7 0 17.2")
            time.sleep(0.25)
            xdo(":91", "key", "1")
            time.sleep(0.1)
            rcon.cmd("execute as Alice run trigger tarot.action set 5")
            deadline = time.monotonic() + 3
            while deck_size("Alice", 0) != 77 - idx and time.monotonic() < deadline:
                time.sleep(0.05)
            assert deck_size("Alice", 0) == 77 - idx, f"{ver}: Spread deal {idx + 1} did not complete"
        assert deck_size("Alice", 0) == 75, f"{ver}: Expected 75 cards after 3 blind deals, got {deck_size('Alice', 0)}"
        assert count_placed("x=0.5,y=-58.9,z=5.5,distance=..2.0") == 3, f"{ver}: Expected 3-card tight spread!"
        rcon.cmd("execute store result score #hot1 tarot.sys if items entity Alice hotbar.1 *")
        assert rcon.score("#hot1", "tarot.sys") == 0, f"{ver}: Blind deal leaked into hotbar!"
        print("  [6] Blind deal (trigger 5) 3-card tight spread (0.42m spacing) verified")
        spread = [f'@e[type=minecraft:item_display,tag=tarot.placed,x={x},y=-58.9165,z=5.5,distance=..0.15,limit=1]' for x in (0.08,0.5,0.92)]
        for selector, expected_x in zip(spread, (0.08,0.5,0.92)):
            rcon.cmd(f'execute store result score #spread_x tarot.sys run data get entity {selector} Pos[0] 10000')
            assert abs(rcon.score('#spread_x','tarot.sys')/10000-expected_x)<0.005, 'Spread spacing changed'

        # 7. Holding Deck, right-click to flip center card & sneak-right-click to rotate, NO accidental draw!
        rcon.cmd("tp Alice 0.5 -60 3.7 0 17.2")
        time.sleep(0.25)
        xdo(":91", "key", "1")
        time.sleep(0.1)
        xdo(":91", "click", "3")
        time.sleep(0.4)
        assert deck_size("Alice", 0) == 75, f"{ver}: Deck drew accidentally when flipping placed card!"
        rcon.cmd("execute as @e[type=minecraft:item_display,tag=tarot.placed,x=0.5,y=-58.9,z=5.5,sort=nearest,limit=1] run scoreboard players operation #cf tarot.sys = @s tarot.face")
        assert rcon.score("#cf", "tarot.sys") == 1, f"{ver}: Center card did not flip face-up!"

        xdo(":91", "keydown", "Shift_L")
        time.sleep(0.25)
        # Crouching drops eye by 0.35m (1.62 -> 1.27): dy = -58.73 - (-58.9165) = 0.1865, dz=1.8 -> pitch 5.9°
        rcon.cmd("tp Alice 0.5 -60 3.7 0 4.8")
        time.sleep(0.15)
        xdo(":91", "click", "3")
        time.sleep(0.35)
        xdo(":91", "keyup", "Shift_L")
        time.sleep(0.2)
        rot = rcon.cmd("execute as @e[type=minecraft:item_display,tag=tarot.placed,x=0.5,y=-58.9,z=5.5,sort=nearest,limit=1] run data get entity @s Rotation[0]")
        assert "225" in rot or "-135" in rot, f"{ver}: Sneak-rotate failed: {rot}"
        print("  [7] Flip & Sneak-Rotate while holding Deck verified (tight hitbox isolated cleanly)")

        # Bob across table flips left card & Alice captures screenshot of multiplayer spread!
        face_before = [rcon.score(selector,'tarot.face') for selector in spread]
        rcon.cmd("tp Bob 0.92 -60 7.3 180 17.2")
        time.sleep(0.25)
        xdo(":92", "click", "3")
        time.sleep(0.4)
        face_after = [rcon.score(selector,'tarot.face') for selector in spread]
        assert face_after == [face_before[0],face_before[1],1-face_before[2]], f"{ver}: Bob's click changed the wrong card or a neighbour: {face_before} -> {face_after}"
        rcon.cmd("tp Alice 0.5 -60 3.5 0 22")
        rcon.cmd("tp Bob 0.5 -59.5 7.5 180 18")
        time.sleep(0.6)
        shot(":91", "multiplayer_spread.png")
        print("  [8] Cross-table multiplayer flip & visual screenshot captured")

        # 8. Hit one card WITH Rider Deck held -> returns straight onto top of deck (+1 -> 76)
        rcon.cmd("tp Alice 0.08 -60 3.7 0 15.4")
        time.sleep(0.25)
        xdo(":91", "key", "1")
        time.sleep(0.15)
        xdo(":91", "click", "1")
        time.sleep(0.45)
        assert deck_size("Alice", 0) == 76, f"{ver}: Expected 76 after direct hit return-to-deck, got {deck_size('Alice', 0)}"
        assert count_placed("x=0.5,y=-58.9,z=5.5,distance=..2.0") == 2, f"{ver}: Expected 2 cards left on carpet"

        # Sneak + Hit with Rider Deck -> scoops remaining spread back into deck (+2 -> 78)!
        xdo(":91", "keydown", "Shift_L")
        time.sleep(0.25)
        rcon.cmd("tp Alice 0.5 -60 3.7 0 4.8")
        time.sleep(0.15)
        xdo(":91", "click", "1")
        time.sleep(0.45)
        xdo(":91", "keyup", "Shift_L")
        time.sleep(0.2)
        assert deck_size("Alice", 0) == 78, f"{ver}: Expected full 78 after spread scoop, got {deck_size('Alice', 0)}"
        assert count_placed("x=0.5,y=-58.9,z=5.5,distance=..2.0") == 0, f"{ver}: Spread not fully scooped!"
        print("  [9] Direct hit return-to-deck & sneak-hit spread scoop verified (78/78 conserved!)")

        # 9. Custom-named card drop via block break (macro-free drop_item check)
        rcon.cmd("setblock 0 -59 5 air")
        rcon.cmd("setblock 0 -60 5 oak_planks")
        rcon.cmd("execute as Alice run trigger tarot.action set 1")
        time.sleep(0.35)
        # Rename card in slot 1 (drawn card) with quotes/apostrophe
        if ver == "26.3":
            rcon.cmd('item modify entity Alice container.1 {"type":"minecraft:set_name","name":{"text":"Ada\'s \\"Luck\\" Card","italic":false}}')
        else:
            rcon.cmd('item modify entity Alice container.1 {"function":"minecraft:set_name","name":{"text":"Ada\'s \\"Luck\\" Card","italic":false}}')
        original_name = rcon.cmd('data get entity Alice Inventory[{Slot:1b}].components."minecraft:custom_name"').split("entity data: ", 1)[-1]
        rcon.cmd("tp Alice 0.5 -60 3.5 0 17.2")
        time.sleep(0.25)
        xdo(":91", "key", "2")
        time.sleep(0.15)
        xdo(":91", "click", "3")
        time.sleep(0.4)
        assert count_placed("x=0.5,y=-58.9,z=5.5,distance=..1.2") == 1, f"{ver}: Custom-named card did not place"
        rcon.cmd("kill @e[type=minecraft:item]")
        rcon.cmd("setblock 0 -60 5 air")
        time.sleep(0.55)
        rcon.cmd("execute store result score #ditm tarot.sys if entity @e[type=minecraft:item,x=0.5,y=-59.0,z=5.5,distance=..1.5]")
        assert rcon.score("#ditm", "tarot.sys") == 1, f"{ver}: Custom-named card failed to drop when plank broken!"
        cname = rcon.cmd('execute as @e[type=minecraft:item,x=0.5,y=-59.0,z=5.5,distance=..1.5,sort=nearest,limit=1] run data get entity @s Item.components."minecraft:custom_name"')
        assert cname.split("entity data: ", 1)[-1] == original_name, f"{ver}: Custom name changed on drop: {cname}"
        rcon.cmd("kill @e[type=minecraft:item]")
        print("  [10] Custom-named card drop physics & name preservation verified")

        # 10. Boat mount trigger + full inventory safety
        mounted = False
        for boat in ("minecraft:oak_boat", "minecraft:boat"):
            reply = rcon.cmd(f'summon {boat} -4 -60 2 {{Tags:["peer.mount"]}}')
            if "summoned" in reply.lower():
                mounted = True
                break
        assert mounted, f"{ver}: Could not create the actual boat fixture: {reply}"
        rcon.cmd('ride Bob mount @e[tag=peer.mount,limit=1]')
        assert "passed" in rcon.cmd('execute as Bob on vehicle if entity @s[tag=peer.mount]').lower(), "Bob did not mount the boat"
        time.sleep(0.25)
        rcon.cmd("execute as Bob run trigger tarot.action set 2")  # shuffle
        time.sleep(0.35)
        rcon.cmd("execute as Bob run trigger tarot.action set 1")  # draw
        time.sleep(0.35)
        assert deck_size("Bob", 0) == 11, f"{ver}: Boat draw expected 11, got {deck_size('Bob', 0)}"
        rcon.cmd("ride Bob dismount")
        for s in range(1, 36):
            rcon.cmd(f"item replace entity Bob container.{s} with minecraft:stone 1")
        rcon.cmd("tp Bob -4.5 -60 2.0 0 0")
        time.sleep(0.25)
        xdo(":92", "key", "1")
        time.sleep(0.15)
        xdo(":92", "click", "3")
        time.sleep(0.4)
        assert deck_size("Bob", 0) == 11, f"{ver}: Full-inventory draw leaked/corrupted deck size ({deck_size('Bob', 0)})!"
        print("  [11] Boat mount trigger & full-inventory conservation verified")

        from adversarial import run_adversarial
        adversarial_count = run_adversarial(ver, rcon, xdo, count_placed, deck_size, work, shot)

        from controls import run_controls
        from polish import run_polish
        run_controls(ver, rcon, xdo, work)
        run_polish(ver, rcon, xdo, work)
        from motion import run_motion
        run_motion(ver, rcon, xdo, work, shot)
        from guidebook_live import run_guidebook
        run_guidebook(ver,rcon,xdo,work,shot,pack_zip.parent/'guidebook-index.json')

        # Check server log has zero tarot errors
        srv_txt = (work / "server.log").read_text(errors="replace")
        for line in srv_txt.splitlines():
            low = line.lower()
            if "tarot" in low and any(w in low for w in ("error", "exception", "failed to load", "couldn't")):
                raise AssertionError(f"{ver} server log error: {line}")

        (work / "result.json").write_text(json.dumps({"minecraft": ver, "pack": str(pack_zip), "sha256": hashlib.sha256((dp_dir / "Tabletop-Tarot.zip").read_bytes()).hexdigest(), "status": "pass", "live_scenarios": 11, "adversarial_scenarios": adversarial_count, "physical_control_cases": 7, "transaction_feedback_cases": 5, "motion_cases": 8, "guidebook_cases":12}, indent=2) + "\n")
        print(f"=== {ver} ALL LIVE MULTI-CLIENT TESTS PASSED ===")
    except BaseException as error:
        failure = {"minecraft": ver, "error": repr(error), "archive_sha256": hashlib.sha256(pack_zip.read_bytes()).hexdigest(), "state": {}}
        if rcon:
            queries = [f"data get entity {p} {field}" for p in ("Alice", "Bob") for field in ("Pos", "Rotation", "Motion")]
            queries += [f"scoreboard players get {holder} {objective}" for holder, objective in
                        [("#placed", "tarot.sys"), ("#carrier_safe", "tarot.sys"), ("#committed", "tarot.sys"),
                         ("Alice", "tarot.cool"), ("Alice", "tarot.action"), ("Alice", "tarot.pending")]]
            queries += ['execute as @e[type=minecraft:item_display,tag=tarot.placed] run data get entity @s Pos']
            queries += ['data get entity Alice SelectedItem','data get entity Bob SelectedItem','data get block 0 -60 2 Page',
                        'execute as @e[type=minecraft:interaction,tag=tarot.touch] run data get entity @s',
                        'execute as @e[type=minecraft:item_display,tag=tarot.placed] run scoreboard players get @s tarot.face',
                        'execute if block 0 -59 2 minecraft:purple_carpet', 'execute if block 0 -60 2 minecraft:oak_planks']
            for query in queries:
                try:
                    failure["state"][query] = rcon.cmd(query)
                except Exception as diagnostic_error:
                    failure["state"][query] = repr(diagnostic_error)
        for name, disp, *_ in clients:
            try:
                shot(disp, f"failure_{name.lower()}.png")
            except Exception:
                pass
        (work / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise
    finally:
        if rcon:
            try:
                rcon.cmd("stop")
                rcon.close()
            except Exception:
                pass
        try:
            srv_proc.wait(timeout=10)
        except Exception:
            srv_proc.kill()
        for _, _, xvfb, cproc, _ in clients:
            cproc.terminate()
            try:
                cproc.wait(timeout=5)
            except Exception:
                cproc.kill()
            xvfb.terminate()
        httpd.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--adversarial-only", action="store_true")
    mode.add_argument("--polish-only", action="store_true")
    mode.add_argument("--backend-only", action="store_true")
    mode.add_argument("--controls-only", action="store_true")
    mode.add_argument("--motion-only", action="store_true")
    mode.add_argument("--guidebook-only", action="store_true")
    parser.add_argument("--baseline-visual", action="store_true")
    parser.add_argument("--versions", nargs="*", default=["26.3", "1.21.1"])
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT / "tests/artifacts")
    args = parser.parse_args()
    if args.baseline_visual and not args.motion_only:
        parser.error('--baseline-visual requires --motion-only')
    if args.backend_only and args.versions != ["26.3"]:
        parser.error("The pinned stock-client backend suite targets --versions 26.3")

    zip_path = args.zip
    if zip_path is None:
        cands = sorted(p for p in (ROOT / "dist").glob("Tabletop-Tarot-*.zip") if not p.name.endswith("-resourcepack.zip"))
        if not cands:
            print("No built zip found in dist/; run tools/build.py first.", file=sys.stderr)
            return 2
        zip_path = cands[-1]

    for ver in args.versions:
        run_suite_for_version(ver, zip_path, args.artifacts_dir, args.adversarial_only, args.polish_only, args.backend_only, args.controls_only, args.motion_only, args.baseline_visual, args.guidebook_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
