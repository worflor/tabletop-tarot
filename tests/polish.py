"""Small transaction-outcome matrix on a real dedicated server and two stock clients."""
from __future__ import annotations
import hashlib
import json
import math
import re
import time
from pathlib import Path


def run_polish(ver, rcon, xdo, work):
    cmd=rcon.cmd
    folder=work/'server/world/datapacks/peer-fixtures/data/peer'/('functions' if ver=='1.20.6' else 'function')
    folder.mkdir(parents=True, exist_ok=True)
    for action in ('deal','shuffle'):
        (folder/(action+'_probe.mcfunction')).write_text(f'execute as Alice at @s run function tarot:input/{action}\n')
    cmd('reload'); time.sleep(0.5)
    cmd('fill -5 -61 -4 5 -61 10 grass_block')
    cmd('fill -5 -60 -4 5 -54 10 air')
    cmd('fill -3 -60 4 3 -60 6 oak_planks')
    cmd('clear Alice'); cmd('clear Bob')
    cmd('tp Bob 0.5 -60 7.5 180 12')
    pitch=math.degrees(math.atan2(0.62,3))
    cmd(f'tp Alice 0.5 -60 1.5 0 {pitch}')
    xdo(':91','key','1'); time.sleep(0.3)
    results=[]

    def count(kind, tag):
        cmd(f'execute store result score #probe_count tarot.sys if entity @e[type=minecraft:{kind},tag={tag}]')
        return rcon.score('#probe_count','tarot.sys')

    def probe(name, action="deal"):
        cmd('scoreboard players set Alice tarot.cool 0')
        cmd('tick freeze')
        try:
            before=cmd('data get entity Alice SelectedItem')
            reply=cmd('debug function peer:'+action+'_probe')
            match=re.search(r'(debug-trace-[^\s]+\.txt)',reply)
            assert match, f'Transaction trace was not produced: {reply}'
            trace=(work/'server/debug'/match.group(1)).read_text()
            (work/(name+'.trace.txt')).write_text(trace)
            after=cmd('data get entity Alice SelectedItem')
            sound='shuffle' if action=='shuffle' else 'place'
            sounds=sum(bool(re.search(r'\[F\]\s+tarot:sound/'+sound+r'\b',line)) for line in trace.splitlines())
            return before,after,sounds
        finally:
            cmd('tick unfreeze')

    # A valid old deck with conflicting history reaches placement, then refuses the commit.
    # This exercises real preservation policy, not a patched production function.
    item='carrot_on_a_stick[minecraft:custom_data={tarot:{kind:"deck",module:"numbers",cards:[{key:"numbers/number-1"}],migration_history:{owner_note:"keep"}}}]'
    cmd('item replace entity Alice weapon.mainhand with '+item)
    before,after,sounds=probe('refused-commit')
    assert rcon.score('#placed','tarot.sys')==1 and rcon.score('#committed','tarot.sys')==0
    assert before==after, 'Rejected migration changed the held deck'
    assert count('item_display','tarot.placed')==0 and count('interaction','tarot.touch')==0
    assert sounds==0, 'Rolled-back deal emitted a successful placement sound'
    results.append({'case':'conflicting migration history','outcome':'unchanged; provisional display and hitbox removed; no success feedback'})
    print('  [P1] Refused commit preserves the exact old deck, cleans provisional entities and stays quiet',flush=True)

    # Same one-card legacy payload, with only the conflicting field removed, must succeed.
    item=item.replace(',migration_history:{owner_note:"keep"}','')
    cmd('item replace entity Alice weapon.mainhand with '+item)
    _,_,sounds=probe('accepted-commit')
    assert rcon.score('#committed','tarot.sys')==1 and sounds==1
    assert count('item_display','tarot.placed')==1 and count('interaction','tarot.touch')==1
    cmd('execute store result score #probe_size tarot.sys run data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
    assert rcon.score('#probe_size','tarot.sys')==0
    deadline=time.monotonic()+5
    while rcon.score('Alice','tarot.cool')>0:
        if time.monotonic()>=deadline:
            raise AssertionError('Accepted-deal input cooldown did not drain')
        time.sleep(0.05)
    xdo(':91','click','1')
    deadline=time.monotonic()+5
    while True:
        cmd('execute store result score #probe_size tarot.sys run data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
        if rcon.score('#probe_size','tarot.sys')==1 and count('item_display','tarot.placed')==0:
            break
        if time.monotonic()>=deadline:
            raise AssertionError('Real-client pickup did not conserve the accepted card')
        time.sleep(0.05)
    cmd('execute store result score #probe_size tarot.sys run data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
    assert rcon.score('#probe_size','tarot.sys')==1 and count('item_display','tarot.placed')==0
    results.append({'case':'same legacy card without conflicting history','outcome':'committed once; placement feedback once; real-client pickup conserved the card'})
    print('  [P2] Accepted migration emits one placement cue and a real-client pickup conserves its card',flush=True)

    # A spatial refusal is distinct from a preservation refusal, but also cannot report success.
    _,_,sounds=probe('first-native-deal')
    assert sounds==1 and count('item_display','tarot.placed')==1
    cmd('loot replace entity Alice hotbar.0 loot peer:baseline')
    cmd('execute store result score #probe_size tarot.sys run data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
    assert rcon.score('#probe_size','tarot.sys')==12, 'Occupied-table control requires the non-empty released deck'
    before,after,sounds=probe('occupied-destination')
    assert before==after and sounds==0 and count('item_display','tarot.placed')==1
    assert rcon.score('#placed','tarot.sys')==-1, 'The occupied-table case must reach the dedicated occupancy refusal'
    results.append({'case':'occupied tabletop','outcome':'held native deck unchanged; existing card retained; no success feedback'})
    print('  [P3] Occupied-table refusal preserves both decks/table state and emits no success cue',flush=True)

    # Shuffle has the same commit boundary: an attempted reorder is not a committed reorder.
    pair='carrot_on_a_stick[minecraft:custom_data={tarot:{kind:"deck",module:"numbers",cards:[{key:"numbers/number-1"},{key:"numbers/number-2"}],migration_history:{owner_note:"keep"}}}]'
    cmd('item replace entity Alice weapon.mainhand with '+pair)
    before,after,sounds=probe('refused-shuffle','shuffle')
    assert rcon.score('#committed','tarot.sys')==0 and before==after
    assert sounds==0, 'Rejected shuffle emitted a successful shuffle cue'
    results.append({'case':'shuffle with conflicting migration history','outcome':'exact deck unchanged; no shuffle feedback'})
    pair=pair.replace(',migration_history:{owner_note:"keep"}','')
    cmd('item replace entity Alice weapon.mainhand with '+pair)
    _,_,sounds=probe('accepted-shuffle','shuffle')
    assert rcon.score('#committed','tarot.sys')==1 and sounds==1
    raw=cmd('data get entity Alice SelectedItem.components."minecraft:charged_projectiles"')
    assert sorted(re.findall(r'key: "([^"]+)"',raw))==['numbers/number-1','numbers/number-2']
    results.append({'case':'shuffle without conflicting history','outcome':'two card identities conserved; shuffle feedback once'})
    print('  [P4] Shuffle feedback follows the same rejection/commit boundary and preserves both identities',flush=True)

    pack=work/'server/world/datapacks/Tabletop-Tarot.zip'
    (work/'polish-result.json').write_text(json.dumps({'minecraft':ver,'archive_sha256':hashlib.sha256(pack.read_bytes()).hexdigest(),
        'status':'pass','cases':results,'scope':'server transaction traces plus one real-client pickup; no claim about subjective sound quality'},indent=2)+'\n')
