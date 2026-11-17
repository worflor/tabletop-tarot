"""Stage the exact verified artifact and curated native photos; never publish."""
import hashlib,json,pathlib,shutil,zipfile
from PIL import Image
from game_lab import ROOT,RUNTIME

VERSION='1.0.0'
SUMMARY='78+ illustrated cards to shuffle, draw, trade and lay on your own tables. You decide what they mean.'
NAMES=['01-a-place-at-the-table','08-afternoon-in-the-garden','12-down-by-the-water','06-every-card-an-object','07-rain-check','02-little-paper-worlds','03-sea-air','04-one-more-before-sunset','05-by-the-open-window','09-something-to-share','10-small-things','11-stay-a-little-longer','13-paper-and-timber','14-the-last-light','15-after-the-sun-goes','16-a-quiet-corner']

def hashed(path,algorithm='sha256'):return hashlib.new(algorithm,path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main(replace_unreleased=False):
    active=json.loads((RUNTIME/'promotion/active.json').read_text());run=pathlib.Path(active['root'])
    shots={pathlib.Path(p['file']).stem:p for p in map(json.loads,(run/'photos.jsonl').read_text().splitlines())}
    # Earlier native exposure of the same composition avoids transient entity poof particles.
    clean=run/'client/screenshots/skin-check.png'
    shots['01-a-place-at-the-table']|={'path':str(clean),'sha256':hashed(clean)}
    compatibility=ROOT/'content/tarot/evidence/compatibility.json';evidence=json.loads(compatibility.read_text());archive=ROOT/'content/tarot/build/universal/Tabletop-Tarot-Universal.zip'
    from verify_packaging import main as verify_packaging
    packaging=verify_packaging()
    if hashed(archive)!=packaging['archive_sha256']:raise ValueError('Artifact differs from packaging proof')
    stage=ROOT/f'staging/releases/tabletop-tarot/{VERSION}';gallery=ROOT/f'docs/gallery/tabletop-tarot/{VERSION}'
    stage.mkdir(parents=True,exist_ok=True);gallery.mkdir(parents=True,exist_ok=True)
    output=stage/f'Tabletop-Tarot-{VERSION}.zip'
    if output.exists() and hashed(output)!=hashed(archive) and not replace_unreleased:raise ValueError('Refusing to replace an existing release with different bytes')
    shutil.copyfile(archive,output)
    for algorithm in ['sha1','sha256','sha512']:(stage/(output.name+'.'+algorithm)).write_text(hashed(output,algorithm)+'  '+output.name+'\n',encoding='utf-8')
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC failure')
        for name in ['pack.png','CREDITS.txt','LICENSE.md','licenses/MIT.txt','licenses/CC-BY-4.0.txt']:
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    images=[]
    for ordering,name in enumerate(NAMES):
        shot=shots[name];source=pathlib.Path(shot['path']);target=gallery/shot['file']
        if hashed(source)!=shot['sha256']:raise ValueError('Raw screenshot changed: '+name)
        with Image.open(source) as pic:
            pic.verify()
        with Image.open(source) as pic:size=list(pic.size)
        if size!=[1920,1080]:raise ValueError('Unexpected native capture size')
        shutil.copyfile(source,target)
        images.append({k:shot[k] for k in ['file','title','description','sha256','camera','edited']}|{'alt':shot['description'],'featured':ordering==0,'ordering':ordering,'size':size,'bytes':target.stat().st_size})
    profile=json.loads((RUNTIME/'promotion/skin-woflo/profile.json').read_text());skin=RUNTIME/'promotion/skin-woflo/skin.png'
    import base64
    texture=json.loads(base64.b64decode(next(p['value'] for p in profile['properties'] if p['name']=='textures')))['textures']['SKIN']
    provenance={'minecraft':'26.3','capture_method':'Official Minecraft Screenshot.grab; photography-only Java camera/options bridge, no class transformations or render replacement','resolution':[1920,1080],'postprocessing':'none; original PNG bytes copied without cropping, resizing, compositing or colour correction','resource_packs':['vanilla','Physical-Cards-Universal.zip'],'shaders':False,'world':{'generation':'minecraft:normal','seed':20261108,'scenery':'Staged ordinary vanilla blocks in naturally generated terrain. Houses, furniture, wool blanket, plants, boat and cat are scenery, not pack content.'},'character':{'username':'woflo_','uuid':'67d58862-7e44-4d3d-8ef5-d2b88ce23f57','skin_url':texture['url'].replace('http:','https:'),'skin_sha256':hashed(skin),'model':texture.get('metadata',{}).get('model','classic'),'retrieved_on':'2026-11-08','staging':'Vanilla mannequin with the signed Mojang woflo_ profile; spectator camera never appears in frame.'},'cards':'Unchanged shipped item models and textures. Tabletop entities created by production tarot:table/create and turned by tarot:table/flip in the disposable photo world. Decks supplied by production loot tables. No oversized replacement models.','artifact_sha256':hashed(output),'captured_artifact_sha256':evidence['combined_archive']['sha256'],'distribution_binding':'Tabletop Tarot packaging proof establishes identical effective runtime and artwork on every supported target; these photos were captured before the naming/license/marker changes.','camera_bridge_source_sha256':hashlib.sha256(__import__('promo_client').JAVA.encode()).hexdigest()}
    write(gallery/'gallery.json',{'project':'Tabletop Tarot','version':VERSION,'captured_on':'2026-11-08','featured':images[0]['file'],'publication_order':'images ordering ascending','provenance':provenance,'images':images})
    (gallery/'scene-commands.jsonl').write_bytes((run/'scene-commands.jsonl').read_bytes())
    rows=['# Tabletop Tarot — 1.0.0 gallery','',SUMMARY,'',f'{len(images)} unedited, native 1920 × 1080 Minecraft screenshots. Character scenes use the current **woflo_** skin. No shaders or external visual packs.','',f'[Release handoff](../../../../staging/releases/tabletop-tarot/{VERSION}/README.md) · [Captions, ordering, hashes and capture details](gallery.json)','','The cottage, furniture, garden, boat and cat are ordinary vanilla scenery. The cards and decks are the shipped pack. Character poses use a vanilla mannequin with the signed woflo_ Mojang profile.','', 'The first image is the suggested featured image. The order below varies locations and close-ups for a publication gallery.','']
    for image in images:rows += [f'### {image["title"]}','',f'![{image["alt"]}]({image["file"]})','',image['description'],'']
    (gallery/'README.md').write_text('\n'.join(rows),encoding='utf-8')
    files=[{'file':output.name,'primary':True,'roles':['datapack','resourcepack'],'bytes':output.stat().st_size,'hashes':{a:hashed(output,a) for a in ['sha1','sha256','sha512']}}]
    manifest={'schema_version':1,'project':'Tabletop Tarot','suggested_slug':'tabletop-tarot','version_number':VERSION,'version_name':'Tabletop Tarot 1.0.0','version_type':'release','github_release':'https://github.com/worflor/commonground-server/releases/tag/tabletop-tarot-v1.0.0','publication_status':'staged','publish_automatically':False,'summary':SUMMARY,'edition':'Java','game_versions':[r['minecraft'] for r in evidence['targets']],'loaders':['datapack'],'dependencies':[],'client_resource_pack_required_for_intended_art':True,'files':files,'modules':{'core':'always included','rider':'complete Rider–Waite–Smith deck, included','numbers':'complete Numbers set, included'},'license':{'code':'MIT','original_artwork':'CC-BY-4.0','rider_illustrations':'public-domain','notice':'LICENSE.md'},'listing':'LISTING.md','changelog':'CHANGELOG.md','icon':'pack.png','credits':'CREDITS.txt','gallery':'../../../../docs/gallery/tabletop-tarot/'+VERSION+'/gallery.json','verification':{'index':'../../../../content/tarot/evidence/compatibility.json','sha256':hashed(compatibility),'artifact_identical_to_verified_universal_zip':False,'effective_runtime_and_art_identical_to_verified_baseline':True,'packaging_index':'../../../../content/tarot/evidence/tabletop-packaging.json','packaging_index_sha256':hashed(ROOT/'content/tarot/evidence/tabletop-packaging.json'),'targets':len(evidence['targets']),'receipt_archives':evidence['saved_receipt_archives_verified']},'publisher_notes':['This is a handoff manifest, not a Modrinth API request body.','Upload the primary ZIP unchanged. It serves both datapack and resource-pack roles.','Use the exact game_versions list, not a continuous range. Bedrock is unsupported.','Use the gallery captions/order/featured flag; scenery and mannequin poses are not pack features.','Licenses: MIT code; CC BY 4.0 original artwork; public-domain Rider illustrations. Use LICENSE.md and preserve CREDITS.txt. Set the exact eleven game_versions explicitly: importer format-range inference is broader than tested support. No authenticated Modrinth upload has been performed.','Nothing has been published to Modrinth by this staging step.']}
    write(stage/'release.json',manifest)
    print(json.dumps({'version':VERSION,'zip':str(output.relative_to(ROOT)),'sha256':hashed(output),'photos':len(images),'gallery_bytes':sum(i['bytes'] for i in images),'release_manifest':str((stage/'release.json').relative_to(ROOT))}))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--replace-unreleased',action='store_true');main(parser.parse_args().replace_unreleased)
