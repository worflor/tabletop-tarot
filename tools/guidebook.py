"""Compile an authored field guide into native, linked book pages per dialect."""
from __future__ import annotations
import json
import re
from pathlib import Path

# Default ASCII glyph advances (bitmap widths plus spacing); the space provider
# overrides the empty bitmap with four pixels. No Minecraft textures are shipped.
WIDTHS = dict.fromkeys((chr(n) for n in range(32,127)), 6)
WIDTHS.update({' ':4,'!':2,'"':4,"'":2,'(':4,')':4,'*':4,',':2,'.':2,':':2,';':2,
               '<':5,'>':5,'@':7,'I':4,'[':4,']':4,'`':3,'f':5,'i':2,'k':5,'l':3,
               't':4,'{':4,'|':2,'}':4,'~':7})
WIDTH, HEIGHT = 114, 14
COUNTS = {'major':22,'wands':14,'cups':14,'swords':14,'pentacles':14,'digits':9,'masters':3}
# Dark inks on vanilla parchment. Colour supports the words and link underline;
# it is never the only way to identify an author, chapter, or control.
PALETTES = {
    'steve': {'accent':'#354f79', 'secondary':'#725126', 'ink':'#342f2a'},
    'alex': {'accent':'#355d47', 'secondary':'#804b33', 'ink':'#30372e'},
}
CHAPTERS = {'major':'#594371','wands':'#81432d','cups':'#2f596b',
            'swords':'#4d5369','pentacles':'#50602f','digits':'#725126','masters':'#694469'}
ITEM_NAME_COLORS={'steve':'#a7bee8','alex':'#a7d8b4'}
EDITIONS = {
    # Keep the original recipe/loot ID as the Steve edition, including commands
    # and existing recipe unlocks. Already signed books keep their original text.
    'steve': {'id':'guidebook', 'ingredients':['book','amethyst_shard']},
    'alex': {'id':'guidebook_alex', 'ingredients':['book','amethyst_shard','feather']},
}


def width(text, bold=False):
    if any(c not in WIDTHS for c in text):
        raise ValueError('Guide uses a glyph without a checked advance: '+repr(text))
    return sum(WIDTHS[c]+(1 if bold else 0) for c in text)


def wrap(text, bold=False):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for word in paragraph.split():
            if width(word,bold)>WIDTH:
                raise ValueError('Guide word is wider than the page: '+word)
            candidate=(line+' '+word).strip()
            if width(candidate,bold)>WIDTH:
                lines.append(line);line=word
            else:line=candidate
        lines.append(line)
    return lines


def component(text, **style):
    return {'text':text, **style}


def link(text, page, modern, tooltip=None, color='#694467'):
    value=component(text,color=color,underlined=True)
    value['click_event' if modern else 'clickEvent'] = (
        {'action':'change_page','page':page} if modern else {'action':'change_page','value':str(page)})
    if tooltip:
        value['hover_event' if modern else 'hoverEvent'] = (
            {'action':'show_text','value':tooltip} if modern else {'action':'show_text','contents':tooltip})
    return value


def compose(identifier, lines, footer, ink='#362d2b'):
    """Explicit line breaks make page fit a checked authoring contract."""
    if len(lines)>HEIGHT-1:
        raise ValueError(f'{identifier}: {len(lines)} lines leave no room for navigation')
    lines=lines+[[component('')]]*(HEIGHT-1-len(lines))+[footer]
    for row in lines:
        if sum(width(c['text'],c.get('bold',False)) for c in row)>WIDTH:
            raise ValueError(identifier+': a line exceeds the vanilla book width')
    parts=[]
    for i,row in enumerate(lines):
        if i:parts.append(component('\n'))
        parts.extend(row)
    return {'id':identifier,'text':'\n'.join(''.join(c['text'] for c in row) for row in lines),
            'component':component('',color=ink,italic=False,extra=parts)}


def paragraph_lines(text, **style):
    return [[component(row,**style)] for row in wrap(text,style.get('bold',False))]


def narrative_lines(text):
    """Set the opening scene in italic; keep the reflection in clear roman ink.

    Styling is applied after wrapping the complete paragraph, so transitions
    cannot insert a space, move a word, or change a link's hit area.
    """
    text=' '.join(text.split())
    scene=re.search(r'[.!?](?:\s|$)',text)
    end=scene.start()+1 if scene else 0
    result=[];offset=0
    for line in wrap(text):
        split=max(0,min(len(line),end-offset))
        result.append(([component(line[:split],italic=True)] if split else [])+
                      ([component(line[split:])] if split<len(line) else []))
        offset+=len(line)+1
    return result


