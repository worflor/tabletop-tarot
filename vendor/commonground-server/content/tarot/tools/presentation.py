"""Quiet release materials, composed from the selected pack's original pixel art."""
import io,json
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]

def release_files(modules,root=None):
    root=Path(root or ROOT)
    from module_registry import load
    registry,_=load(root)
    module='rider' if 'rider' in modules else modules[0]
    name=registry[module]['icon']
    source=root/'modules'/module
    # Native pixels, no repainting or resampling of the source illustrations.
    front=Image.open(source/(name+'.png')).convert('RGBA')
    back=Image.open(source/'back.png').convert('RGBA')
    icon=Image.new('RGBA',(128,128),(26,31,29,255));draw=ImageDraw.Draw(icon)
    draw.rectangle((4,4,123,123),outline=(125,117,87,255))
    for plate,xy in [(back,(10,5)),(front,(46,3))]:
        draw.rectangle((xy[0]+2,xy[1]+3,xy[0]+plate.width+2,xy[1]+plate.height+3),fill=(12,16,14,255))
        icon.alpha_composite(plate,xy)
    out=io.BytesIO();icon.convert('RGB').save(out,format='PNG')
    install='''Tabletop Tarot — one ZIP, two vanilla pack locations

Keep this ZIP intact. It serves as both the datapack and resource pack.

SINGLEPLAYER
1. Copy this ZIP into your world's datapacks folder.
2. Copy the same ZIP into Minecraft's resourcepacks folder, then enable it.
3. Reload or reopen the world. No mod or plugin is required.

SERVER
Install this ZIP in the world's datapacks folder. Host the same unchanged ZIP
at a direct download URL and set resource-pack and resource-pack-sha1 in
server.properties. To calculate this ZIP's SHA-1 in PowerShell, run:
Get-FileHash -Algorithm SHA1 ./Tabletop-Tarot-Universal.zip
Use the hash shown, without spaces. The build folder also includes a .sha1 file.
Players can then accept Minecraft's normal server resource-pack prompt.
On older releases, keep Tabletop Tarot above other packs that replace item
models (for example 3D Default). Ordinary texture replacements remain usable.
If your server already offers resources, combine the packs during server setup;
do not replace the existing server pack without preserving it.

PLAY
Craft eight paper around an ink sac (Rider) or lapis lazuli (Numbers).
The normal recipe book learns a deck when you have its ingredients.
Deck in hand: use draws the top card; sneak-use shuffles.
With a card offhand, sneak-use on a deck puts that card on top instead.
Card in hand: use places it face-down on a clear tabletop or slab.
Aim at the top face; sides and undersides do not place cards.
Sneak-use avoids opening a workstation. On a placed card, use turns it over,
sneak-use rotates it, and hit picks it up. Q remains an ordinary item drop.
Keep the offhand empty for ordinary use, except when returning a card.
Vanilla blocks, usable offhand items and ridden pigs can take priority over use.
The dependable alternative is /trigger tarot.action set N:
1 draws, 2 shuffles, 3 returns the offhand card, 4 places the held card.
These commands also work while mounted and do not require operator permissions.
Existing paper-based cards retain their notes and contents. Drawing, returning
or placing one upgrades its carrier; hold a band offhand to place, or use
/trigger tarot.action set 4. Until handled, older items still count as paper
in crafting, so keep untouched older cards out of paper recipes.
New cards and bands also have vanilla tool-repair eligibility removed. Successful
handling upgrades older carriers; keep untouched earlier items out of tool-repair
crafting. Custom durability-capacity overrides are saved in their card data.

Only your marked cards and bands respond. There is no welcome screen,
automatic item grant, mandatory tutorial, or enforced reading/game.
Vanilla fire, lava, despawn and inventory-space rules still apply.
'''
    from profiles import PROFILES
    ingredients='Craft eight paper around the matching centre ingredient:\n'+ '\n'.join('- '+m.replace('_',' ').replace('-',' ').title()+': '+registry[m]['ingredient'].split(':',1)[1].replace('_',' ') for m in modules)
    install=install.replace('Craft eight paper around an ink sac (Rider) or lapis lazuli (Numbers).',ingredients)
    install+='\nSUPPORTED JAVA RELEASES\n'+', '.join(PROFILES)+'.\nOther releases and Bedrock are not covered.\n'
    credits=['Tabletop Tarot','Runtime and packaging: woflo','',
             'Original plates and card metadata are imported from the owner’s Cartomancy source.',
             'The following source manifest credits travel with this selected build:']
    for selected in modules:
        manifest=json.loads((root/'modules'/selected/'pack.json').read_text(encoding='utf-8'))['manifest']
        credits += ['',selected, *[f'{k}: {manifest[k]}' for k in ['name','author','licenseId','version'] if k in manifest]]
    credits += ['', 'Original code: Copyright (c) 2026 woflo (worflor), MIT.',
                'Original Numbers art, backs, textures and icon composition: woflo (worflor), CC BY 4.0.',
                'Rider–Waite–Smith 1909 illustrations: Pamela Colman Smith with Arthur Edward Waite; public domain.',
                'The icon includes a public-domain Rider illustration; no new rights are asserted over it.',
                'Source artwork is preserved without repainting or resampling.',
                'Imported Lore/source license identifiers above are preserved provenance.',
                'See LICENSE.md for the explicit Tabletop Tarot grant and attribution requirements.',
                'https://github.com/worflor/commonground-server/tree/main/content/tarot',
                'https://creativecommons.org/licenses/by/4.0/']
    result = {'pack.png':out.getvalue(),'INSTALL.txt':install.encode('utf-8'),
              'CREDITS.txt':('\n'.join(credits)+'\n').encode('utf-8')}
    # License materials belong to this distribution, including synthetic module fixtures.
    for name in ['LICENSE.md', 'licenses/MIT.txt', 'licenses/CC-BY-4.0.txt']:
        result[name]=(ROOT/name).read_bytes()
    return result

def write_release(folder,modules,root=None):
    for name,data in release_files(modules,root).items():
        target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
