"""Invoke the real vanilla client Use dispatch on its game thread, with explicit instrumentation scope."""
import hashlib,json,pathlib,subprocess,time
from game_lab import ROOT,RUNTIME,sha,write_json
from lab_environment import java_runtime

JAVA=r'''import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
public final class CardUseProbe {
 public static void premain(String argument, Instrumentation instrumentation) {
  Path folder=Path.of(argument);
  Thread worker=new Thread(()->{while(true){try{
   Path request=folder.resolve("request.txt");
   if(!Files.exists(request)){Thread.sleep(25);continue;}
   String command=Files.readString(request,StandardCharsets.UTF_8).trim();Files.delete(request);
   Class<?> type=Class.forName("net.minecraft.client.Minecraft");Object client=type.getMethod("getInstance").invoke(null);
   type.getMethod("execute",Runnable.class).invoke(client,(Runnable)()->{try{
    if(!command.equals("use"))throw new IllegalArgumentException("Unsupported probe request");
    if(type.getField("player").get(client)==null)throw new IllegalStateException("Player not ready");
    Method pick=type.getDeclaredMethod("pick",float.class);pick.setAccessible(true);pick.invoke(client,1.0f);
    Object hit=type.getField("hitResult").get(client);
    if(hit==null||!hit.getClass().getMethod("getType").invoke(hit).toString().equals("BLOCK"))throw new IllegalStateException("Expected real client block hit");
    Method use=type.getDeclaredMethod("startUseItem");use.setAccessible(true);use.invoke(client);
    reply(folder,"ok: actual Minecraft.startUseItem on client thread");
   }catch(Throwable error){reply(folder,"error: "+error);}});
  }catch(Throwable error){reply(folder,"error: "+error);try{Thread.sleep(100);}catch(InterruptedException ignored){return;}}}},"PhysicalCards-client-dispatch-probe");
  worker.setDaemon(true);worker.start();
 }
 private static void reply(Path folder,String value){try{
  Path temporary=folder.resolve("response.tmp");Files.writeString(temporary,value,StandardCharsets.UTF_8);
  Files.move(temporary,folder.resolve("response.txt"),StandardCopyOption.REPLACE_EXISTING);
 }catch(Exception error){error.printStackTrace();}}
}'''

def prepare(folder):
    digest=hashlib.sha256(JAVA.encode()).hexdigest();base=RUNTIME/'client-dispatch-agent'/digest;base.mkdir(parents=True,exist_ok=True)
    source=base/'CardUseProbe.java';source.write_text(JAVA,encoding='utf-8');jar=base/'probe.jar'
    if not jar.exists():
        classes=base/'classes';classes.mkdir(exist_ok=True);binary=java_runtime(21).parent
        subprocess.run([str(binary/'javac.exe'),'--release','21','-d',str(classes),str(source)],check=True)
        manifest=base/'MANIFEST.MF';manifest.write_text('Manifest-Version: 1.0\nPremain-Class: CardUseProbe\n\n',encoding='ascii')
        subprocess.run([str(binary/'jar.exe'),'--create','--file',str(jar),'--manifest',str(manifest),'-C',str(classes),'.'],check=True)
    control=folder/'dispatch-control';control.mkdir(exist_ok=True)
    for name in ['request.txt','response.txt']: (control/name).unlink(missing_ok=True)
    return '-javaagent:'+str(jar)+'='+str(control),control,{'source_sha256':digest,'jar_sha256':sha(jar),'mechanism':'Reflection only; no class transformation or OS input injection'}