def pages(content, modern):
    palette=PALETTES.get(content.get('edition'),{'accent':'#694467','secondary':'#76543b','ink':'#362d2b'})
    def nav(text,page,tooltip=None):
        return link(text,page,modern,tooltip,color=palette['accent'])
    def finish(identifier,rows,footer):
        return compose(identifier,rows,footer,ink=palette['ink'])
    sections=content['sections']
    if [s['id'] for s in sections]!=list(COUNTS) or any(len(s['entries'])!=COUNTS[s['id']] for s in sections):
        raise ValueError('Guide section membership differs from the 90-card catalogue')
    # The 100-page cap is a writable-book editing limit. WrittenBookContent's
    # page codec is an unbounded list; this signed guide uses 108 readable pages.
    indices=[];section_page={};card_index={}
    for section in sections:
        entries=section['entries'];chunk=11 if section['id']=='major' else 7
        if section['id'] in ['digits','masters']:chunk=len(entries)
        groups=[entries[i:i+chunk] for i in range(0,len(entries),chunk)]
        section_page[section['id']]=6+len(indices)
        for i,group in enumerate(groups):
            page=6+len(indices)
            for entry in group:card_index[entry['key']]=page
            indices.append((section,i,len(groups),group))
    cards=[e for s in sections for e in s['entries']]
    if len(cards)!=90 or len({c['key'] for c in cards})!=90:
        raise ValueError('Guide must cover all 90 unique cards')
    card_page={c['key']:6+len(indices)+i for i,c in enumerate(cards)}
    postscript=content.get('postscript')
    closing=6+len(indices)+len(cards)+bool(postscript)
    contents=lambda:[nav('Contents',2)]
    result=[]

    def front(identifier,value,footer=None):
        rows=paragraph_lines(value['title'],bold=True,color=palette['accent'])
        if identifier=='opening' and content.get('edition'):
            rows+=paragraph_lines('Notes by '+content['author'],color=palette['secondary'],italic=True)
        rows += [[component('')]]+paragraph_lines(value['body'])
        if identifier=='closer' and content.get('edition'):
            rows+=paragraph_lines('- '+content['author'],color=palette['secondary'],italic=True)
        result.append(finish(identifier,rows,footer or contents()))

    opening_footer=contents()
    if postscript:opening_footer += [component(' | '),nav('P.S.',closing-1)]
    front('opening',content['opening'],opening_footer)
    rows=paragraph_lines('Find a Page',bold=True,color=palette['accent'])+[[component('')]]
    for title,page in [('A Deck in Hand',3),('Around the Table',4),('A Little Reading',5),
                        *[(s['title'],section_page[s['id']]) for s in sections],('Leave a Light On',closing)]:
        rows.append([nav(title,page)])
    result.append(compose('contents',rows,[nav('Opening',1)],ink=palette['ink']))
    front('controls/deck',content['how_to'][0])
    front('controls/table',content['how_to'][1])
    copy=component('Copy deal',color=palette['accent'],underlined=True)
    copy['click_event' if modern else 'clickEvent']={'action':'copy_to_clipboard','value':'/trigger tarot.action set 5'}
    front('reading',content['reading'],[copy,component(' | '),*contents()])
    for section,index,total,entries in indices:
        title=section['title']+(f' {index+1}/{total}' if total>1 else '')
        heading=component(title,bold=True,color=CHAPTERS[section['id']])
        heading['hover_event' if modern else 'hoverEvent']=(
            {'action':'show_text','value':section['intro']} if modern else {'action':'show_text','contents':section['intro']})
        rows=[[heading],[component('')]]
        if section['id']=='digits':
            # Use the previous spacer for a third explanatory line; card links
            # stay on the same rows and the complete index still fits one page.
            rows=[[heading]]+paragraph_lines('Add digits; repeat.\nStop at 1-9, or keep\n11,22,33.',color=palette['secondary'])
        if section['id']=='masters':
            rows+=paragraph_lines(section['intro'])+[[component('')]]
        rows += [[nav(e['name'],card_page[e['key']],e['minecraft_title'])] for e in entries]
        footer=contents()
        if index+1<total:footer+=[component(' | '),nav('More >',section_page[section['id']]+index+1)]
        elif total>1:footer=[nav('< List',section_page[section['id']]),component(' | '),*footer]
        result.append(finish('index/'+section['id']+'/'+str(index+1),rows,footer))
    for section in sections:
        for entry in section['entries']:
            rows=paragraph_lines(entry['name'],bold=True,color=CHAPTERS[section['id']])
            rows+=paragraph_lines(entry['minecraft_title'],color=palette['secondary'],italic=True)
            rows += [[component('')]]+narrative_lines(entry['body'])
            result.append(finish(entry['key'],rows,[nav('Index',card_index[entry['key']]),component(' | '),*contents()]))
    if postscript:front('postscript',postscript,[*contents(),component(' | '),nav('Close',closing)])
    front('closer',content['closer'],[nav('Read again',1),component(' | '),*contents()])
    if len(result)!=closing or closing!=108+bool(postscript):
        raise ValueError('Guidebook index and compiled pages disagree')
    return result


