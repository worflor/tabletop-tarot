"""Reviewed generators layered over the byte-pinned original engine."""
import json


def descending_shuffle(capacity=128):
    """Partially evaluate descending Fisher-Yates into bounded literal ranges.

    For an n-item prefix, step k swaps k-1 with a uniform j in [0,k-1].
    The product of those independent probabilities is 1/n!; repeated items
    remain distinct indices. Each helper continues at k-1, ending at two.
    """
    result = {'stack/shuffle_start.mcfunction':
              '$function tarot:stack/shuffle_step/$(size)\n'}
    for size in range(2, capacity+1):
        index = size-1
        lines = [f'execute store result storage tarot:shuffle j int 1 run random value 0..{index}',
                 f'function tarot:stack/swap_{index} with storage tarot:shuffle']
        if size > 2:
            lines.append(f'function tarot:stack/shuffle_step/{size-1}')
        result[f'stack/shuffle_step/{size}.mcfunction'] = '\n'.join(lines)+'\n'
    # The original forward loop stopped at capacity-2; the descending loop
    # needs the final index too. Keep the same small-integer permutation.
    index = capacity-1
    result[f'stack/swap_{index}.mcfunction'] = '\n'.join([
        f'data modify storage tarot:shuffle swap set from storage tarot:shuffle indices[{index}]',
        f'$data modify storage tarot:shuffle indices[{index}] set from storage tarot:shuffle indices[$(j)]',
        '$data modify storage tarot:shuffle indices[$(j)] set from storage tarot:shuffle swap',
    ])+'\n'
    return result


def native_validation(cards, implicit_count):
    """Factor independent per-row invariants without accepting mixed invalid rows."""
    lines = [
        'execute if data storage tarot:transaction main.components."minecraft:custom_data".tarot.cards run return 0',
        'data modify storage tarot:runtime cards set value []',
        'data modify storage tarot:runtime cards set from storage tarot:transaction main.components."minecraft:charged_projectiles"',
        'execute store result score #size tarot.roll run data get storage tarot:runtime cards',
        'execute unless score #size tarot.roll matches 0..128 run return 0',
        '# Every row must independently be a singleton supported carrier.',
        'data modify storage tarot:validation carriers set from storage tarot:runtime cards',
    ]
    for carrier in ['minecraft:paper', 'minecraft:carrot_on_a_stick']:
        for count in ['1', '1b']:
            lines.append('data remove storage tarot:validation carriers[{id:"'+carrier+'",count:'+count+'}]')
    if implicit_count:
        lines.append('execute if data storage tarot:validation carriers[].count run return 0')
        for carrier in ['minecraft:paper', 'minecraft:carrot_on_a_stick']:
            lines.append('data remove storage tarot:validation carriers[{id:"'+carrier+'"}]')
    lines += [
        'execute unless data storage tarot:validation {carriers:[]} run return 0',
        'data remove storage tarot:validation carriers',
        '# Independently require a recognized key, matching module and card kind on every same-source row.',
        'data modify storage tarot:validation unchecked set from storage tarot:runtime cards',
    ]
    for card in cards:
        pattern = {'components': {'minecraft:custom_data': {'tarot': {
            'kind':'card', 'key':card['key'], 'module':card['module']}}}}
        lines.append('data remove storage tarot:validation unchecked['+json.dumps(pattern,separators=(',',':'))+']')
    lines.append('execute if data storage tarot:validation {unchecked:[]} run scoreboard players set #valid tarot.sys 1')
    return '\n'.join(lines)+'\n'
