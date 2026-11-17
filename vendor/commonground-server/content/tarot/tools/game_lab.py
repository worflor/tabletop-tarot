"""Exercise the Tarot datapack on an unmodified official Minecraft server.

The server, disposable world and logs live in the sibling runtime cache. This lane
uses loopback RCON for administration and a real offline protocol player for all
inventory/context interactions. No mods or plugins are installed.
"""
from __future__ import annotations

import hashlib
import gzip
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from receipt_binding import summarize_checks
from profiles import PROFILES, profile
from lab_environment import java_runtime,reserve_port

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("TAROT_PROJECT_ROOT",str(HERE.parents[2])))
CACHE_ROOT = ROOT.parent / "commonground-microvoxels-runtime"
RUNTIME = CACHE_ROOT / "tarot"
RECEIPT = ROOT / "content" / "tarot" / "evidence" / "game-1.21.4.json"
MANIFEST_URL = "https://piston-meta.mojang.com/v1/packages/ee8ab0f6ec89b3127436d35e36aa766c1e85c3a9/1.21.4.json"
MANIFEST_SHA1 = "ee8ab0f6ec89b3127436d35e36aa766c1e85c3a9"
VERSION_INDEX_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
NODE_CLIENTS = Path(os.environ.get("TAROT_NODE_CLIENTS",str(RUNTIME / "protocol-clients")))
NODE = shutil.which("node")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def port() -> int:
    return reserve_port(RUNTIME)


def packet(rid: int, kind: int, value: str) -> bytes:
    body = struct.pack("<ii", rid, kind) + value.encode() + b"\0\0"
    return struct.pack("<i", len(body)) + body


def receive(sock: socket.socket):
    def exact(n):
        out = b""
        while len(out) < n:
            part = sock.recv(n - len(out))
            if not part:
                raise ConnectionError("RCON closed mid-packet")
            out += part
        return out
    size, = struct.unpack("<i", exact(4))
    if not 10 <= size <= 1_048_576:
        raise ValueError(f"invalid RCON packet length {size}")
    data = exact(size)
    if data[-2:] != b"\0\0":
        raise ValueError("invalid RCON terminator")
    return (*struct.unpack("<ii", data[:8]), data[8:-2].decode("utf-8"))


