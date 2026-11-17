"""Derive common recipe ingredients from exact official server registry reports."""
import json,pathlib,subprocess
from game_lab import ROOT,RUNTIME,VanillaLane,sha
from profiles import PROFILES

def main():
    common=None;sources={}
    for version,pin in PROFILES.items():
        lane=VanillaLane(version);lane.download_server();folder=RUNTIME/'official-reports'/version;folder.mkdir(parents=True,exist_ok=True)
        report=folder/'generated/reports/registries.json'
        if not report.exists():
            with (folder/'datagen.log').open('wb') as output:
                subprocess.run([str(lane.java),'-Xmx768M','-XX:ActiveProcessorCount=2','-DbundlerMainClass=net.minecraft.data.Main','-jar',str(lane.server_jar),'--reports','--output',str(folder/'generated')],cwd=folder,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=180)
        items=set(json.loads(report.read_text(encoding='utf-8'))['minecraft:item']['entries'])
        common=items if common is None else common&items
        sources[version]={'server_sha1':pin['server_sha1'],'manifest_sha1':pin['manifest_sha1'],'registry_report_sha256':sha(report),'items':len(items)}
        print(json.dumps({'minecraft':version,'items':len(items),'common_so_far':len(common)}),flush=True)
    result={'schema':1,'scope':'Item IDs present in official registry reports of every explicitly supported Java target','sources':sources,'ingredients':sorted(common)}
    (ROOT/'content/tarot/core/vanilla-recipe-ingredients.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