def run(lane,control,agent):
    result={'minecraft':lane.version,'scope':'Instrumented vanilla client: actual Minecraft.startUseItem dispatched on its main thread, including vanilla block/offhand priority; no OS-keyboard/mouse claim','combined_zip_sha256':sha(lane.archive),'test_agent':agent,'checks':[]}
    functions=lane.world_dir/'datapacks/tarot/data/tarot/function/lab/client_dispatch';functions.mkdir(parents=True,exist_ok=True)
    fixture=functions/'fixture.mcfunction'
    fixture.write_text('''clear TarotVisual
kill @e[type=minecraft:item_display,tag=tarot.placed]
kill @e[type=minecraft:interaction,tag=tarot.touch]
execute as TarotVisual run function tarot:give/rider
data modify storage tarot_lab:dispatch sun set from entity TarotVisual SelectedItem.components."minecraft:charged_projectiles"[{components:{"minecraft:custom_data":{tarot:{key:"rider/major-19"}}}}]
data modify storage tarot_lab:dispatch sun.Slot set value 4b
setblock 4 -60 0 minecraft:chest
data modify block 4 -60 0 Items set value []
data modify block 4 -60 0 Items append from storage tarot_lab:dispatch sun
item replace entity TarotVisual weapon.mainhand from block 4 -60 0 container.4
data modify block 4 -60 0 Items set value []
setblock 4 -60 0 minecraft:air
item replace entity TarotVisual weapon.offhand with minecraft:air
fill -2 -59 1 2 -57 3 minecraft:air
fill -2 -60 1 2 -60 3 minecraft:oak_planks
tp TarotVisual 0.5 -60 0.5 0 20
gamemode survival TarotVisual
scoreboard players set TarotVisual tarot.cool 0
data modify storage tarot_lab:dispatch expected set from entity TarotVisual SelectedItem.components
''',encoding='utf-8')
    def wait(command,predicate,label):
        until=time.monotonic()+20
        while True:
            response=lane.rcon(command)
            if predicate(response):return response
            if time.monotonic()>until:raise TimeoutError(label+': '+response)
            time.sleep(.1)
    def use():
        response=control/'response.txt';response.unlink(missing_ok=True)
        (control/'request.txt').write_text('use',encoding='utf-8');until=time.monotonic()+20
        while not response.exists():
            if time.monotonic()>until:raise TimeoutError('Client-thread Use dispatch did not answer')
            time.sleep(.05)
        value=response.read_text(encoding='utf-8')
        if not value.startswith('ok:'):raise AssertionError(value)
    def equal(path):
        lane.rcon('data modify storage tarot_lab:dispatch compare set from '+path)
        lane.rcon('execute store success score #dispatch_changed tarot.sys run data modify storage tarot_lab:dispatch compare set from storage tarot_lab:dispatch expected')
        if 'has 0 ' not in lane.rcon('scoreboard players get #dispatch_changed tarot.sys'):raise AssertionError('Client Use changed card components')
    try:
        lane.rcon('reload')
        for offhand in [False,True]:
            wait('function tarot:lab/client_dispatch/fixture',lambda r:'Executed' in r or 'Running function' in r,'dispatch fixture reload completion')
            wait('data get entity TarotVisual SelectedItem.components."minecraft:custom_data"',lambda r:'rider/major-19' in r,'actual factory Sun fixture')
            lane.rcon('deop TarotVisual')
            if offhand:lane.rcon('item replace entity TarotVisual weapon.offhand with minecraft:torch 64')
            # Real client frames receive the inventory and camera updates before
            # startUseItem checks the actual renderer's block hit result.
            time.sleep(1)
            use()
            if offhand:
                wait('execute if block 0 -59 2 minecraft:torch',lambda r:'Test passed' in r,'actual client offhand torch placement')
                if 'Test passed' in lane.rcon('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]'):raise AssertionError('Occupied offhand also placed the card')
                equal('entity TarotVisual SelectedItem.components')
            else:
                wait('execute if entity @e[type=minecraft:item_display,tag=tarot.placed]',lambda r:'Test passed' in r,'actual client card placement')
                if 'No items' not in lane.rcon('clear TarotVisual #tarot:card_carriers[minecraft:custom_data~{tarot:{kind:"card"}}] 0'):raise AssertionError('Placed card remained in inventory')
                equal('entity @e[type=minecraft:item_display,tag=tarot.placed,limit=1] item.components')
            name='client_dispatch_offhand_places_torch_without_also_placing_card' if offhand else 'client_dispatch_places_exact_card_with_clear_offhand'
            result['checks'].append({'name':name,'passed':True});print(name,flush=True)
        result['passed']=True
    except Exception as e:result['passed']=False;result['error']=repr(e);raise
    finally:
        result['commands']=list(lane.commands);write_json(ROOT/f'content/tarot/evidence/client-dispatch-{lane.version}.json',result)