class VanillaLane:
    def __init__(self, version="1.21.4"):
        if version not in PROFILES:
            raise ValueError(f"unsupported lab version: {version}")
        self.version = version
        self.java = java_runtime(profile(version)['java'])
        self.pack = ROOT / "content" / "tarot" / "build" / f"java-{version}" / "datapack"
        self.server_dir = RUNTIME / f"server-{version}"
        self.game_port, self.rcon_port = port(), port()
        while self.rcon_port == self.game_port:
            self.rcon_port = port()
        self.password = secrets.token_hex(20)
        self.world_name = "tarot-world-" + str(time.time_ns())
        self.world_dir = self.server_dir / self.world_name
        self.process = None
        self.log = None
        self.starts = []
        self.commands = []
        self.client_process = None
        self.client_lines = []
        self.client_events = []
        self.client_lock = threading.Lock()
        self.client_ready = threading.Event()

    def remove_staged_pack(self, staged: Path):
        runtime = RUNTIME.resolve()
        server_root = self.server_dir.resolve()
        resolved = staged.resolve()
        if not server_root.is_relative_to(runtime):
            raise ValueError(f"server directory escaped runtime root: {server_root}")
        if not resolved.is_relative_to(server_root):
            raise ValueError(f"datapack staging directory escaped owned server: {resolved}")
        if resolved != (self.world_dir / "datapacks" / "tarot").resolve():
            raise ValueError(f"unexpected staged datapack path: {resolved}")
        if resolved.exists():
            shutil.rmtree(resolved)

    def download_server(self):
        RUNTIME.mkdir(parents=True, exist_ok=True)
        spec=profile(self.version)
        manifest_url, manifest_sha1=spec['manifest_url'],spec['manifest_sha1']
        manifest_path = RUNTIME / f"{self.version}.json"
        if not manifest_path.exists() or hashlib.sha1(manifest_path.read_bytes()).hexdigest() != manifest_sha1:
            data = urllib.request.urlopen(manifest_url, timeout=40).read()
            if hashlib.sha1(data).hexdigest() != manifest_sha1:
                raise ValueError(f"official {self.version} version metadata SHA-1 mismatch")
            manifest_path.write_bytes(data)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact = manifest["downloads"]["server"]
        jar = RUNTIME / f"server-{self.version}.jar"
        if not jar.exists() or hashlib.sha1(jar.read_bytes()).hexdigest() != artifact["sha1"]:
            data = urllib.request.urlopen(artifact["url"], timeout=90).read()
            if hashlib.sha1(data).hexdigest() != artifact["sha1"]:
                raise ValueError("official server jar SHA-1 mismatch")
            jar.write_bytes(data)
        self.server_jar_sha256 = sha(jar)
        self.manifest_url = manifest_url
        self.manifest_sha1 = manifest_sha1
        self.server_url = artifact["url"]
        self.server_sha1 = artifact["sha1"]
        self.server_jar = jar

    def rcon(self, command: str) -> str:
        with socket.create_connection(("127.0.0.1", self.rcon_port), timeout=60 if command=='reload' else 15) as sock:
            sock.sendall(packet(1, 3, self.password))
            rid, _, _ = receive(sock)
            if rid == -1:
                raise PermissionError("RCON auth failed")
            sock.sendall(packet(2, 2, command))
            rid, _, response = receive(sock)
            if rid != 2:
                raise ValueError(f"unexpected RCON response id {rid}")
            if command!='stop':
                sock.sendall(packet(3,2,'list'))
                parts=[response]
                while True:
                    packet_id,_,part=receive(sock)
                    if packet_id==3:break
                    if packet_id!=2:raise ValueError('Unexpected RCON continuation')
                    parts.append(part)
                response=''.join(parts)
            self.commands.append({"via": "rcon", "command": command, "response": response})
            return response

    def start(self):
        if not self.pack.is_dir():
            raise FileNotFoundError(f"generated datapack not found: {self.pack}")
        if not self.java.is_file():
            raise FileNotFoundError(f"Java runtime not found: {self.java}")
        self.server_dir.mkdir(parents=True, exist_ok=True)
        (self.server_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        world = self.world_dir
        (world / "datapacks").mkdir(parents=True, exist_ok=True)
        staged = world / "datapacks" / "tarot"
        self.remove_staged_pack(staged)
        self.stage_pack(staged)
        props = {
            "server-ip": "127.0.0.1", "server-port": self.game_port,
            "enable-rcon": "true", "rcon.port": self.rcon_port, "rcon.password": self.password,
            "broadcast-rcon-to-ops": "false", "online-mode": "false", "enforce-secure-profile": "false",
            "white-list":"false","enforce-whitelist":"false",
            "level-name": self.world_name, "level-seed": "4738291",
            "level-type":"minecraft:flat",
            "generator-settings":json.dumps({"layers":[{"height":1,"block":"minecraft:bedrock"},{"height":2,"block":"minecraft:dirt"},{"height":1,"block":"minecraft:grass_block"}],"biome":"minecraft:plains"}),
            "generate-structures": "false", "view-distance": 3, "simulation-distance": 3,
            "spawn-protection": 0, "max-players": 20, "difficulty": "peaceful",
            "allow-nether": "false", "enable-query": "false", "enable-status": "false",
            "motd": "Disposable Tarot vanilla lab", "sync-chunk-writes": "false",
        }
        props.update(getattr(self,'property_overrides',{}))
        (self.server_dir / "server.properties").write_text("".join(f"{k}={v}\n" for k, v in props.items()), encoding="utf-8")
        log_path = RUNTIME / f"server-{self.version}-{time.time_ns()}.log"
        self.log = log_path.open("wb")
        command = [str(self.java), "-Xms256M", "-Xmx"+getattr(self,'server_heap','1536M'), "-XX:ActiveProcessorCount=4", "-jar", str(self.server_jar), "--nogui"]
        self.process = subprocess.Popen(command, cwd=self.server_dir, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        self.starts.append({"pid": self.process.pid, "command": command, "cwd": str(self.server_dir), "log": str(log_path)})
        print(f"Started owned vanilla {self.version} PID {self.process.pid}; game port {self.game_port}; log {log_path}", flush=True)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"server exited {self.process.returncode}; see {log_path}")
            if log_path.exists() and "Done (" in log_path.read_text(encoding="utf-8", errors="replace"):
                self.rcon("list")
                self.check_log(log_path.read_text(encoding="utf-8",errors="replace"))
                return
            time.sleep(1)
        raise TimeoutError(f"server startup timeout; see {log_path}")

    def stage_pack(self,staged):
        shutil.copytree(self.pack,staged)

    def check_log(self,text):
        bad=[l for l in text.splitlines() if any(s in l for s in ["Couldn't load","Failed to load","Couldn't parse","Failed to parse","Unknown or incomplete command"])]
        if bad:raise RuntimeError('Datapack engine errors: '+' | '.join(l[:300] for l in bad[:6]))

    def refresh_pack(self):
        """Copy a newly generated datapack into the world and run real /reload."""
        staged = self.world_dir / "datapacks" / "tarot"
        self.remove_staged_pack(staged)
        self.stage_pack(staged)
        response = self.rcon("reload")
        time.sleep(1)
        log = next((Path(row["log"]) for row in self.starts), None)
        tail = log.read_text(encoding="utf-8", errors="replace")[-16000:] if log and log.exists() else ""
        self.commands.append({"via": "harness", "action": "reload", "response": response,
                              "recent_log": tail[-5000:]})
        bad = [line for line in tail.splitlines() if "Couldn't load" in line or "Failed to load" in line
               or "Couldn't parse" in line or "Unknown or incomplete command" in line]
        if bad:
            raise RuntimeError("datapack reload reported errors: " + " | ".join(bad[-10:]))
        return {"response": response, "errors": bad}

    def start_player(self, name="TarotLab"):
        if not NODE:
            raise FileNotFoundError("node executable not found")
        if not (NODE_CLIENTS / "node_modules" / "mineflayer").exists():
            raise FileNotFoundError("Protocol observer is missing. Run python -B content/tarot/tools/bootstrap_lab.py")
        self.player_name=name
        self.client_ready.clear()
        js = self.server_dir / "tarot-player.cjs"
        js.write_text(PLAYER_CLIENT, encoding="utf-8")
        node_env = os.environ.copy()
        node_env["NODE_PATH"] = str(NODE_CLIENTS / "node_modules")
        self.client_process = subprocess.Popen([NODE, str(js), str(self.game_port), name, self.version], cwd=NODE_CLIENTS, env=node_env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", bufsize=1)
        def reader():
            for line in self.client_process.stdout:
                line = line.rstrip()
                self.client_lines.append(line)
                try:
                    event = json.loads(line)
                    with self.client_lock:
                        self.client_events.append(event)
                    if event.get("ready"):
                        self.client_ready.set()
                except ValueError:
                    pass
        threading.Thread(target=reader, daemon=True).start()
        deadline = time.monotonic() + 90
        while not self.client_ready.wait(.2):
            if self.client_process.poll() is not None:
                raise RuntimeError(f"protocol player exited {self.client_process.returncode}: {self.client_lines[-20:]}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"protocol player did not spawn; output: {self.client_lines[-20:]}")
        self.rcon(f"op {name}")
        self.rcon(f"gamemode creative {name}")
        self.client_action("snapshot")

    def client_action(self, verb, timeout=20, **args):
        if not self.client_process or self.client_process.poll() is not None:
            raise RuntimeError("protocol player process is not running")
        before = len(self.client_events)
        payload = json.dumps({"verb": verb, **args})
        self.client_process.stdin.write(payload + "\n")
        self.client_process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.client_lock:
                recent = self.client_events[before:]
            for event in recent:
                if event.get("action") == verb and "result" in event:
                    self.commands.append({"via": "protocol-player", "action": verb, **event["result"]})
                    result=event["result"]
                    if verb=="chat" and args.get("text","").startswith("/trigger "):
                        until=time.monotonic()+10
                        while True:
                            score=self.rcon(f"scoreboard players get {self.player_name} tarot.action")
                            if "has 0 " in score:break
                            if time.monotonic()>until:raise TimeoutError('Server did not consume trigger')
                            time.sleep(.05)
                        result['snapshot']=self.client_action('snapshot')
                    return result
                if event.get("error"):
                    raise RuntimeError(event)
            time.sleep(.05)
        raise TimeoutError(f"protocol action timed out: {verb}")

    def wait_state(self,predicate,label,timeout=10):
        deadline=time.monotonic()+timeout
        while True:
            state=self.client_action('snapshot')
            if predicate(state):return state
            if time.monotonic()>deadline:raise TimeoutError('Waiting for server inventory: '+label)
            time.sleep(.05)

    def player_function(self, function):
        result = self.client_action("function", function=function)
        time.sleep(.35)
        return result

    def stop(self):
        if self.client_process is not None:
            try:
                if self.client_process.poll() is None:
                    self.client_process.stdin.write('{"verb":"quit"}\n')
                    self.client_process.stdin.flush()
                    self.client_process.wait(timeout=10)
            except Exception:
                if self.client_process.poll() is None:
                    self.client_process.kill()
                    self.client_process.wait(timeout=10)
        if self.process is not None and self.process.poll() is None:
            try:
                self.rcon("stop")
            except Exception:
                pass
            try:
                self.process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log:
            self.log.close()


PLAYER_CLIENT = r'''const mineflayer=require('mineflayer'); const readline=require('readline');
// Observer-only repair: 1.21.3 sends integer CMD; the pinned dataset incorrectly
// describes 1.21.4's floats/flags structure and otherwise drops entire slot packets.
if(process.argv[4]==='1.21.3'){const types=require('minecraft-data')('1.21.3').protocol.types;types.SlotComponent[1].find(f=>f.name==='data').type[1].fields.custom_model_data='varint';}
const bot=mineflayer.createBot({host:'127.0.0.1',port:Number(process.argv[2]),username:process.argv[3],version:process.argv[4],auth:'offline'});
const observedEntities=new Map();const send=x=>process.stdout.write(JSON.stringify(x)+'\n'); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
bot.on('message',(m,position)=>send({feedback:JSON.stringify(m.json||m),position}));
bot.on('actionBar',m=>send({actionbar:JSON.stringify(m.json||m)}));
bot.on('error',e=>send({error:String(e)})); bot.on('kicked',r=>send({error:'kicked',reason:r}));
bot.once('spawn',async()=>{await bot.waitForChunksToLoad();await waitTicks(4);send({ready:true}); const rl=readline.createInterface({input:process.stdin}); let q=Promise.resolve(); rl.on('line',line=>{q=q.then(async()=>{const a=JSON.parse(line);try{let result;
if(a.verb==='snapshot'){await waitTicks(2); result=snapshot();}
else if(a.verb==='chat'){if(a.text.startsWith('/trigger ')){await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{bot.removeListener('message',listener);reject(Error('No trigger acknowledgement'));},10000);const listener=m=>{const raw=JSON.stringify(m.json||m);if(raw.includes('commands.trigger')){clearTimeout(timer);bot.removeListener('message',listener);if(raw.includes('failed')||raw.includes('invalid'))reject(Error(raw));else resolve();}};bot.on('message',listener);bot.chat(a.text);});}else bot.chat(a.text);await waitTicks(4);result={chat:a.text,snapshot:snapshot()};}
else if(a.verb==='function'){bot.chat('/function '+a.function);await waitTicks(5);result={function:a.function,snapshot:snapshot()};}
else if(a.verb==='clear'){await confirmedCommand('/clear','commands.clear.');const until=Date.now()+10000;while(bot.inventory.items().length){if(Date.now()>until)throw Error('Server-confirmed clear did not reach inventory');await waitTicks(2);}result=snapshot();}
else if(a.verb==='equip'){const item=bot.inventory.slots[Number(a.slot)];if(!item)throw Error('No item to equip');await bot.equip(item,'hand');await waitTicks(3);result=snapshot();}
else if(a.verb==='hold'){bot.setQuickBarSlot(Number(a.slot));await waitTicks(a.wait_ticks??2);result=snapshot();}
else if(a.verb==='raw_use'){bot.activateItem(Boolean(a.offhand));await waitTicks(a.wait_ticks??3);bot.deactivateItem();result=snapshot();}
else if(a.verb==='mount_state'){result={vehicle:bot.vehicle?.name||bot.entity?.vehicle?.name||null};}
else if(a.verb==='drop'){const item=bot.inventory.slots[Number(a.slot??(36+bot.quickBarSlot))];if(!item)throw Error('No item to drop');await bot.tossStack(item);await waitTicks(3);result=snapshot();}
else if(a.verb==='use'){const before=JSON.stringify(norm(bot.heldItem));bot.activateItem();const deadline=Date.now()+10000;while(JSON.stringify(norm(bot.heldItem))===before&&Date.now()<deadline)await waitTicks(2);bot.deactivateItem();result={sneakControl:bot.getControlState('sneak'),inventoryUpdateObserved:JSON.stringify(norm(bot.heldItem))!==before,snapshot:snapshot()};}
else if(a.verb==='sneak'){const enabled=Boolean(a.enabled);bot.setControlState('sneak',enabled);const nativeTypes=require('minecraft-data')(bot.version).protocol.play.toServer.types;const actions=nativeTypes.packet_entity_action[1].find(f=>f.name==='actionId').type[1].mappings;if(Object.values(actions).includes('start_sneaking'))bot._client.write('entity_action',{entityId:bot.entity.id,actionId:enabled?'start_sneaking':'stop_sneaking',jumpBoost:0});if(nativeTypes.packet_player_input){bot._client.write('player_input',{inputs:{forward:bot.getControlState('forward'),backward:bot.getControlState('back'),left:bot.getControlState('left'),right:bot.getControlState('right'),jump:bot.getControlState('jump'),shift:enabled,sprint:bot.getControlState('sprint')}});}await waitTicks(5);result={enabled,sneakControl:bot.getControlState('sneak'),snapshot:snapshot()};}
else if(a.verb==='offhand'){const Item=require('prismarine-item')(bot.version);bot.creative.setInventorySlot(45,bot.inventory.slots[Number(a.slot)]);bot.creative.setInventorySlot(Number(a.slot),null);await waitTicks(3);result=snapshot();}
else if(a.verb==='craft_deck'){const table=await observedCraftingTable(a);const Recipe=require('prismarine-recipe')(bot.registry).Recipe;const paper=bot.registry.itemsByName.paper.id;const ink=bot.registry.itemsByName[a.ingredient].id;const recipe=new Recipe({inShape:[[paper,paper,paper],[paper,ink,paper],[paper,paper,paper]],result:{id:bot.registry.itemsByName.carrot_on_a_stick.id,count:1}});await bot.craft(recipe,1,table);await waitTicks(4);result=snapshot();}
else if(a.verb==='craft_probe'){const table=await observedCraftingTable(a);const opened=new Promise(resolve=>bot.once('windowOpen',resolve));await bot.activateBlock(table);const win=await opened;try{const names=a.repair_slots?['carrot_on_a_stick','carrot_on_a_stick']:(a.card?['carrot_on_a_stick','paper','paper','leather']:['paper','paper','paper','leather']);for(let i=0;i<names.length;i++){const from=a.repair_slots?a.repair_slots[i]:a.card_slot;const src=names[i]==='carrot_on_a_stick'?win.inventoryStart+(from>=36?27+from-36:from-9):win.slots.findIndex((x,s)=>s>=win.inventoryStart&&x&&x.name===names[i]);if(src<0)throw Error('Missing crafting input '+names[i]);await bot.clickWindow(src,0,0);await bot.clickWindow(i+1,1,0);if(win.selectedItem)await bot.clickWindow(src,0,0);}await waitTicks(5);result={output:norm(win.slots[0]),inputs:win.slots.slice(1,10).map(norm)};}finally{await bot.closeWindow(win);await waitTicks(4);}}
else if(a.verb==='use_offhand'){bot.activateItem(true);await waitTicks(6);bot.deactivateItem();result=snapshot();}
else if(a.verb==='entities'){for(const e of Object.values(bot.entities)){observedEntities.set(String(e.id),e);if(e.uuid)observedEntities.set(e.uuid,e);}result={entities:Object.values(bot.entities).map(e=>({id:e.id,uuid:e.uuid,name:e.name,position:e.position}))};}
else if(a.verb==='touch'){const e=Object.values(bot.entities).find(e=>a.uuid?e.uuid===a.uuid:e.id===a.id)||observedEntities.get(a.uuid||String(a.id));if(!e)throw Error('Target entity not observed');await bot.lookAt(e.position.offset(0,.04,0),true);if(a.attack&&require('minecraft-data')(bot.version).protocol.play.toServer.types.packet_attack)bot._client.write('attack',{entityId:e.id});else bot._client.write('use_entity',{target:e.id,mouse:a.attack?1:0,hand:bot.version==='26.1.2'?'main_hand':0,location:{x:0,y:.04,z:0},x:0,y:.04,z:0,sneaking:bot.getControlState('sneak')});bot.swingArm();await waitTicks(6);result=snapshot();}
else if(a.verb==='look'){await bot.look(Number(a.yaw)*Math.PI/180,Number(a.pitch)*Math.PI/180,true);await waitTicks(2);result=snapshot();}
else if(a.verb==='quit'){bot.quit();result={quit:true};setTimeout(()=>process.exit(0),250);}
else throw new Error('unknown verb '+a.verb); send({action:a.verb,result});}catch(e){send({error:String(e),action:a.verb})}}).catch(e=>send({error:String(e)}))}); });
async function waitTicks(n){if(bot.vehicle||bot.entity?.vehicle)await sleep(n*50);else await bot.waitForTicks(n);}
function norm(item){if(!item)return null;const components=Array.isArray(item.components)?Object.fromEntries(item.components.map(c=>[String(c.type),c.data])):null;return {name:item.name,count:item.count,slot:item.slot,components,nbt:item.nbt??null,displayName:item.displayName};}
function snapshot(){const p=bot.entity.position;return {username:bot.username,held:norm(bot.heldItem),offhand:norm(bot.inventory.slots[45]),items:bot.inventory.slots.map((x,i)=>x?{...norm(x),slot:i}:null).filter(Boolean),position:{x:p.x,y:p.y,z:p.z}};}
async function observedCraftingTable(a){const Vec3=require('vec3').Vec3;const until=Date.now()+10000;while(Date.now()<until){const block=bot.blockAt(new Vec3(a.x,a.y,a.z));if(block?.name==='crafting_table')return block;await waitTicks(2);}throw Error('Crafting table update did not reach client');}
async function confirmedCommand(command,prefix){await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{bot.removeListener('message',listener);reject(Error('No server acknowledgement for '+command));},10000);const listener=m=>{if(JSON.stringify(m.json||m).includes(prefix)){clearTimeout(timer);bot.removeListener('message',listener);resolve();}};bot.on('message',listener);bot.chat(command);});}
'''


def write_json(path: Path, data):
    """Keep complete receipts losslessly, with a small readable index."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        prior=json.loads(path.read_text(encoding="utf-8"))
        tag=str(time.time_ns())
        history=path.parent/'history';history.mkdir(exist_ok=True)
        if 'full_receipt' in prior:
            original=path.parent/prior['full_receipt']['path']
            if not original.exists():raise ValueError('Previous receipt archive missing')
            prior['full_receipt']['path']=Path(os.path.relpath(original,history)).as_posix()
        (history/(path.stem+'-'+tag+'.json')).write_text(json.dumps(prior,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    # Full inventory receipts can be large. Stream the exact same JSON bytes
    # through gzip instead of allocating a second JSON string and UTF-8 copy.
    payload_hash=hashlib.sha256();archive_temp=path.with_name('.'+path.stem+'-receipt-'+secrets.token_hex(6)+'.tmp')
    with archive_temp.open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:
            chunks=[];length=0
            for chunk in json.JSONEncoder(indent=2,ensure_ascii=False).iterencode(data):
                chunks.append(chunk);length+=len(chunk)
                if length>=65536:
                    encoded=''.join(chunks).encode('utf-8');payload_hash.update(encoded);compressed.write(encoded);chunks=[];length=0
            encoded=(''.join(chunks)+'\n').encode('utf-8');payload_hash.update(encoded);compressed.write(encoded)
    compressed_hash=hashlib.sha256(archive_temp.read_bytes()).hexdigest()
    # Include the compressed digest so an identical payload using a different
    # gzip implementation cannot overwrite an older receipt's referenced bytes.
    blobs=path.parent/'blobs';blobs.mkdir(exist_ok=True)
    archive=blobs/(compressed_hash+'.json.gz')
    if archive.exists():
        if sha(archive)!=compressed_hash:raise ValueError('Receipt blob collision')
        archive_temp.unlink()
    else:archive_temp.replace(archive)
    summary = {k:v for k,v in data.items() if k not in {"commands", "protocol_lines", "start", "checks"}}
    if 'checks' in data:summary["checks"] = summarize_checks(data['checks'])
    summary["full_receipt"] = {"path":archive.relative_to(path.parent).as_posix(),"sha256":compressed_hash,"uncompressed_sha256":payload_hash.hexdigest(),"commands":len(data.get("commands",[])),"protocol_events":len(data.get("protocol_lines",[]))}
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    temp.replace(path)


def unwrap_nbt(value):
    if isinstance(value, dict):
        if set(value.keys()) == {"type", "value"}:
            return unwrap_nbt(value["value"])
        return {k: unwrap_nbt(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap_nbt(v) for v in value]
    return value


def tarot_data(item):
    """Read this item's own marker, never a nested card's marker."""
    if not item:
        return None
    value=unwrap_nbt(item);components=value.get('components') or {}
    if isinstance(components,list):components={str(c['type']):c.get('data') for c in components}
    own=components.get('minecraft:custom_data',components.get('custom_data',{}))
    if isinstance(own,dict) and isinstance(own.get('tarot'),dict):return own['tarot']
    legacy=value.get('nbt') or {}
    if isinstance(legacy,dict) and isinstance(legacy.get('tarot'),dict):return legacy['tarot']
    return None

def native_items(deck):
    if not deck:return []
    components=deck.get('components') or {}
    if isinstance(components,list):components={str(c['type']):c.get('data') for c in components}
    value=components.get('charged_projectiles',components.get('minecraft:charged_projectiles',[]))
    return value.get('projectiles',[]) if isinstance(value,dict) else value


def deck_item(snapshot, module="rider"):
    for item in snapshot.get("items", []):
        data = tarot_data(item)
        if data and data.get("kind") == "deck" and data.get("module") == module:
            return item
    return None


def card_items(snapshot, module=None):
    found = []
    for item in snapshot.get("items", []):
        data = tarot_data(item)
        if data and data.get("kind") == "card" and (module is None or data.get("module") == module):
            found.append((item, data))
    return found


def card_keys(deck):
    data = tarot_data(deck) if deck else None
    if data and data.get('storage') in {1,'native-v1'}:return [(tarot_data(item) or {}).get('key') for item in native_items(deck)]
    cards = data.get("cards", []) if data else []
    return [c.get("key") if isinstance(c, dict) else c for c in cards]


def run_scenarios(lane):
    checks = []
    def record(name, details):
        checks.append({"name": name, "passed": True, **details})
    lane.rcon("clear TarotLab")
    lane.client_action("chat", text="/function tarot:give/rider")
    initial = lane.wait_state(lambda s:deck_item(s) is not None,"initial Rider deck")
    deck = deck_item(initial)
    if not deck:
        raise AssertionError("Rider deck missing after player-context give function")
    original = card_keys(deck)
    if len(original) != 78 or len(set(original)) != 78:
        raise AssertionError(f"Rider identity count/uniqueness failed: count={len(original)}, unique={len(set(original))}")
    record("rider_deck_identity", {"count": len(original), "unique": len(set(original)), "sample": original[:4]})

    lane.client_action("hold", slot=(deck["slot"] - 36) if deck["slot"] >= 36 else deck["slot"])
    lane.client_action("use")
    time.sleep(.25)
    after_draw = lane.client_action("snapshot")
    after_deck = deck_item(after_draw)
    drawn = card_items(after_draw, "rider")
    if not after_deck or len(card_keys(after_deck)) != 77 or len(drawn) != 1:
        raise AssertionError(f"right-click draw did not conserve count: deck={len(card_keys(after_deck)) if after_deck else None}, cards={len(drawn)}")
    key = drawn[0][1].get("key")
    if key not in original or key in card_keys(after_deck):
        raise AssertionError(f"drawn identity missing from/or still in deck: {key}")
    record("right_click_draw_copy_custom_data", {"drawn_key": key, "remaining": len(card_keys(after_deck)),
           "physical_card": drawn[0][0], "updated_deck": after_deck})

    lane.client_action("sneak", enabled=True)
    lane.rcon("scoreboard players set #sneak_probe tarot.sys 0")
    lane.rcon('execute as TarotLab if predicate tarot:is_sneaking run scoreboard players set #sneak_probe tarot.sys 1')
    sneak_probe=lane.rcon("scoreboard players get #sneak_probe tarot.sys")
    shuffled=lane.client_action("snapshot")
    if 'has 1 ' in sneak_probe:
        changed=False
        for _ in range(3):
            lane.client_action("use");shuffled=lane.client_action("snapshot")
            keys=card_keys(deck_item(shuffled))
            if len(keys)!=77 or set(keys)!=set(original)-{key}:raise AssertionError('Physical shuffle changed membership')
            if keys!=card_keys(after_deck):changed=True;break
        if not changed:raise AssertionError('Physical shuffle produced no observable permutation in three attempts')
        record('sneak_right_click_shuffle',{'server_sneak':True,'permutation_changed':True,'remaining':77})
    else:
        checks.append({'name':'sneak_right_click_shuffle','status':'inconclusive_mineflayer_input','sneak_predicate_probe':sneak_probe,'note':'No shuffle claim from an input the server did not receive'})
    lane.client_action("sneak",enabled=False)
    before_keys=card_keys(deck_item(shuffled));changed=False
    for _ in range(3):
        lane.client_action("chat",text="/trigger tarot.action set 2");trigger_shuffle=lane.client_action("snapshot")
        trigger_keys=card_keys(deck_item(trigger_shuffle))
        if len(trigger_keys)!=77 or set(trigger_keys)!=set(before_keys):raise AssertionError('Trigger shuffle changed membership')
        if trigger_keys!=before_keys:changed=True;break
    if not changed:raise AssertionError('Trigger shuffle was a no-op in three attempts')
    drawn_keys={d.get('key') for _,d in card_items(trigger_shuffle,'rider')};expected_after_shuffle=len(original)-len(drawn_keys)
    record('trigger_shuffle_membership',{'count':len(trigger_keys),'membership_matches':True,'permutation_changed':True})

    lane.client_action("chat", text="/trigger tarot.action set 1")
    triggered = lane.client_action("snapshot")
    tdeck = deck_item(triggered)
    tcards = card_items(triggered, "rider")
    if not tdeck or len(card_keys(tdeck)) != expected_after_shuffle - 1 or len(tcards) != len(drawn_keys) + 1:
        raise AssertionError("trigger draw entrypoint did not conserve card count")
    record("trigger_draw", {"remaining": len(card_keys(tdeck)), "physical_cards": [d.get("key") for _, d in tcards]})

    lane.client_action("clear")
    lane.client_action("chat", text="/function tarot:give/rider")
    prefull = lane.wait_state(lambda s:deck_item(s) is not None and len(card_keys(deck_item(s)))==78 and not card_items(s) and len(s.get('items',[]))==1,"fresh complete deck before full-inventory fixture")
    fdeck = deck_item(prefull)
    # Fill every actual storage/hotbar slot except the mainhand deck using
    # native server commands, avoiding synthetic inventory packet ordering.
    for slot in range(0, 27):
        lane.rcon(f"item replace entity TarotLab inventory.{slot} with minecraft:dirt 64")
    for slot in range(1, 9):
        lane.rcon(f"item replace entity TarotLab hotbar.{slot} with minecraft:dirt 64")
    lane.client_action("chat", text="/trigger tarot.action set 1")
    full = lane.client_action("snapshot")
    after_full = deck_item(full)
    if not fdeck or not after_full or card_keys(after_full) != card_keys(fdeck) or card_items(full):
        raise AssertionError("full-inventory draw changed deck or emitted card")
    record("full_inventory_rejection", {"deck_count": len(card_keys(after_full)), "cards_given": 0})

    lane.client_action("clear")
    lane.client_action("chat", text="/function tarot:give/rider")
    lane.client_action("use")
    time.sleep(.25)
    saved = lane.client_action("snapshot")
    sdeck = deck_item(saved)
    scards = card_items(saved, "rider")
    if not sdeck or len(card_keys(sdeck)) != 77 or len(scards) != 1:
        raise AssertionError("restart persistence setup draw did not work")
    saved_key = scards[0][1].get("key")
    lane.client_action("quit")
    lane.client_process.wait(timeout=10)
    lane.client_process = None
    lane.stop()
    lane.process = None
    lane.log = None
    lane.start()
    lane.start_player()
    restored = lane.client_action("snapshot")
    rdeck = deck_item(restored)
    rcards = card_items(restored, "rider")
    if not rdeck or len(card_keys(rdeck)) != 77 or len(rcards) != 1 or rcards[0][1].get("key") != saved_key:
        raise AssertionError("player inventory custom data did not survive graceful vanilla restart")
    record("restart_persistence", {"remaining": len(card_keys(rdeck)), "drawn_key": saved_key,
           "restored_deck": rdeck, "restored_card": rcards[0][0]})
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=tuple(PROFILES), default="1.21.4")
    parser.add_argument("--keep-alive", action="store_true")
    args = parser.parse_args()
    lane = VanillaLane(args.version)
    receipt = ROOT / "content" / "tarot" / "evidence" / f"game-{args.version}.json"
    evidence = {"minecraft": args.version, "server_type": "official vanilla server", "mods": [], "plugins": [],
                "world_and_logs": str(RUNTIME), "datapack": str(lane.pack), "protocol_player": f"Mineflayer offline {args.version}","harness_sha256":os.environ.get("TAROT_HARNESS_SHA256","working_tree")}
    try:
        if not lane.pack.is_dir():
            raise FileNotFoundError(f"datapack build is not ready: {lane.pack}")
        lane.download_server()
        evidence["official_server"] = {"manifest_url": lane.manifest_url, "server_url": lane.server_url,
            "manifest_sha1": lane.manifest_sha1, "server_sha1": lane.server_sha1, "server_sha256": lane.server_jar_sha256}
        if hasattr(lane, "version_index_sha256"):
            evidence["official_server"]["version_index_sha256"] = lane.version_index_sha256
            evidence["official_server"]["version_index_url"] = VERSION_INDEX_URL
        evidence["datapack_sha256"] = {p.relative_to(lane.pack).as_posix(): sha(p) for p in sorted(lane.pack.rglob("*")) if p.is_file()}
        evidence["java"] = str(lane.java)
        evidence["protocol_observer_patches"]=(['1.21.3 integer custom_model_data wire decoder'] if args.version=='1.21.3' else [])+(['Explicit native PlayerInput shift flags; pinned Mineflayer uses obsolete entity_action sneak below1.21.6'] if args.version in {'1.21.3','1.21.4','1.21.5'} else [])+['Native interaction secondary-action flag; pinned activateEntity forces sneaking=false']
        evidence["protocol_dependencies_sha256"]=sha(NODE_CLIENTS/"package-lock.json")
        lane.start()
        lane.start_player()
        evidence["start"] = {"rcon": lane.rcon("datapack list"), "player": lane.client_action("snapshot")}
        evidence["reload"] = lane.refresh_pack()
        evidence["checks"] = run_scenarios(lane)
        from deck_scenarios import run_extra
        evidence["checks"].extend(run_extra(lane))
        from hardening_scenarios import run_hardening
        evidence["checks"].extend(run_hardening(lane))
        from multiplayer_scenarios import run_multiplayer
        evidence["checks"].extend(run_multiplayer(lane))
        from customization_scenarios import run_customizations
        evidence["checks"].extend(run_customizations(lane))
        from physical_lab import run_physical
        run_physical(lane,evidence["checks"])
        evidence["passed"] = not any(c.get("passed") is False for c in evidence["checks"])
        if not evidence["passed"]:
            raise AssertionError("one or more real-game checks failed")
        if args.keep_alive:
            print(f"LIVE vanilla {args.version} server: 127.0.0.1:{lane.game_port}; protocol player TarotLab; enter q to stop", flush=True)
            while input().strip().lower() != "q":
                pass
        evidence["commands"] = lane.commands
        evidence["processes"] = lane.starts
    except Exception as e:
        evidence["passed"] = False
        evidence["error"] = repr(e)
        if lane.process and lane.process.poll() is None:
            evidence['failure_state']={}
            for command in ['scoreboard players get #budget tarot.sys','scoreboard players get #permit tarot.sys','scoreboard players get #valid tarot.sys','scoreboard players get TarotLab tarot.cool','scoreboard players get TarotLab tarot.use','scoreboard players get TarotLab tarot.action','scoreboard players get TarotLab tarot.pending','data get entity TarotLab SelectedItem']:
                try:evidence['failure_state'][command]=lane.rcon(command)
                except Exception as error:evidence['failure_state'][command]=repr(error)
        raise
    finally:
        lane.stop()
        evidence["commands"] = lane.commands
        evidence["protocol_lines"] = lane.client_lines
        evidence["processes"] = lane.starts
        write_json(receipt, evidence)


if __name__ == "__main__":
    main()
