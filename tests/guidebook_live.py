"""Native survival crafting, shared lectern links, reload and whole-book custody."""
import hashlib
import json
import math
import os
import re
import subprocess
import time
import zipfile

from guidebook import width
from verify import VERSION_MAP


def run_guidebook(version,rcon,xdo,work,shot,index_path):
    index=json.loads(index_path.read_text())
    assert index['schema']==2 and list(index['editions'])==['steve','alex']
    editions={}
    for edition,guide in index['editions'].items():
        def painted_shot(display,name):
            # A page-change packet is authoritative before either GPU paints it.
            time.sleep(.35)
            shot(display,edition+'-'+name)
        editions[edition]=run_edition(version,rcon,xdo,work,painted_shot,guide,edition)
    for player in ['Alice','Bob']:
        log=(work/f'client_{player}.log').read_text(errors='replace')
        assert any('Reloading ResourceManager:' in line and 'server/' in line for line in log.splitlines()), player+' did not apply the server resource pack'
        assert not any('tarot:guidebook' in line and any(error in line for error in ['Missing textures','Unable to load','Failed to load']) for line in log.splitlines()), player+' has guidebook resource errors'
    frozen=work/'server/world/datapacks/Tabletop-Tarot.zip'
    result={'minecraft':version,'archive_sha256':hashlib.sha256(frozen.read_bytes()).hexdigest(),
            'passed':True,'editions':editions,
            'checks':sum(len(value['checks']) for value in editions.values()),
            'guide_index_sha256':hashlib.sha256(index_path.read_bytes()).hexdigest(),
            'scope':'Two stock graphical clients; both survival recipes, native shared lectern links from both players, clipboard, reload and exact whole-book custody. RCON prepares fixtures and observes authoritative page and inventory state. Screenshots retain both rendered views.'}
    (work/'guidebook-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Both guide editions passed native crafting, navigation, reload and custody',flush=True)


