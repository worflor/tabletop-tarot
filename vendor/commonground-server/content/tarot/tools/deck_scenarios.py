"""Extra real-server conservation scenarios for the Tarot vanilla game lab."""
from __future__ import annotations

try:
    from game_lab import card_items, card_keys, deck_item, tarot_data
except ImportError:  # imported as content.tarot.tools.deck_scenarios
    from .game_lab import card_items, card_keys, deck_item, tarot_data


def run_extra(lane) -> list[dict]:
    checks: list[dict] = []

    def record(name, **details):
        checks.append({"name": name, "passed": True, **details})

    def snap():
        return lane.client_action("snapshot")

    def trigger(value):
        return lane.client_action("chat", text=f"/trigger tarot.action set {value}")["snapshot"]

    def slot_name(slot):
        if 36 <= slot <= 44:
            return f"hotbar.{slot - 36}"
        if slot == 45:
            return "weapon.offhand"
        return f"inventory.{slot - 9}"

    def fresh(module="numbers"):
        lane.rcon("clear TarotLab")
        lane.player_function(f"tarot:give/{module}")
        state = lane.wait_state(lambda s:deck_item(s,module) is not None,module+" deck")
        deck = deck_item(state, module)
        if not deck:
            raise AssertionError(f"{module} deck missing after give")
        lane.client_action("hold", slot=deck["slot"] - 36 if deck["slot"] >= 36 else deck["slot"])
        return snap()

    # Draw all twelve Numbers cards. Each returned key must be distinct and
    # the deck must become empty without creating or refilling a card.
    state = fresh("numbers")
    deck = deck_item(state, "numbers")
    original = card_keys(deck)
    if len(original) != 12 or len(set(original)) != 12:
        raise AssertionError(f"Numbers deck identity invalid: {len(original)} cards")
    drawn: list[str] = []
    for _ in range(12):
        state = trigger(1)
        deck = deck_item(state, "numbers")
        visible = [data.get("key") for _, data in card_items(state, "numbers")]
        if not deck or len(card_keys(deck)) != 12 - len(drawn) - 1:
            raise AssertionError("Numbers draw did not remove exactly one deck card")
        newly_drawn = set(visible) - set(drawn)
        if len(newly_drawn) != 1:
            raise AssertionError("Numbers draw did not produce one new physical identity")
        drawn.extend(newly_drawn)
    if len(set(drawn)) != 12 or set(drawn) != set(original):
        raise AssertionError("Numbers draw sequence duplicated or lost a card")
    state = trigger(1)
    empty_deck = deck_item(state, "numbers")
    if not empty_deck or card_keys(empty_deck) or len(card_items(state, "numbers")) != 12:
        raise AssertionError("Exhausted deck refilled or emitted another card")
    record("numbers_draw_without_replacement_and_exhaustion", count=12, unique=len(set(drawn)), deck_empty=True)

    # Shuffle only the remaining physical cards after four draws.
    state = fresh("numbers")
    before = set(card_keys(deck_item(state, "numbers")))
    drawn_before = set()
    for _ in range(4):
        state = trigger(1)
        drawn_before = {data.get("key") for _, data in card_items(state, "numbers")}
    before_shuffle = set(card_keys(deck_item(state, "numbers")))
    if len(before_shuffle) != 8 or before_shuffle | drawn_before != before:
        raise AssertionError("pre-shuffle remaining/drawn membership is invalid")
    initial_order=card_keys(deck_item(state,"numbers"))
    for _ in range(3):
        state=trigger(2)
        if card_keys(deck_item(state,"numbers"))!=initial_order:break
    else:raise AssertionError("Remaining-card shuffle was a no-op in three attempts")
    after_shuffle = card_keys(deck_item(state, "numbers"))
    if len(after_shuffle) != 8 or len(set(after_shuffle)) != 8 or set(after_shuffle) != before_shuffle:
        raise AssertionError("shuffle changed remaining card membership")
    record("shuffle_remaining_membership", remaining=8, drawn=4, membership_preserved=True)

    # A stack accepts a second physical copy of a printed identity.
    state = fresh("numbers")
    state = trigger(1)
    deck = deck_item(state, "numbers")
    drawn_card = card_items(state, "numbers")[0][0]
    key = tarot_data(drawn_card)["key"]
    lane.rcon(f"item replace entity TarotLab weapon.offhand from entity TarotLab {slot_name(drawn_card['slot'])}")
    lane.rcon(f"item replace entity TarotLab {slot_name(drawn_card['slot'])} with minecraft:air")
    state = trigger(3)
    returned_deck = deck_item(state, "numbers")
    if len(card_keys(returned_deck)) != 12 or key not in card_keys(returned_deck) or state.get("offhand"):
        raise AssertionError("offhand return failed to restore the physical card")
    record("offhand_return_conserves_card", key=key, deck_count=12, offhand_consumed=True)

    snbt_key = key.replace('\\', '\\\\').replace('"', '\\"')
    lane.rcon(f'give TarotLab minecraft:paper[minecraft:custom_data={{tarot:{{kind:"card",module:"numbers",key:"{snbt_key}"}}}}] 1')
    state = lane.wait_state(lambda s:any(data.get('key')==key for _,data in card_items(s,'numbers')),'second physical copy fixture')
    duplicate = next((item for item, data in card_items(state, "numbers") if data.get("key") == key), None)
    if not duplicate:
        raise AssertionError("duplicate return fixture could not be created")
    lane.rcon(f"item replace entity TarotLab weapon.offhand from entity TarotLab {slot_name(duplicate['slot'])}")
    lane.rcon(f"item replace entity TarotLab {slot_name(duplicate['slot'])} with minecraft:air")
    state = trigger(3)
    duplicate_deck = deck_item(state, "numbers")
    if len(card_keys(duplicate_deck)) != 13 or card_keys(duplicate_deck)[:2]!=[key,key] or state.get("offhand"):
        raise AssertionError("Second physical copy did not enter the top of the stack")
    record("duplicate_printed_identity_is_a_second_card", key=key, deck_count=13)

    # Printed packs may be mixed without changing the cards themselves.
    lane.rcon("clear TarotLab")
    lane.player_function("tarot:give/numbers")
    lane.player_function("tarot:give/rider")
    state = snap()
    number_deck = deck_item(state, "numbers")
    rider_deck = deck_item(state, "rider")
    if not number_deck or not rider_deck:
        raise AssertionError("could not create both modules for mismatch scenario")
    lane.client_action("hold", slot=number_deck["slot"] - 36 if number_deck["slot"] >= 36 else number_deck["slot"])
    state = trigger(1)
    numbers_card = card_items(state, "numbers")[0][0]
    rider_deck = deck_item(state, "rider")
    lane.rcon(f"item replace entity TarotLab weapon.offhand from entity TarotLab {slot_name(numbers_card['slot'])}")
    lane.rcon(f"item replace entity TarotLab {slot_name(numbers_card['slot'])} with minecraft:air")
    lane.client_action("hold", slot=rider_deck["slot"] - 36 if rider_deck["slot"] >= 36 else rider_deck["slot"])
    before_wrong = card_keys(deck_item(snap(), "rider"))
    state = trigger(3)
    if card_keys(deck_item(state, "rider")) != [tarot_data(numbers_card)['key']]+before_wrong or state.get("offhand"):
        raise AssertionError("Mixed stack did not retain the other pack's card on top")
    record("mixed_modules_keep_printed_identity", deck="rider", card_module="numbers", total=79)

    # Persist a partially drawn deck through a chest transfer and datapack reload.
    state = fresh("numbers")
    state = trigger(1)
    state = trigger(1)
    expected = card_keys(deck_item(state, "numbers"))
    deck = deck_item(state, "numbers")
    pos = state["position"]
    x, y, z = int(pos["x"]) + 2, int(pos["y"]) + 1, int(pos["z"]) + 2
    lane.rcon(f"setblock {x} {y} {z} minecraft:chest replace")
    lane.rcon(f"item replace block {x} {y} {z} container.0 from entity TarotLab {slot_name(deck['slot'])}")
    lane.rcon(f"item replace entity TarotLab {slot_name(deck['slot'])} with minecraft:air")
    lane.rcon("reload")
    lane.rcon(f"item replace entity TarotLab {slot_name(deck['slot'])} from block {x} {y} {z} container.0")
    lane.rcon(f"item replace block {x} {y} {z} container.0 with minecraft:air")
    # Legacy protocol clients can lose the slot update while /reload reconfigures.
    # Reconnect to observe the server's saved inventory, not an optimistic model.
    from profiles import profile
    if profile(lane.version)['legacy_models']:
        lane.client_action('quit');lane.client_process.wait(timeout=10);lane.client_process=None
        lane.start_player()
    state = snap()
    restored = deck_item(state, "numbers")
    if not restored or card_keys(restored) != expected:
        raise AssertionError("chest/reload transfer changed the physical deck contents")
    record("chest_transfer_and_reload_persistence", remaining=len(expected), membership_preserved=True)
    return checks
