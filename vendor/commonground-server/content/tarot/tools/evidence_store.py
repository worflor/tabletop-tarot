"""Deduplicate receipt bytes while retaining every index and unique archive."""
import argparse,gzip,hashlib,json,os,pathlib,shutil

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):value.update(block)
    return value.hexdigest()

def compact(root):
    root=root.resolve(strict=True)
    def contained(path):
        resolved=path.resolve(strict=True)
        if not resolved.is_relative_to(root):raise ValueError('Archive escapes evidence directory: '+str(path))
        return resolved
    indexes=[]
    # Verify every reference before moving anything. Failures leave the old
    # layout usable. New blobs are copied before indexes are atomically changed.
    for path in sorted(root.rglob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or 'full_receipt' not in data:continue
        ref=data['full_receipt'];archive=contained(path.parent/ref['path'])
        if digest(archive)!=ref['sha256']:raise ValueError('Compressed receipt mismatch: '+str(path))
        h=hashlib.sha256()
        with gzip.open(archive,'rb') as stream:
            for block in iter(lambda:stream.read(65536),b''):h.update(block)
        if h.hexdigest()!=ref['uncompressed_sha256']:raise ValueError('Receipt payload mismatch: '+str(path))
        indexes.append((path,data))
    originals=[contained(p) for p in root.rglob('*.json.gz')]
    blobs=root/'blobs';blobs.mkdir(exist_ok=True)
    mapping={};saved=0;removed=0
    for original in originals:
        key=digest(original);target=blobs/(key+'.json.gz')
        if not target.exists():shutil.copyfile(original,target)
        if digest(target)!=key:raise ValueError('Receipt blob collision')
        mapping[original]=target
    for path,data in indexes:
        ref=data['full_receipt'];original=contained(path.parent/ref['path'])
        ref['path']=pathlib.Path(os.path.relpath(mapping[original],path.parent)).as_posix()
        temporary=path.with_suffix('.json.compact.tmp')
        temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');temporary.replace(path)
    # Re-resolve all published references before retiring duplicate copies.
    for path,_ in indexes:
        ref=json.loads(path.read_text(encoding='utf-8'))['full_receipt']
        if digest(contained(path.parent/ref['path']))!=ref['sha256']:raise ValueError('Published reference mismatch')
    before=sum(p.stat().st_size for p in originals)
    for original,target in mapping.items():
        if original==target:continue
        contained(original);original.unlink();removed+=1
    after=sum(p.stat().st_size for p in blobs.glob('*.json.gz'))
    saved=before-after
    result={'passed':True,'indexes_preserved':len(indexes),'unique_archives':len(set(mapping.values())),'retired_copies':removed,'bytes_saved':saved}
    print(json.dumps(result));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]/'evidence');a=p.parse_args();compact(a.root)