def run_edition(version,rcon,xdo,work,shot,index,edition):
    cmd=rcon.cmd
    checks=[];navigation=[]
    scale=int(re.search(r'^guiScale:(\d+)$',(work/'client_Alice/options.txt').read_text(),re.M)[1])
    assert scale>0
    screen_width=math.ceil(1280/scale);screen_height=math.ceil(720/scale)
    inventory_left=(screen_width-176)//2;inventory_top=(screen_height-166)//2
    lookup={p['id']:p for p in index['entries']}
    frozen=work/'server/world/datapacks/Tabletop-Tarot.zip'
    with zipfile.ZipFile(frozen) as source:
        prefix=VERSION_MAP[version][0]
        directory='recipes' if VERSION_MAP[version][2] else 'recipe'
        recipe_id=index['recipe'].split(':')[1]
        recipe=json.loads(source.read(f'{prefix}/data/tarot/{directory}/{recipe_id}.json'))
    raw=recipe['result']['components']['minecraft:written_book_content']['pages']
    book=[json.loads(p) if isinstance(p,str) else p for p in raw]
    assert len(book)==index['pages'] and index['cards']==90

    def yes(command):return 'passed' in cmd(command).lower()

    def wait(label,predicate):
        deadline=time.monotonic()+8
        while not predicate():
            if time.monotonic()>deadline:raise AssertionError(label)
            time.sleep(.05)

    def click(x,y,screen=':91'):
        xdo(screen,'mousemove',str(round(x)),str(round(y)),'click','1')
        time.sleep(.12)

    def page():
        response=cmd('data get block 0 -60 2 Page')
        return int(re.findall(r'-?\d+',response.split('following block data:',1)[-1])[-1])

    def rendered_counter(screen):
        # The page-number strip is opaque, static parchment, outside link hover
        # areas. Its pixels acknowledge a painted page independently of RCON.
        left=scale*((screen_width-192)//2+36)
        region=f'{scale*114}x{scale*8}+{left}+{scale*18}'
        return subprocess.run(['import','-display',screen,'-window','root','-crop',region,'rgb:-'],
                              capture_output=True,check=True,timeout=5).stdout

    def press_link(label,target_page=None,screen=':91'):
        current=page()+1;x=0;line=0
        for value in book[current-1]['extra']:
            text=value['text']
            if text=='\n':line+=1;x=0;continue
            event=value.get('click_event',value.get('clickEvent',{}))
            number=event.get('page',event.get('value'))
            matches=(event.get('action')=='copy_to_clipboard' if target_page is None else
                     event.get('action')=='change_page' and int(number)==target_page)
            if text==label and matches:
                # Use the client's actual configured scale. BookViewScreen's
                # text starts at (imageLeft+36,32), with nine-pixel lines.
                click(scale*((screen_width-192)//2+36+x+width(text,value.get('bold',False))/2),
                      scale*(32+line*9+4),screen)
                return event
            x+=width(text,value.get('bold',False))
        raise AssertionError('No matching native link: '+repr((current,label,target_page)))

    def follow(label,target,screen=':91'):
        current=page()+1;target_page=lookup[target]['page']
        previous={display:rendered_counter(display) for display in [':91',':92']}
        press_link(label,target_page,screen)
        wait(f'Native book link {label}: {current} -> {target_page}',lambda:page()==target_page-1)
        if current!=target_page:
            for display in previous:
                wait(f'Painted book page {target_page} on {display}',
                     lambda:rendered_counter(display)!=previous[display])
        navigation.append({'from':current,'label':label,'to':target_page,'player':'Alice' if screen==':91' else 'Bob'})

    for name in ['Alice','Bob']:
        cmd('ride '+name+' dismount');cmd('clear '+name);cmd('gamemode survival '+name);cmd('deop '+name)
    cmd('fill -3 -60 -2 3 -57 6 air')
    cmd('tp Alice 0.5 -60 0.5 0 0');cmd('tp Bob 0.5 -60 4.5 180 0')
    cmd('advancement revoke Alice only tarot:recipes/'+recipe_id)
    cmd('recipe take Alice '+index['recipe'])
    for slot,ingredient in enumerate(index['ingredients']):
        cmd(f'item replace entity Alice hotbar.{slot} with minecraft:{ingredient}')
    wait('Guide recipe discovery',lambda:yes('execute as Alice if entity @s[advancements={tarot:recipes/'+recipe_id+'=true}]'))
    xdo(':91','key','1');time.sleep(.25)
    xdo(':91','key','e');time.sleep(.7)
    # Standard player inventory, 2x2 grid; all item movement uses real clicks.
    def inventory_click(x,y):click(scale*(inventory_left+x),scale*(inventory_top+y))
    for slot in range(len(index['ingredients'])):
        inventory_click(16+18*slot,150);inventory_click(106+18*(slot%2),26+18*(slot//2))
    time.sleep(.4);shot(':91','guide-crafting.png')
    inventory_click(162,36);inventory_click(16,150)
    xdo(':91','key','e');time.sleep(.3)
    wait('Native guide crafting',lambda:yes('execute if items entity Alice weapon.mainhand minecraft:written_book[minecraft:custom_data~{tarot:{kind:"guide"}}]'))
    for ingredient in index['ingredients']:
        assert 'Found ' not in cmd('clear Alice minecraft:'+ingredient+' 0'), 'Crafting left an ingredient behind'
    assert yes('execute if data entity Alice SelectedItem.components."minecraft:written_book_content"{author:"'+index['author']+'"}')
    assert yes('execute if data entity Alice SelectedItem.components."minecraft:custom_data"{tarot:{guide_author:"'+edition+'"}}')
    cmd('execute store result score #guide_pages tarot.sys run data get entity Alice SelectedItem.components."minecraft:written_book_content".pages')
    assert rcon.score('#guide_pages','tarot.sys')==index['pages']
    cmd('data modify storage tarot_guide:oracle item set from entity Alice SelectedItem')
    checks.append({'name':'recipe_discovery_and_native_survival_crafting','passed':True,'author':index['author'],'recipe':index['recipe'],'pages':index['pages'],'cards':90})
    if any(key in recipe['result']['components'] for key in ['minecraft:item_model','minecraft:custom_model_data']):
        from guidebook_models_live import capture
        capture(version,rcon,xdo,work,shot,scale,inventory_left,inventory_top,recipe)
    xdo(':91','click','3');time.sleep(.5);shot(':91','guide-opening-held.png')
    xdo(':91','key','Escape');time.sleep(.2)
    cmd('setblock 0 -60 2 minecraft:lectern[facing=north]')
    pitch=math.degrees(math.atan2(.82,2.0))
    cmd(f'tp Alice 0.5 -60 0.5 0 {pitch}')
    time.sleep(.4)  # Let the native client receive and render the aim change.
    xdo(':91','click','3')
    wait('Native guide insertion',lambda:yes('execute if block 0 -60 2 minecraft:lectern[has_book=true]'))
    assert not yes('execute if items entity Alice weapon.mainhand minecraft:written_book')
    xdo(':91','click','3');time.sleep(.5)
    cmd(f'tp Bob 0.5 -60 4.5 180 {pitch}')
    time.sleep(.4)
    xdo(':92','click','3');time.sleep(.5)
    assert page()==0
    if 'postscript' in lookup:
        follow('P.S.','postscript')
        shot(':91','guide-postscript.png');shot(':92','guide-postscript-Bob.png')
        follow('Contents','contents');follow('Opening','opening')
    follow('Contents','contents')
    follow('A Little Reading','reading');press_link('Copy deal')
    clipboard=subprocess.run(['xclip','-o','-selection','clipboard'],env={**os.environ,'DISPLAY':':91'},
                             capture_output=True,text=True,check=True,timeout=5).stdout
    assert clipboard=='/trigger tarot.action set 5'
    checks.append({'name':'native_copy_link_places_only_the_blind_deal_command_on_clipboard','passed':True})
    follow('Contents','contents')
    for label,section,key in [('Major Arcana','major','rider/major-0'),('Wands','wands','rider/wands-ace'),
                              ('Cups','cups','rider/cups-ace'),('Swords','swords','rider/swords-ace'),
                              ('Pentacles','pentacles','rider/pentacles-ace'),('The Digits','digits','numbers/number-1'),
                              ('Master Numbers','masters','numbers/number-33')]:
        follow(label,'index/'+section+'/1')
        if section=='major':shot(':91','guide-major-index.png')
        entry=next(p for p in index['entries'] if p['id']==key)
        first_name=entry['text'].split('\n',1)[0]
        # Names that wrap in the heading remain single-line index labels.
        for value in book[page()]['extra']:
            event=value.get('click_event',value.get('clickEvent',{}))
            if event.get('action')=='change_page' and int(event.get('page',event.get('value'))) == entry['page']:
                first_name=value['text'];break
        follow(first_name,key)
        if section in ['major','masters']:
            shot(':91','guide-'+section+'.png');shot(':92','guide-'+section+'-Bob.png')
        follow('Index','index/'+section+'/1')
        if section=='digits':
            follow('Five','numbers/number-5')
            shot(':91','guide-review-five.png');shot(':92','guide-review-five-Bob.png')
            follow('Index','index/digits/1')
            shot(':91','guide-digits-index.png')
        if section=='swords':
            follow('More >','index/swords/2')
            for label,key,slug in [('Eight of Swords','rider/swords-eight','eight-swords'),
                                   ('Queen of Swords','rider/swords-queen','queen-swords')]:
                follow(label,key)
                shot(':91','guide-review-'+slug+'.png');shot(':92','guide-review-'+slug+'-Bob.png')
                follow('Index','index/swords/2')
        follow('Contents','contents')
    follow('Major Arcana','index/major/1');follow('More >','index/major/2')
    for label,key,slug in [('The Hanged Man','rider/major-12','hanged-man'),
                           ('Death','rider/major-13','death'),('The Tower','rider/major-16','tower')]:
        follow(label,key)
        shot(':91','guide-review-'+slug+'.png');shot(':92','guide-review-'+slug+'-Bob.png')
        follow('Index','index/major/2')
    follow('The World','rider/major-21')
    # Bob changes the shared book using the same physical link, as a non-op.
    time.sleep(.35)
    follow('Index','index/major/2',screen=':92')
    shot(':91','guide-shared-return-Alice.png');shot(':92','guide-shared-return-Bob.png')
    follow('Contents','contents')
    follow('Pentacles','index/pentacles/1');follow('More >','index/pentacles/2')
    follow('Knight of Pentacles','rider/pentacles-knight');shot(':91','guide-long-name.png')
    follow('Index','index/pentacles/2');follow('Contents','contents')
    follow('Leave a Light On','closer')
    shot(':91','guide-closer.png');shot(':92','guide-closer-Bob.png')
    checks.append({'name':'native_lectern_hyperlinks_reach_all_seven_sections_and_cards_beyond_page_100','passed':True,'navigation':navigation})
    checks.append({'name':'both_non_operator_clients_navigate_the_same_lectern','passed':True,'scope':'Bob returns from The World to its index with a real click; Alice continues from that page. Both rendered views are retained.'})
    cmd('reload');time.sleep(.5)
    assert page()==lookup['closer']['page']-1
    xdo(':91','key','Escape');time.sleep(.2);xdo(':91','click','3');time.sleep(.5)
    follow('Contents','contents')
    checks.append({'name':'reload_preserves_book_and_native_navigation','passed':True})
    shot(':91','guide-contents.png')
    follow('Opening','opening')
    shot(':91','guide-opening.png');shot(':92','guide-opening-Bob.png')
    follow('Contents','contents')
    # Removing a lectern book closes the other reader's screen. Close Bob's
    # known book screen first; Escape after removal would open the pause menu.
    click(scale*(screen_width//2-51),scale*206,screen=':92')
    click(scale*(screen_width//2+51),scale*206)  # Native non-operator Take Book button.
    wait('Guide book take',lambda:yes('execute if items entity Alice weapon.mainhand minecraft:written_book[minecraft:custom_data~{tarot:{kind:"guide"}}]'))
    assert yes('execute if block 0 -60 2 minecraft:lectern[has_book=false]')
    assert not yes('execute if items entity Bob hotbar.* minecraft:written_book')
    cmd('data modify storage tarot_guide:oracle compare set from storage tarot_guide:oracle item')
    cmd('execute store success score #guide_changed tarot.sys run data modify storage tarot_guide:oracle compare set from entity Alice SelectedItem')
    assert rcon.score('#guide_changed','tarot.sys')==0
    assert 'Found 1 ' in cmd('clear Alice minecraft:written_book 0')
    checks.append({'name':'taking_guide_returns_one_exact_complete_book','passed':True})
    result={'author':index['author'],'passed':True,'checks':checks}
    (work/('guidebook-'+edition+'-result.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(index['author']+' native crafting, navigation, reload and custody passed',flush=True)
    return result
