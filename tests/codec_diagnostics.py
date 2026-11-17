"""Recognize only the deliberate payload lab's native ItemStack rejections."""
import hashlib
import re
from collections import Counter


def expected_payload_rejection(line, world, seed, count):
    prefix = re.fullmatch(
        r"[A-Za-z0-9_.$]+\['Armor Stand'/\d+, l='ServerLevel\[" + re.escape(world) +
        r"\]', x=-?\d+\.\d+, y=-188\.00, z=-?\d+\.\d+\]: Failed to decode value '(.*)' from field 'equipment': (.*)", line)
    if not prefix:
        return None
    equipment, reason = prefix.groups()
    marks = set(re.findall(r'seed-(\d+)-case-(\d+)', equipment))
    source = 'fixed'
    if marks:
        if len(marks) != 1:
            return None
        actual_seed, index = map(int, next(iter(marks)))
        if actual_seed != seed or not 0 <= index < count:
            return None
        source = f'seed-{seed}-case-{index}'
        mutation = index % 12
        if mutation == 6:
            valid = f'"minecraft:fuzz_unknown_component":{{keep:{index}}}' in equipment and reason.startswith("No component with type: 'minecraft:fuzz_unknown_component'")
        elif mutation == 7:
            value = re.search(r'"minecraft:max_stack_size":(-?\d+)', equipment)
            valid = value and int(value[1]) in (0, -1, 1000) and reason.startswith(f'Value must be within range [1;99]: {value[1]} missed input:')
        elif mutation == 8:
            valid = f'"minecraft:repair_cost":{{unexpected:[{{number:{index}}},{{deep:[0b]}}]}}' in equipment and reason.startswith('Not a number missed input:')
        elif mutation == 9:
            valid = f'"minecraft:custom_name":{{text:{{not_text:[{index}]}}}}' in equipment and reason.startswith('Failed to parse either.') and f'Not a list: {{text:{{not_text:[{index}]}}}}' in reason and 'No matching codec found missed input:' in reason
        else:
            valid = False
    elif '"minecraft:max_stack_size":0' in equipment:
        source += '-stack-limit'
        valid = reason.startswith('Value must be within range [1;99]: 0 missed input:')
    elif '"minecraft:custom_name":{text:{invalid:[1,2]}}' in equipment:
        source += '-text'
        valid = reason.startswith('Failed to parse either.') and 'Not a list: {text:{invalid:[1,2]}}' in reason and 'No matching codec found missed input:' in reason
    elif '"minecraft:physical_cards_unknown_component":1b' in equipment:
        source += '-unknown-component'
        valid = reason.startswith("No component with type: 'minecraft:physical_cards_unknown_component'")
    else:
        valid = False
    if not valid:
        return None
    return {'fixture': source, 'reason': reason.partition(' missed input:')[0],
            'line_sha256': hashlib.sha256(line.encode()).hexdigest()}


def split_payload_diagnostics(text, world, seed, count):
    retained, diagnostics = [], []
    repetitions = Counter()
    for number, line in enumerate(text.splitlines(), 1):
        if 'Failed to decode value' not in line:
            retained.append(line)
            continue
        known = expected_payload_rejection(line, world, seed, count)
        if known is None:
            raise AssertionError(f'Unexpected codec diagnostic at server log line {number}')
        repetitions[known['fixture']] += 1
        if repetitions[known['fixture']] > (1 if known['fixture'].startswith('fixed-') else 3):
            raise AssertionError('Repeated codec diagnostics exceeded the fixture action count')
        diagnostics.append({'line': number, **known})
    return '\n'.join(retained), diagnostics
