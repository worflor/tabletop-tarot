"""Read-only Cartomancy import. Verify the complete pinned batch before publishing."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--ref',default='f990fcf610f0a2676e0f29b1231760e08332a167');a=p.parse_args()
 tree=json.loads(subprocess.check_output(['gh','api',f'repos/worflor/cartomancy-private/git/trees/{a.ref}?recursive=1']))
 if tree.get('truncated'):raise ValueError('Truncated remote tree')
 blobs={e['path']:e['sha'] for e in tree['tree'] if e['type']=='blob'};batch=[]
 def collect(source,destination):
  data=(a.source/source).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if blob!=blobs.get(source):raise ValueError('Stale local source: '+source)
  dest=ROOT/destination
  if not dest.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Import destination escaped project')
  batch.append((data,{'source':source,'destination':destination,'git_blob':blob,'sha256':hashlib.sha256(data).hexdigest()}))
 for module,folder,count in [('rider','smith-waite',78),('numbers','numbers',12)]:
  base='src/main/resources/assets/cartomancy/decks/'+folder
  pack=json.loads((a.source/base/'pack.json').read_text(encoding='utf-8'));side=json.loads((a.source/base/'deck.json').read_text(encoding='utf-8'))
  if len(pack['cards'])!=count or len({c['id'] for c in pack['cards']})!=count:raise ValueError('Wrong source deck identity count')
  names=['pack.json','deck.json',side['back']]+[c['id']+'.png' for c in pack['cards']]
  if any(not re.fullmatch(r'[a-z0-9_.-]+',name) or name in {'.','..'} for name in names):raise ValueError('Unsafe source plate name')
  for name in names:collect(base+'/'+name,'modules/'+module+'/'+name)
 for source,destination in [('src/main/resources/assets/cartomancy/models/item/card.json','core/display-source.json'),('src/main/resources/assets/cartomancy/textures/card/edge_vellum.png','core/edge_vellum.png')]:collect(source,destination)
 previous=ROOT/'source-lock.json'
 if previous.exists():
  for entry in json.loads(previous.read_text(encoding='utf-8'))['files']:
   path=ROOT/entry['destination']
   if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Preserve local source edit before reimport: '+str(path))
 # No destination is touched unless all remote identities and existing sources pass.
 for data,entry in batch:
  dest=ROOT/entry['destination'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 receipt={'repository':'worflor/cartomancy-private','verified_ref':a.ref,'files':[entry for _,entry in batch]}
 previous.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 print('Imported and remote-verified',len(batch),'files; no Cartomancy writes')
if __name__=='__main__':main()
