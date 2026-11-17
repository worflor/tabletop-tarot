"""Bind current deliverables to complete game receipts and validate saved history."""
import gzip,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from check import check,require
from profiles import PROFILES
from receipt_binding import bind_index

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence'

def digest(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def bound(path):return bind_index(path,read(path))
def pack_hashes(path):return {p.relative_to(path).as_posix():digest(p.read_bytes()) for p in path.rglob('*') if p.is_file()}

def main():
    # Keep the complete baseline receipts intact. Packaging-only changes bind
    # through exact effective-byte equality rather than relabeling old game runs.
    if read(ROOT/'build/universal/build.json')['zip_sha256']!=read(EVIDENCE/'compatibility.json')['combined_archive']['sha256']:
        from verify_packaging import main as verify_packaging
        verify_packaging()
        return
    from universal import validate as validate_bundle,resolve,hashes
    import zipfile
    archives=0
    for index in EVIDENCE.rglob('*.json'):
        data=read(index)
        if not isinstance(data,dict) or 'full_receipt' not in data:continue
        ref=data['full_receipt'];path=(index.parent/ref['path']).resolve()
        require(path.is_relative_to(EVIDENCE.resolve()),'Receipt escaped evidence: '+str(index))
        require(digest(path.read_bytes())==ref['sha256'],'Compressed receipt mismatch: '+str(index))
        checksum=hashlib.sha256()
        # Gzip verifies its CRC. Hash the complete stream without allocating a
        # second enormous JSON document; the writer's JSON encoding is tested.
        with gzip.open(path,'rb') as stream:
            for block in iter(lambda:stream.read(65536),b''):checksum.update(block)
        require(checksum.hexdigest()==ref['uncompressed_sha256'],'Receipt payload mismatch: '+str(index));archives+=1
    bundle=ROOT/'build/universal';combined=validate_bundle(bundle);manifest=read(bundle/'build.json')
    planner_lock=ROOT/'tools/mycelium-overlays/source-lock.json'
    require(manifest['planner_lock_sha256']==digest(planner_lock.read_bytes()),'Combined build uses a different compiler pin')
    for name,expected in read(planner_lock)['files'].items():require(digest((planner_lock.parent/name).read_bytes())==expected,'Pinned compiler file changed: '+name)
    zip_hash=combined['zip_sha256'];rows=[]
    for version in PROFILES:
        output=ROOT/'build'/('java-'+version);static=check(output,quiet=True)
        for kind,folder,prefix in [('data','datapack','data/'),('resource','resourcepack','assets/')]:
            actual={n:d for n,d in pack_hashes(output/folder).items() if n.startswith(prefix)}
            require(actual==manifest['effective_sha256'][version][kind],'Combined/per-target bytes differ: '+version+' '+kind)
        index=EVIDENCE/(('universal-backend-' if version=='26.3' else 'universal-')+version+'.json');game=bound(index)
        require(game.get('passed') is True and game['combined_zip_sha256']==zip_hash,'Current combined artifact not tested: '+version)
        if version=='26.3':
            require(len(game['checks'])==15,'Incomplete stock-client backend probes')
            require(game['datapack_sha256']==pack_hashes(output/'datapack'),'Backend source adapter mismatch')
        else:require(len(game['checks'])==50 and len(game.get('focused_shuffle',[]))==2,'Incomplete full/focused combined suite: '+version)
        require(all(c.get('passed') is True for c in game['checks']+game.get('focused_shuffle',[])),'Failed engine check: '+version)
        rows.append({'minecraft':version,'test_scope':'idle stock-client context and RCON backend probes; no new native-input/full-protocol claim' if version=='26.3' else 'same combined ZIP:50 broad engine checks plus2 whole-instance shuffle regressions','checks':len(game['checks']),'focused_shuffle_checks':len(game.get('focused_shuffle',[])),'receipt':index.name,'receipt_sha256':digest(index.read_bytes()),'static_checks':static['passed']})
    for suffix,total,version,module in [('-rider',78,'1.20.6','rider'),('-numbers',12,'1.21.11','numbers')]:
        selected=ROOT/('build/universal'+suffix);result=validate_bundle(selected)
        require(result['cards']==total,'Wrong combined subset count')
        require(read(selected/'build.json')['planner_lock_sha256']==digest(planner_lock.read_bytes()),'Subset compiler pin changed')
        game=bound(EVIDENCE/f'universal-subset-{version}-{module}.json')
        require(game.get('passed') and game['combined_zip_sha256']==result['zip_sha256'],'Combined subset artifact not tested: '+module)
    for version in ['1.20.6','1.21.11','26.3']:
        native=bound(EVIDENCE/f'{"universal" if version=="26.3" else "modrinth-above"}-client-{version}.json')
        require(native.get('passed') and native['combined_zip_sha256']==zip_hash,'Current stock resource proof missing: '+version)
        require(digest((EVIDENCE/native['client_log']).read_bytes())==native['client_log_sha256'],'Stock client log changed')
    for version in ['1.20.6','1.21.3','1.21.11','26.1.2']:
        quiet=bound(EVIDENCE/f'quiet-{version}.json')
        require(quiet.get('passed') and quiet.get('combined_zip_sha256')==zip_hash and len(quiet['checks'])>=15,'Current quiet integration suite missing: '+version)
    for version in ['1.20.6','1.21.11','26.1.2']:
        refinement=bound(EVIDENCE/f'refinement-{version}.json')
        require(refinement.get('passed') and refinement.get('combined_zip_sha256')==zip_hash and len(refinement['checks'])==16 and all(c.get('passed') for c in refinement['checks']),'Current delayed-input/surface/carrier regressions missing: '+version)
    native_input=bound(EVIDENCE/'native-refinement-1.21.11.json')
    require(native_input.get('passed') and len(native_input['checks'])==2,'Historical stock-client input checks missing')
    current_native_input=native_input.get('combined_zip_sha256')==zip_hash
    dispatch=bound(EVIDENCE/'client-dispatch-26.3.json')
    require(dispatch.get('passed') and dispatch.get('combined_zip_sha256')==zip_hash and len(dispatch['checks'])==2,'Current real client Use-dispatch probes missing')
    from client_dispatch_lab import JAVA
    expected_agent=digest(JAVA.encode('utf-8'));agent_path=ROOT.parents[2]/'commonground-microvoxels-runtime/tarot/client-dispatch-agent'/expected_agent/'probe.jar'
    require(dispatch['test_agent']['source_sha256']==expected_agent and digest(agent_path.read_bytes())==dispatch['test_agent']['jar_sha256'],'Client test-agent provenance changed')
    for screenshot in native_input.get('screenshots',[]):require(digest((EVIDENCE/screenshot['path']).read_bytes())==screenshot['sha256'],'Native input capture changed')
    for version,seed in [('1.20.6',8191),('1.21.11',671083),('26.1.2',104729)]:
        game_fuzz=bound(EVIDENCE/f'fuzz-{version}-{seed}.json')
        require(game_fuzz.get('passed') and game_fuzz.get('combined_zip_sha256')==zip_hash and game_fuzz.get('steps_requested')==300 and game_fuzz.get('audits')==301,'Current whole-item state-machine fuzzing missing: '+version)
    for version in ['1.20.6','26.1.2']:
        negative=bound(EVIDENCE/f'payload-{version}-fuzz-65537.json')
        require(negative.get('passed') and len(negative['checks'])==105 and negative['datapack_sha256']==pack_hashes(ROOT/('build/java-'+version)/'datapack'),'Malformed fuzzing does not match this adapter: '+version)
        expansion=bound(EVIDENCE/f'expansion-{version if version=="1.20.6" else "1.21.11"}.json')
        require(expansion.get('passed') and len(expansion['checks'])==5,'Saved-item content expansion checks missing')
        catalogue=bound(EVIDENCE/f'catalogue-budget-{version}.json')
        require(catalogue.get('passed') and catalogue['checks'][0]['catalogue']==1024,'Maximum-catalogue legacy promotion evidence missing: '+version)
    module_contract=bound(EVIDENCE/'module-contract.json')
    require(module_contract.get('passed') and digest((EVIDENCE/module_contract['log']).read_bytes())==module_contract['log_sha256'] and digest((ROOT/'tools'/module_contract['test_source']).read_bytes())==module_contract['test_source_sha256'],'Module authoring contract tests are stale')
    resources=bound(EVIDENCE/'resource-compatibility.json')
    require(resources.get('passed') and resources['combined_zip_sha256']==zip_hash,'Current Modrinth resource resolution proof missing')
    for version in ['1.20.6','1.21.11']:
        for order in ['above','below']:
            native=bound(EVIDENCE/f'modrinth-{order}-client-{version}.json')
            require(native.get('passed') and native['combined_zip_sha256']==zip_hash and len(native['external_resources'])==3,'Current real resource-stack load proof missing')
            require(digest((EVIDENCE/native['client_log']).read_bytes())==native['client_log_sha256'],'Resource-stack client log changed')
    for name in ['pressure-1.21.11.json','payload-1.21.11.json']:
        extra=bound(EVIDENCE/name)
        require(extra.get('passed') and extra['datapack_sha256']==pack_hashes(ROOT/'build/java-1.21.11/datapack'),'Supplemental receipt does not match final pack: '+name)
    require(read(EVIDENCE/'pressure-1.21.11.json')['checks'][-1]['unique_items']==144,'Pressure did not conserve all instances')
    upgrades=['upgrade-probe-1.21.5.json','upgrade-probe-26.3.json','deck-upgrade-1.20.6-to-1.21.11.json']
    require(all(bound(EVIDENCE/name).get('passed') for name in upgrades),'Forward world upgrade evidence missing')
    gameplay_upgrade=read(EVIDENCE/upgrades[-1])
    require(gameplay_upgrade['source_datapack_sha256']==pack_hashes(ROOT/'build/java-1.20.6/datapack') and gameplay_upgrade['target_datapack_sha256']==pack_hashes(ROOT/'build/java-1.21.11/datapack'),'Gameplay upgrade did not test current adapters')
    for version in ['1.21.11','26.3']:require(bound(EVIDENCE/f'metadata-modern-client-{version}.json').get('passed'),'Typed metadata bridge not tested')
    visual=read(EVIDENCE/'native-upgraded-art-1.21.11.json')
    require(visual.get('passed') and digest((EVIDENCE/visual['screenshot']).read_bytes())==visual['screenshot_sha256'],'Upgraded artwork capture changed')
    for name in ['build-integrity.json','universal-integrity.json']:
        integrity=read(EVIDENCE/name)
        require(integrity['passed'] and digest((EVIDENCE/integrity['log']).read_bytes())==integrity['log_sha256'],'Integrity evidence mismatch: '+name)
        require(digest((ROOT/'tools'/integrity['test_source']).read_bytes())==integrity['test_source_sha256'],'Integrity test source changed: '+name)
    result={'verified_on':datetime.now(timezone.utc).date().isoformat(),'scope':'Exact listed vanilla Java releases; forward-upgrade probes are separately scoped. No arbitrary downgrade, unlisted release, Bedrock or Folia certification.','combined_archive':{'path':'../build/universal/Physical-Cards-Universal.zip','sha256':zip_hash,'sha1':manifest['zip_sha1'],'cards':manifest['cards'],'roles':['datapack','resourcepack'],'modules':manifest['modules']},'targets':rows,'selected_module_tests':['universal-subset-1.20.6-rider.json','universal-subset-1.21.11-numbers.json'],'forward_world_upgrades':upgrades,'queue_stress':'pressure-1.21.11.json','historical_native_controls':{'receipt':'native-physical-1.21.11.json','scope':'Mouse/keyboard controls and original artwork before native-storage revision; not a new native-input claim'},'stock_client_resources':['universal-client-'+v+'.json' for v in ['1.20.6','1.21.11','26.3']],'malformed_payloads':'payload-1.21.11.json','adversarial_build_tests':['build-integrity.json','universal-integrity.json'],'saved_receipt_archives_verified':archives,'source_files_pinned':len(read(ROOT/'source-lock.json')['files'])}
    result['stock_client_resources']=['modrinth-above-client-1.20.6.json','modrinth-above-client-1.21.11.json','universal-client-26.3.json']
    result['quiet_integration']=['quiet-'+v+'.json' for v in ['1.20.6','1.21.3','1.21.11','26.1.2']]
    result['interaction_refinement']=['refinement-'+v+'.json' for v in ['1.20.6','1.21.11','26.1.2']]
    result['native_input_refinement']={'receipt':'native-refinement-1.21.11.json','current_archive':current_native_input,'scope':'Actual OS Use-key evidence for this exact archive.' if current_native_input else 'Historical OS Use-key evidence for its recorded archive; current coverage uses the separately labelled client dispatch probe, not a new keyboard/mouse pass.'}
    result['client_use_dispatch']={'receipt':'client-dispatch-26.3.json','scope':dispatch['scope'],'test_agent':dispatch['test_agent']}
    result['stateful_fuzz']=[f'fuzz-{v}-{s}.json' for v,s in [('1.20.6',8191),('1.21.11',671083),('26.1.2',104729)]]
    result['malformed_fuzz']=['payload-'+v+'-fuzz-65537.json' for v in ['1.20.6','26.1.2']]
    result['future_content']={'saved_world_expansion':['expansion-1.20.6.json','expansion-1.21.11.json'],'maximum_catalogue':['catalogue-budget-1.20.6.json','catalogue-budget-26.1.2.json'],'authoring_contract':'module-contract.json'}
    result['resource_pack_compatibility']={'resolution':'resource-compatibility.json','stock_client_stacks':[f'modrinth-{order}-client-{v}.json' for v in ['1.20.6','1.21.11'] for order in ['above','below']],'scope':'Hash-pinned Faithful 32x, Bare Bones and 3D Default. Legacy 3D Default requires Physical Cards above it; lower priority is an explicitly recorded conflict, not a compatibility pass.'}
    result['release_presentation']=['pack.png','INSTALL.txt','CREDITS.txt']
    (EVIDENCE/'compatibility.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'targets':len(rows),'receipt_archives_verified':archives,'selected_module_builds':2,'combined_zip_sha256':zip_hash}))

if __name__=='__main__':main()
