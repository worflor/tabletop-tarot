"""Two players operate identically positioned tables in different dimensions."""
import time

from game_lab import VanillaLane, card_items, card_keys, deck_item


def run(lane):
    peer = VanillaLane(lane.version)
    peer.game_port, peer.rcon_port, peer.password = lane.game_port, lane.rcon_port, lane.password
    checks = []

    def wait(label, predicate):
        deadline = time.monotonic() + 20
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError(label)
            time.sleep(.05)

    def yes(command):
        return 'Test passed' in lane.rcon(command)

    def in_world(world, command):
        return f'execute in minecraft:{world} run {command}'

    # A position filter makes @e dimension-scoped; `execute in` alone does not.
    display = '@e[type=minecraft:item_display,tag=tarot.placed,distance=0..,limit=1]'
    touch = '@e[type=minecraft:interaction,tag=tarot.touch,distance=0..]'
    try:
        peer.start_player('TarotPeer')
        actors = [(lane, 'overworld', 'numbers', 12, 'numbers/number-1'),
                  (peer, 'the_nether', 'rider', 78, 'rider/major-0')]
        for client, world, module, size, key in actors:
            name = client.player_name
            lane.rcon(in_world(world, f'tp {name} 0.5 80 0.5 0 20'))
            assert f'minecraft:{world}' in lane.rcon(f'data get entity {name} Dimension')
            wait('Destination chunks did not load', lambda w=world: yes(in_world(w, 'execute if loaded 0 80 0')))
            # Enclosed rooms avoid terrain, lava and other dimension fixtures.
            response = lane.rcon(in_world(world, 'fill -4 79 -4 4 86 5 minecraft:bedrock'))
            assert 'filled' in response.lower(), response
            lane.rcon(in_world(world, 'fill -3 80 -3 3 85 4 minecraft:air'))
            lane.rcon(in_world(world, 'setblock 0 80 2 minecraft:stone'))
            lane.rcon(in_world(world, f'tp {name} 0.5 80 0.5 0 20'))
            lane.rcon('clear '+name)
            lane.rcon(f'execute as {name} run function tarot:give/{module}')
            lane.rcon('gamemode survival '+name)
            lane.rcon('deop '+name)
            client.client_action('hold', slot=0)
            client.wait_state(lambda s, m=module, n=size: len(card_keys(deck_item(s, m))) == n, 'complete dimension deck')
        # Both requests enter the normal player queue in different dimensions.
        for client, *_ in actors:
            client.client_action('chat', text='/trigger tarot.action set 5')
        targets = []
        for client, world, module, size, key in actors:
            client.wait_state(lambda s, m=module, n=size: len(card_keys(deck_item(s, m))) == n-1, 'dimension blind deal')
            wait('Wrong dimension or card identity', lambda w=world, k=key: yes(in_world(w,
                f'execute if data entity {display} item.components."minecraft:custom_data".tarot{{key:"{k}"}}')))
            observed = []
            def interaction_arrived():
                observed[:] = [e for e in client.client_action('entities')['entities'] if e['name'] == 'interaction']
                return len(observed) == 1
            wait('Client did not receive its own dimension hitbox', interaction_arrived)
            targets.append(observed[0])
        assert targets[0]['uuid'] != targets[1]['uuid']
        for _, world, *_ in actors:
            wait('Placement motion did not settle in '+world, lambda w=world: not yes(in_world(w,
                'execute if entity @e[type=minecraft:item_display,tag=tarot.moving,distance=0..]')))
        peer.client_action('touch', uuid=targets[1]['uuid'], attack=False)
        wait('Nether flip did not complete', lambda: 'has 1 ' in lane.rcon(in_world('the_nether', f'scoreboard players get {display} tarot.face')))
        wait('Nether flip motion did not finish', lambda: not yes(in_world('the_nether',
            'execute if entity @e[type=minecraft:item_display,tag=tarot.moving,distance=0..]')))
        assert yes(in_world('the_nether', f'execute if data entity {display} {{transformation:{{translation:[0f,0f,0f],right_rotation:[0f,1f,0f,0f]}}}}'))
        assert 'has 0 ' in lane.rcon(in_world('overworld', f'scoreboard players get {display} tarot.face'))
        before = lane.rcon(in_world('the_nether', f'data get entity {display} Rotation')).split('following entity data:')[-1]
        peer.client_action('sneak', enabled=True)
        try:
            wait('Nether sneak intent or cooldown not ready', lambda: yes('execute as TarotPeer if predicate tarot:is_sneaking') and
                 'has 0 ' in lane.rcon('scoreboard players get TarotPeer tarot.cool'))
            peer.client_action('touch', uuid=targets[1]['uuid'], attack=False)
            wait('Nether rotation did not complete', lambda: lane.rcon(in_world('the_nether', f'data get entity {display} Rotation')).split('following entity data:')[-1] != before)
        finally:
            peer.client_action('sneak', enabled=False)
        lane.client_action('hold', slot=1)
        lane.client_action('touch', uuid=targets[0]['uuid'], attack=True)
        first = lane.wait_state(lambda s: len(card_items(s)) == 1, 'overworld pickup')
        assert card_items(first)[0][1]['key'] == 'numbers/number-1'
        assert not yes(in_world('overworld', f'execute if entity {display}'))
        assert yes(in_world('the_nether', f'execute if entity {display}'))
        checks.append({'name':'cross_dimension_deal_flip_rotate_and_pickup_isolation', 'passed':True,
                       'dimensions':['overworld','the_nether'], 'tables_share_coordinates':True,
                       'distinct_hitboxes':True, 'non_operator_players':True,
                       'placement_and_flip_motion_settled_in_each_dimension':True})
        lane.rcon(in_world('the_nether', 'setblock 0 80 2 minecraft:air'))
        wait('Nether support loss did not release the card', lambda: not yes(in_world('the_nether', f'execute if entity {display}')))
        lane.rcon(in_world('the_nether', 'tp TarotPeer 0.5 80 2.5'))
        second = peer.wait_state(lambda s: len(card_items(s)) == 1, 'nether dropped-item pickup')
        assert card_items(second)[0][1]['key'] == 'rider/major-0'
        for client, world, module, size, _ in actors:
            snapshot = client.client_action('snapshot')
            assert len(card_keys(deck_item(snapshot, module))) + len(card_items(snapshot)) == size
            assert not yes(in_world(world, f'execute if entity {touch}'))
        checks.append({'name':'cross_dimension_support_loss_and_custody_conservation', 'passed':True,
                       'numbers_cards':12, 'rider_cards':78, 'cards_conserved':90})
        return checks
    finally:
        peer.stop()
        lane.commands.extend(peer.commands)
        lane.client_lines.extend(peer.client_lines)
