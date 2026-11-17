"""Test-only Minecraft camera and native Screenshot.grab bridge; no render replacement."""
import hashlib,json,os,pathlib,subprocess,time,uuid,zipfile
from game_lab import RUNTIME,sha

JAVA=r'''import com.google.gson.*;
import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import net.minecraft.client.*;
import net.minecraft.world.level.levelgen.Heightmap;
public final class CardsPhotoAgent {
 static final Gson JSON=new Gson(); static Path folder;
 public static void premain(String argument,Instrumentation instrumentation){
  folder=Path.of(argument);Thread worker=new Thread(()->{while(true){try{
   Path file=folder.resolve("request.json");if(!Files.isRegularFile(file)){Thread.sleep(40);continue;}
   JsonObject request=JSON.fromJson(Files.readString(file),JsonObject.class);Files.delete(file);
   CompletableFuture<Void> done=new CompletableFuture<>();Minecraft mc=Minecraft.getInstance();
   mc.execute(()->{try{run(mc,request,done);}catch(Throwable error){reply(Map.of("error",error.toString()));done.complete(null);}});done.get(60,TimeUnit.SECONDS);
  }catch(Throwable error){reply(Map.of("error",error.toString()));try{Thread.sleep(100);}catch(InterruptedException stop){return;}}}},"cards-photo-native-bridge");worker.setDaemon(true);worker.start();
 }
 static void run(Minecraft mc,JsonObject request,CompletableFuture<Void> done){
  if(mc.player==null||mc.level==null)throw new IllegalStateException("World not ready");
  String action=request.get("action").getAsString();Map<String,Object> answer=new LinkedHashMap<>();answer.put("action",action);
  switch(action){
   case "prepare" -> {if(!mc.gui.hud.isHidden())mc.gui.hud.toggle();mc.options.bobView().set(false);mc.options.fovEffectScale().set(0.0);mc.options.gamma().set(0.7);mc.options.fov().set(55);}
   case "look" -> {float yaw=request.get("yaw").getAsFloat(),pitch=request.get("pitch").getAsFloat();mc.player.setYRot(yaw);mc.player.setXRot(pitch);mc.player.yRotO=yaw;mc.player.xRotO=pitch;}
   case "fov" -> mc.options.fov().set(request.get("value").getAsInt());
   case "probe" -> {answer.put("position",List.of(mc.player.getX(),mc.player.getY(),mc.player.getZ()));answer.put("biome",mc.level.getBiome(mc.player.blockPosition()).unwrapKey().map(k->k.identifier().toString()).orElse("unknown"));answer.put("hud_hidden",mc.gui.hud.isHidden());answer.put("size",List.of(mc.getWindow().getWidth(),mc.getWindow().getHeight()));}
   case "terrain" -> {List<Object> points=new ArrayList<>();int cx=(int)mc.player.getX(),cz=(int)mc.player.getZ();for(int x=cx-30;x<=cx+30;x+=5)for(int z=cz-30;z<=cz+30;z+=5)points.add(List.of(x,mc.level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,x,z),z));answer.put("points",points);}
   case "shot" -> {String name=request.get("name").getAsString();if(!name.matches("[a-z0-9_-]+"))throw new IllegalArgumentException("Screenshot name");Screenshot.grab(mc.gameDirectory,name+".png",mc.gameRenderer.mainRenderTarget(),1,message->{answer.put("message",message.getString());answer.put("path",mc.gameDirectory.toPath().resolve("screenshots").resolve(name+".png").toString());reply(answer);done.complete(null);});return;}
   default -> throw new IllegalArgumentException("Unknown photo action");
  }
  reply(answer);done.complete(null);
 }
 static void reply(Object value){try{Path temporary=folder.resolve("response.tmp");Files.writeString(temporary,JSON.toJson(value));Files.move(temporary,folder.resolve("response.json"),StandardCopyOption.REPLACE_EXISTING);}catch(Exception error){error.printStackTrace();}}
}'''

def prepare(base):
    from visual_client import prepare as prepare_official
    from lab_environment import java_runtime
    prepare_official('26.3');cache=RUNTIME/'client-26.3';command=json.loads((cache/'launch.json').read_text(encoding='utf-8'));cp=command[command.index('-cp')+1]
    digest=hashlib.sha256(JAVA.encode()).hexdigest();folder=RUNTIME/'photo-agent'/digest;folder.mkdir(parents=True,exist_ok=True);source=folder/'CardsPhotoAgent.java';source.write_text(JAVA,encoding='utf-8');jar=folder/'photo.jar'
    if not jar.exists():
        classes=folder/'classes';classes.mkdir(exist_ok=True);compiler=RUNTIME.parent/'java/bin/javac.exe'
        args=folder/'compile.args';args.write_text('\n'.join('"'+str(v).replace('\\','\\\\').replace('"','\\"')+'"' for v in ['-encoding','UTF-8','-cp',cp,'-d',classes,source])+'\n',encoding='utf-8')
        subprocess.run([str(compiler),'@'+str(args)],check=True)
        with zipfile.ZipFile(jar,'w',zipfile.ZIP_DEFLATED) as out:
            out.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nPremain-Class: CardsPhotoAgent\n\n')
            for path in classes.rglob('*.class'):out.write(path,path.relative_to(classes).as_posix())
    control=base/'photo-control';control.mkdir(parents=True)
    command.insert(1,'-javaagent:'+str(jar)+'='+str(control));command.insert(1,'-XX:ActiveProcessorCount=2')
    return command,control,{'source_sha256':digest,'jar_sha256':sha(jar),'scope':'Camera/options and Minecraft native Screenshot.grab only; no class transforms or render replacement'}

def send(control,action,**args):
    response=control/'response.json';response.unlink(missing_ok=True);temporary=control/'request.tmp';temporary.write_text(json.dumps({'action':action,**args}),encoding='utf-8');temporary.replace(control/'request.json')
    until=time.monotonic()+60
    while not response.exists():
        if time.monotonic()>until:raise TimeoutError('Photo client action '+action)
        time.sleep(.05)
    result=json.loads(response.read_text(encoding='utf-8'))
    if 'error' in result:raise RuntimeError(result['error'])
    return result
