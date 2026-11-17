"""Two actual protocol players, shared tick inputs, and custody transfer."""
import time
from game_lab import VanillaLane,deck_item,card_keys,card_items

def run_multiplayer(lane):
    peer=VanillaLane(lane.version)
    peer.game_port,peer.rcon_port,peer.password=lane.game_port,lane.rcon_port,lane.password
    checks=[]
    try:
        peer.start_player('TarotPeer')
        for name,module in [('TarotLab','rider'),('TarotPeer','numbers')]:
            lane.rcon(f'clear {name}')
            lane.rcon(f'execute as {name} run function tarot:give/{module}')
        lane.client_action('hold',slot=0);peer.client_action('hold',slot=0)
        # One vanilla command pulses both real players in the same tick.
        lane.rcon('scoreboard players set @a tarot.action 1')
        for name in ['TarotLab','TarotPeer']:
            until=time.monotonic()+10
            while 'has 0 ' not in lane.rcon(f'scoreboard players get {name} tarot.action'):
                if time.monotonic()>until:raise TimeoutError('Two-player queue did not drain')
                time.sleep(.05)
        main=lane.wait_state(lambda s:deck_item(s,'rider') and len(card_keys(deck_item(s,'rider')))==77,'main two-player draw')
        other=peer.wait_state(lambda s:deck_item(s,'numbers') and len(card_keys(deck_item(s,'numbers')))==11,'peer two-player draw')
        for state,module,count in [(main,'rider',77),(other,'numbers',11)]:
            deck=deck_item(state,module);cards=card_items(state,module)
            if not deck or len(card_keys(deck))!=count or len(cards)!=1 or any(not k.startswith(module+'/') for k in card_keys(deck)):
                raise AssertionError('Shared-tick player state crossed decks or lost cards')
        checks.append({'name':'two_player_same_tick_isolation','passed':True,'rider_remaining':77,'numbers_remaining':11})
        # Transfer a partially used physical deck through the actual server inventory.
        expected=card_keys(deck_item(main,'rider'))
        lane.rcon('item replace entity TarotPeer hotbar.2 from entity TarotLab hotbar.0')
        lane.rcon('item replace entity TarotLab hotbar.0 with minecraft:air')
        peer.client_action('hold',slot=2);peer.wait_state(lambda s:s.get('held') and deck_item(s,'rider') is not None,'transferred deck visible');peer.client_action('use')
        other=peer.client_action('snapshot');main=lane.client_action('snapshot')
        deck=deck_item(other,'rider')
        if deck_item(main,'rider') or not deck or len(card_keys(deck))!=76 or not set(card_keys(deck))<set(expected) or len(card_items(other,'rider'))!=1:
            raise AssertionError('Transferred deck did not carry its independent persistent state')
        checks.append({'name':'two_player_deck_custody_transfer','passed':True,'remaining':76,'transfer':'vanilla item commands, followed by recipient right-click'})
    finally:
        peer.stop()
        lane.commands.append({'via':'peer-evidence','protocol_lines':peer.client_lines,'commands':peer.commands})
    return checks
