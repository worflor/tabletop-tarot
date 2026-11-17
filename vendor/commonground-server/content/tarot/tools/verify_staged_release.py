"""Verify a publisher handoff without launching Minecraft or rebuilding the ZIP."""
import argparse,hashlib,json,pathlib,re,zipfile
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[3]

def digest(path,algorithm='sha256'):return hashlib.new(algorithm,path.read_bytes()).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)

def main(version):
    stage=ROOT/'staging/releases/tabletop-tarot'/version
    manifest=json.loads((stage/'release.json').read_text(encoding='utf-8'))
    require(manifest['version_number']==version,'Version folder differs from manifest')
    require(manifest['project']=='Tabletop Tarot' and manifest['version_name']=='Tabletop Tarot '+version,'Release identity')
    require({p.name for p in stage.glob('*.zip')}=={'Tabletop-Tarot-'+version+'.zip'},'Unlisted or incorrectly named release ZIP')
    require(manifest['publication_status']=='staged' and not manifest['publish_automatically'],'Handoff must remain staged')
    require(len(manifest['files'])==1,'Combined release must have one primary ZIP')
    for entry in manifest['files']:
        artifact=(stage/entry['file']).resolve();require(artifact.is_relative_to(stage.resolve()),'Artifact escaped version directory')
        require(artifact.stat().st_size==entry['bytes'],'Artifact length')
        for algorithm,value in entry['hashes'].items():
            require(digest(artifact,algorithm)==value,'Artifact '+algorithm)
            require((stage/(entry['file']+'.'+algorithm)).read_text().strip()==value+'  '+entry['file'],'Checksum sidecar')
        with zipfile.ZipFile(artifact) as archive:
            require(archive.testzip() is None,'ZIP CRC')
            require(all(p in archive.namelist() for p in ['pack.mcmeta','pack.png','INSTALL.txt','CREDITS.txt','LICENSE.md','licenses/MIT.txt','licenses/CC-BY-4.0.txt']),'ZIP presentation/licenses')
            for name in ['pack.png','CREDITS.txt','LICENSE.md','licenses/MIT.txt','licenses/CC-BY-4.0.txt']:require((stage/name).read_bytes()==archive.read(name),'Extracted '+name)
    verification=manifest['verification'];index=(stage/verification['index']).resolve();compatibility=json.loads(index.read_text())
    require(digest(index)==verification['sha256'],'Compatibility index hash')
    proof_path=(stage/verification['packaging_index']).resolve();proof=json.loads(proof_path.read_text())
    require(proof['passed'] and digest(proof_path)==verification['packaging_index_sha256'],'Packaging proof hash')
    require(proof['baseline']['compatibility_index_sha256']==digest(index),'Historical compatibility binding')
    require(proof['baseline']['sha256']==compatibility['combined_archive']['sha256'] and proof['archive_sha256']==manifest['files'][0]['hashes']['sha256'],'Tested effective content binding')
    require(manifest['game_versions']==[t['minecraft'] for t in compatibility['targets']],'Exact supported versions')
    gallery_path=(stage/manifest['gallery']).resolve();gallery=json.loads(gallery_path.read_text())
    require(gallery['version']==version and gallery['provenance']['artifact_sha256']==manifest['files'][0]['hashes']['sha256'],'Gallery artifact binding')
    images=gallery['images'];require(len(images)>0 and sum(i['featured'] for i in images)==1,'Gallery feature')
    require([i['ordering'] for i in images]==list(range(len(images))),'Gallery order')
    require({p.name for p in gallery_path.parent.glob('*.png')}=={i['file'] for i in images},'Unlisted or missing gallery images')
    for image in images:
        path=(gallery_path.parent/image['file']).resolve();require(path.is_relative_to(gallery_path.parent),'Image escaped gallery')
        require(digest(path)==image['sha256'] and path.stat().st_size==image['bytes'],'Image bytes '+image['file'])
        with Image.open(path) as png:
            require(png.format=='PNG' and list(png.size)==image['size']==[1920,1080],'Native image dimensions');png.verify()
        require(image['edited'] is False and image['alt'] and image['description'],'Image description/provenance')
    pages=[stage/'README.md',stage/'LISTING.md',ROOT/'docs/gallery/README.md',gallery_path.parent/'README.md',ROOT/'content/tarot/README.md']
    for page in pages:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',page.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            require((page.parent/target.split('#')[0]).exists(),'Broken link '+str(page)+': '+target)
    result={'passed':True,'version':version,'scope':'Staged ZIP CRC, effective-content packaging proof and historical evidence hashes, extracted icon/credits/licenses, sidecars, exact game versions, gallery PNGs/hashes/dimensions/order and handoff links; does not claim new gameplay tests','artifact_sha256':manifest['files'][0]['hashes']['sha256'],'compatibility_index_sha256':digest(index),'packaging_index_sha256':digest(proof_path),'gallery_manifest_sha256':digest(gallery_path),'photos':len(images),'game_versions':manifest['game_versions']}
    (stage/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',default='1.0.0');main(parser.parse_args().version)
