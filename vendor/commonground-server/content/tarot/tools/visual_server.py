"""Keep one disposable vanilla scene server alive for manual/native client review."""
from pathlib import Path
import json,sys,argparse
import game_lab as lab
parser=argparse.ArgumentParser();parser.add_argument('--version',choices=lab.PROFILES,default='1.21.4');args=parser.parse_args()
base=lab.RUNTIME
lab.RUNTIME=base/('visual-'+args.version);lab.RUNTIME.mkdir(exist_ok=True)
lane=lab.VanillaLane(args.version);lane.server_jar=base/('server-'+args.version+'.jar')
try:
 lane.start();print(json.dumps({'ready':True,'game_port':lane.game_port}),flush=True)
 for line in sys.stdin:
  command=line.strip()
  if command=='stop':break
  try:print(lane.rcon(command),flush=True)
  except Exception as e:print(repr(e),flush=True)
finally:
 lane.stop();(lab.RUNTIME/('visual-commands-'+str(__import__('time').time_ns())+'.json')).write_text(json.dumps(lane.commands,indent=2),encoding='utf-8')