def write(folder, target, catalogue, spec, sources, expected_files):
    if list(sources)!=list(EDITIONS):
        raise ValueError('Guide sources must explicitly name Steve and Alex in edition order')
    expected={c['key']:c['name'] for c in catalogue}
    modern=bool(spec['text_objects'])
    generated=set();index={};controls=None
    for edition,source in sources.items():
        content=json.loads(source.read_text())
        authored={e['key']:e['name'] for s in content['sections'] for e in s['entries']}
        if authored!=expected:
            raise ValueError('Guide entries must exactly match the original catalogue')
        if content.get('edition')!=edition or content['author']!=edition.title():
            raise ValueError('Guide author and edition disagree')
        if not 1<=len(content['title'])<=32:
            raise ValueError('Native book title must fit its 32-character codec')
        if controls is not None and content['how_to']!=controls:
            raise ValueError('Both authors must teach identical gameplay controls')
        controls=content['how_to']
        book=pages(content,modern)
        identity=EDITIONS[edition]
        write_edition(folder,target,spec,content,book,identity)
        generated.update(f'{d}/{identity["id"]}.json' for d in ['recipe','loot_table'])
        generated.add('advancement/recipes/'+identity['id']+'.json')
        index[edition]={'author':content['author'],'title':content['title'],
                       'recipe':'tarot:'+identity['id'],'ingredients':identity['ingredients'],
                       'pages':len(book),'cards':len(authored),
                       'entries':[{'page':i+1,'id':p['id'],'text':p['text']} for i,p in enumerate(book)]}
    if generated!=set(expected_files):
        raise ValueError('Generated guide files differ from src/overrides.json')
    return {'schema':2,'editions':index}


def write_edition(folder,target,spec,content,book,identity):
    modern=bool(spec['text_objects'])
    page_values=[p['component'] if modern else json.dumps(p['component'],ensure_ascii=False,separators=(',',':')) for p in book]
    edition=content['edition'];palette=PALETTES[edition]
    components={
        'minecraft:written_book_content':{'title':content['title'],'author':content['author'],
                                          'pages':page_values,'generation':0,'resolved':True},
        'minecraft:custom_data':{'tarot':{'kind':'guide','edition':2,'guide_author':edition}},
        'minecraft:custom_name':component(content.get('item_name',content['author']+"'s Tarot Guide"),color=ITEM_NAME_COLORS[edition],italic=False),
        'minecraft:enchantment_glint_override':False,
    }
    from guidebook_models import appearance
    components.update(appearance(edition,spec))
    if not modern:components['minecraft:custom_name']=json.dumps(components['minecraft:custom_name'])
    item={'id':'minecraft:written_book','count':1,'components':components}
    ingredients=['minecraft:'+name for name in identity['ingredients']]
    recipe={'type':'minecraft:crafting_shapeless','ingredients':[
        {'item':name} for name in ingredients] if spec['object_ingredients'] else ingredients, 'result':item}
    modifier={'type' if target.mc_version=='26.3' else 'function':'minecraft:set_components','components':components}
    entry={'type':'minecraft:item','name':'minecraft:written_book',
           **({'modifier':modifier} if target.mc_version=='26.3' else {'functions':[modifier]})}
    loot={'type':'minecraft:generic','pools':[{'rolls':1,'entries':[entry]}]}
    advancement={'criteria':{'ingredients':{'trigger':'minecraft:inventory_changed','conditions':{
        'items':[{'items':[name]} for name in ingredients]}}},'rewards':{'recipes':['tarot:'+identity['id']]}}
    for directory,name,value in [('recipe',identity['id'],recipe),('loot_table',identity['id'],loot),('advancement','recipes/'+identity['id'],advancement)]:
        if target.plural_folders:directory={'recipe':'recipes','loot_table':'loot_tables','advancement':'advancements'}[directory]
        out=folder/'data/tarot'/directory/(name+'.json');out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
