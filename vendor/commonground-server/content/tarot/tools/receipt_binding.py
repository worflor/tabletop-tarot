"""Bind small receipt indexes to their authoritative archived metadata without loading huge traces."""
import gzip,json

FIELDS={'minecraft','scope','passed','checks','focused_shuffle','combined_zip_sha256','datapack_sha256','source_datapack_sha256','target_datapack_sha256','source','target','module','client_log','client_log_sha256','artifact_validation','resource_order','external_resources','downloads','screenshots'}
FIELDS|={'seed','steps_requested','audits','operations','transitions','fuzzer_source_sha256','fuzz_seed','baseline_zip_sha256','expanded_zip_sha256','test_agent','test_source','test_source_sha256','log','log_sha256'}

def summarize_checks(checks):
    return [{k:v for k,v in check.items() if isinstance(v,(str,int,float,bool,type(None))) or (isinstance(v,list) and all(isinstance(i,(str,int,float,bool,type(None))) for i in v))} for check in checks]

def archived_fields(path,wanted):
    """Read top-level members incrementally; stop before large trailing protocol/command traces.

    Receipt producers put binding metadata before those traces. Small earlier
    members are decoded individually; unexpectedly large metadata fails closed.
    The complete compressed/uncompressed stream is separately SHA/CRC checked.
    """
    decoder=json.JSONDecoder();buffer='';eof=False;found={}
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        def more():
            nonlocal buffer,eof
            chunk=stream.read(65536)
            if not chunk:eof=True
            buffer+=chunk
            if len(buffer)>32*1024*1024:raise ValueError('Receipt metadata member exceeds bounded decoder capacity')
        def whitespace():
            nonlocal buffer
            while True:
                buffer=buffer.lstrip()
                if buffer or eof:return
                more()
        def value():
            nonlocal buffer
            while True:
                whitespace()
                try:
                    result,end=decoder.raw_decode(buffer)
                    if end==len(buffer) and not eof:more();continue
                    buffer=buffer[end:];return result
                except json.JSONDecodeError:
                    if eof:raise
                    more()
        whitespace()
        if not buffer.startswith('{'):raise ValueError('Receipt must be a JSON object')
        buffer=buffer[1:]
        while wanted-found.keys():
            whitespace()
            if buffer.startswith('}'):break
            key=value()
            if not isinstance(key,str):raise ValueError('Receipt member name must be a string')
            whitespace()
            if not buffer.startswith(':'):raise ValueError('Receipt member separator missing')
            buffer=buffer[1:];member=value()
            if key in wanted:found[key]=member
            if not wanted-found.keys():break
            whitespace()
            if buffer.startswith(','):buffer=buffer[1:]
            elif buffer.startswith('}'):break
            else:raise ValueError('Receipt object delimiter missing')
    missing=wanted-found.keys()
    if missing:raise ValueError('Archived receipt lacks binding fields: '+', '.join(sorted(missing)))
    return found

def bind_index(index_path,index):
    wanted=FIELDS & index.keys()
    try:actual=archived_fields(index_path.parent/index['full_receipt']['path'],wanted)
    except ValueError as error:
        # Older writers added an empty summary list even to log-only receipts.
        # Absence means zero checks, never permission to invent a passing check.
        if str(error)!='Archived receipt lacks binding fields: checks' or index.get('checks')!=[]:raise
        actual=archived_fields(index_path.parent/index['full_receipt']['path'],wanted-{'checks'});actual['checks']=[]
    if 'checks' in actual:actual['checks']=summarize_checks(actual['checks'])
    def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    for key in wanted:
        if canonical(actual[key])!=canonical(index[key]):raise ValueError('Receipt index differs from archived '+key+': '+str(index_path))
    return index
