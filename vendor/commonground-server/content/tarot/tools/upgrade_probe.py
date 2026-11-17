"""Observe vanilla DataFixer on saved nested items versus opaque custom NBT, using copied disposable worlds."""
import argparse,json,pathlib,shutil,time
from game_lab import VanillaLane,RUNTIME,ROOT,write_json
from runtime import printed_item

def snbt(value):
    # Legacy SNBT quotes escape only quote/backslash; JSON's \n escape is not accepted there.
    if isinstance(value,str):return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
    if isinstance(value,dict):return '{'+','.join(snbt(k)+':'+snbt(v) for k,v in value.items())+'}'
    if isinstance(value,list):return '['+','.join(snbt(v) for v in value)+']'
    if isinstance(value,bool):return 'true' if value else 'false'
    return str(value)

def main(target):
    run=RUNTIME/'upgrade-probes'/str(time.time_ns());old=VanillaLane('1.20.6');new=VanillaLane(target)
    for lane,label in [(old,'source'),(new,'target')]:
        lane.server_dir=run/label;lane.world_dir=lane.server_dir/lane.world_name
    result={'source':'1.20.6','target':target,'scope':'Actual official vanilla saved-world upgrade on a copy; no game modifications or external NBT conversion','checks':[]}
    def read(lane,path):
        response=lane.rcon('data get block 0 -60 0 '+path)
        if 'following block data: ' not in response:raise AssertionError(response)
        return response.split('following block data: ',1)[1]
    try:
        old.download_server();old.start();old.rcon('forceload add 0 0');old.rcon('setblock 0 -60 0 minecraft:chest')
        catalogue=json.loads((old.pack.parent/'catalogue.json').read_text(encoding='utf-8'));keys=['rider/major-0','numbers/number-1','rider/major-19'];items=[]
        for i,key in enumerate(keys):
            card=next(c for c in catalogue['cards'] if c['key']==key);item=printed_item(card,'1.20.6');components=item['components']
            components['minecraft:custom_name']=json.dumps({'text':'Keepsake '+str(i)+' — café "moon"','color':'gold'},ensure_ascii=False)
            components['minecraft:lore']=[json.dumps({'text':'Line one\nLine two','italic':False})]
            components['minecraft:repair_cost']=i+3;components['minecraft:enchantments']={'levels':{'minecraft:unbreaking':1}}
            components['minecraft:custom_data']['private_note']={'serial':i,'text':'Keep "this"\n谢谢'};items.append(item)
        fixtures=old.world_dir/'datapacks/tarot/data/tarot/item_modifiers/upgrade_probe';fixtures.mkdir(parents=True)
        variants=[('minecraft:charged_projectiles',items),('minecraft:container',[{'slot':i,'item':item} for i,item in enumerate(items)]),('minecraft:custom_data',{'opaque':items})]
        for slot,(component,value) in enumerate(variants):
            (fixtures/f'case_{slot}.json').write_text(json.dumps({'function':'minecraft:set_components','components':{component:value}},ensure_ascii=False),encoding='utf-8')
        old.rcon('reload')
        for slot in range(3):
            old.rcon(f'item replace block 0 -60 0 container.{slot} with minecraft:carrot_on_a_stick')
            response=old.rcon(f'item modify block 0 -60 0 container.{slot} tarot:upgrade_probe/case_{slot}')
            if 'Replaced' not in response:raise AssertionError('Source fixture rejected: '+response)
        result['before']=read(old,'Items');old.rcon('save-all flush');old.stop()
        shutil.copytree(old.world_dir,new.world_dir)
        new.download_server();new.start();new.rcon('forceload add 0 0');result['after']=read(new,'Items')
        for slot,component in [(0,'minecraft:charged_projectiles'),(1,'minecraft:container')]:
            base=f'Items[{{Slot:{slot}b}}].components."{component}"'
            new.rcon('execute store result score #upgrade_probe tarot.sys run data get block 0 -60 0 '+base)
            if 'has 3 ' not in new.rcon('scoreboard players get #upgrade_probe tarot.sys'):raise AssertionError('Nested items lost')
            for i in range(3):
                path=base+f'[{i}]'+('.item' if slot==1 else '')
                expected={'components':{'minecraft:custom_name':{'text':'Keepsake '+str(i)+' — café "moon"'},'minecraft:repair_cost':i+3,'minecraft:custom_data':{'tarot':{'key':keys[i]},'private_note':{'text':'Keep "this"\n谢谢'}}}}
                new.rcon('data modify storage tarot:upgrade current set from block 0 -60 0 '+path)
                if 'Test passed' not in new.rcon('execute if data storage tarot:upgrade current'+json.dumps(expected,ensure_ascii=True,separators=(',',':'))):raise AssertionError('Native item annotation/order not migrated')
                if 'Test passed' not in new.rcon('execute if data block 0 -60 0 '+path+'.components."minecraft:custom_model_data".floats'):raise AssertionError('Legacy model component did not migrate')
            result['checks'].append({'name':component+'_native_items_migrated_in_order_with_annotations','passed':True})
        if 'Test passed' in new.rcon('execute if data block 0 -60 0 Items[{Slot:2b}].components."minecraft:custom_data".opaque[0].components."minecraft:custom_name".text'):raise AssertionError('Opaque negative control unexpectedly fixed')
        result['checks'].append({'name':'opaque_custom_data_remains_old_schema_negative_control','passed':True});result['passed']=True
    except Exception as error:result['passed']=False;result['error']=repr(error);raise
    finally:
        old.stop();new.stop();result['commands']=old.commands+new.commands;result['processes']=old.starts+new.starts
        write_json(ROOT/f'content/tarot/evidence/upgrade-probe-{target}.json',result)
    print(json.dumps({'target':target,'passed':True}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',default='1.21.5');main(p.parse_args().target)
