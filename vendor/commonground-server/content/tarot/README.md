# Tabletop Tarot

78+ illustrated cards to shuffle, draw, trade and lay on your own tables. You decide what they mean.

**First release:** [1.0.0 staged publication handoff](../../staging/releases/tabletop-tarot/1.0.0/README.md), including the renamed combined ZIP, checksums, licenses and listing copy. [Packaging verification](evidence/tabletop-packaging.json) binds it to the tested runtime and art. [Promotional gallery](../../docs/gallery/tabletop-tarot/1.0.0/README.md) uses native Minecraft captures and the woflo_ skin. Staged does not mean published to Modrinth.

Cartomancy's illustrated cards as ordinary, tangible vanilla Java items. No mod,
plugin, spells, powers, progression or enforced tarot rules. Install the datapack
for handling and the matching resource pack for the original artwork and 3D
front/back/edge models.

## Modules

| Module | Contents |
| --- | --- |
| Core (always included) | Ordered stacks of individual cards, shuffle, top draw/insertion, tabletop placement/turning/pickup and shared presentation |
| `rider` (default) | All 78 Rider–Waite–Smith cards, their original backs, names and canonical metadata |
| `numbers` (default) | All 12 Numbers cards: 1–9, 11, 22 and 33, with their separate oracle identity |

Both card modules ship by default. The build selects which content is included;
it does not require players to install several independently ordered datapacks.
Install one combined master ZIP in both vanilla pack locations. Existing
items from an omitted module should be stored before changing that world's build;
omitting a module removes its handlers and art, and never converts it to another deck.

## Install and play

Use **`Tabletop-Tarot-Universal.zip`** on every supported release. Adapters cover **1.20.6,
1.21.1, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.8, 1.21.10, 1.21.11,
26.1.2 and 26.3**. See verification below for each test scope. Other releases
and Bedrock are not covered; a newer pack-format number alone is insufficient.

1. Put `Tabletop-Tarot-Universal.zip` in the world's `datapacks/` directory.
2. Put **the same file** in the client's `resourcepacks/` directory and enable it.
3. Run `/reload` or restart the world.

Minecraft selects the matching data and resource overlays itself. One download
serves both roles; vanilla still has separate server/world and client install
locations. A server can host that same ZIP and offer it using `resource-pack`
and `resource-pack-sha1` in `server.properties`. Calculate the hash with
`Get-FileHash -Algorithm SHA1 ./Tabletop-Tarot-Universal.zip`, or use the
build folder’s `Tabletop-Tarot-Universal.zip.sha1` sidecar.
The ZIP contains no mod JAR or shared runtime. Exact-version ZIPs remain available
for diagnostics and integrations that prefer them.

Craft a deck using a ring of **eight paper** around **an ink sac** (Rider) or
**lapis lazuli** (Numbers). These recipes are the datapack's acquisition design,
not copied magic mechanics from Cartomancy.

- **Stack in main hand:** use takes the **top card**. A newly crafted stack
  follows the original source pack's order; randomness comes from shuffling.
- **Sneak-use:** shuffle the remaining cards. With a card in the offhand,
  sneak-use instead puts **that individual card on top**.
- **Card in main hand:** use places it **face-down** on the aimed flat surface.
  No offhand band is needed. Sneak-use avoids opening a workstation
  when its vanilla block interaction would otherwise take priority. Aim at the
  top face: sides, undersides and the empty half of slabs do not place cards.
- **On a placed card:** use turns it over; sneak-use rotates it 45°; hit picks
  it up. There are no upright/reversed labels, readings or effects.
- `/trigger tarot.action set 1` draws, `2` shuffles, `3` puts the offhand card on
  top, and `4` places the main-hand card. The placement fallback works without
  carrying a stack; it also supports untouched older paper-based cards.
- Ordinary trading, chests, **Q dropping**, and item frames retain vanilla
  behavior. Dropping does not silently become permanent placement. Drawing or
  retrieving a placed card needs a free inventory slot.

Keep the offhand clear for physical use, except for other marked cards/bands.
Ordinary occupied offhands pause card handling so using a torch, food or shield
does not also move a card. Vanilla block interactions still take priority. While
riding a pig, use the trigger controls: vanilla use can boost the pig instead.
Triggers work with any offhand or mount and do not activate its vanilla item.

Operators can use `/function tarot:give/rider`, `/function tarot:give/numbers`
and `/function tarot:help`. Player actions need no operator permissions.
Routine handling failures use a quiet actionbar hint instead of chat.
Hidden ingredient advancements teach the ordinary crafting book when paper and
the corresponding ink/lapis are present. There is no login message, automatic
item grant, visible advancement or mandatory tutorial. Card and band tooltips
carry short handling hints; successful placement does not post chat instructions.

The combined ZIP includes its icon, `INSTALL.txt` and source-manifest credits.
The icon uses the selected module's original pixel plates without repainting.
It contains no downloaded third-party resource-pack files.

Contents live on the **stack item**, as an ordered native item-list component. Each entry retains the complete serialized
card, including its name, lore and other existing components. Returning and
redrawing a marked card preserves those details. Mixed Rider/Numbers stacks,
partial stacks and repeated printed identities are allowed. Two copies of The
Sun are two physical cards; there is no collection-completion rule. A band holds
at most **128 cards**, a technical work bound. Empty bands stay empty.

Stack silhouettes thin as cards leave. A plain retaining band remains at zero;
the visible printed back follows the actual top card's pack. Presentation updates
preserve a player's stack name and notes. Shuffle permutes whole instances and
never restores missing cards. Simultaneous physical/trigger inputs deal once.

Placed cards retain their pose through restart and hold their own actual item.
Their mounted interaction entity addresses that exact card, avoiding nearest-card
pickup. Support removal releases the same item into ordinary falling/pickup
physics. Surface checks cover loaded cards within 48 blocks of players. Cards
need a little clear space for reliable targeting; coincident placement is rejected
without consuming the held card. Supported surfaces include common flat wood,
stone, wool/work blocks and top/bottom slabs. Unusual shapes are not inferred
from their artwork. The generated `table_surface` block tag can admit additional
full-height flat blocks.

The server command budget must be at least the vanilla default **65536**;
handling pauses with feedback below that value. The setting is
`maxCommandChainLength` through 1.21.10 and
`minecraft:max_command_sequence_length` on later adapters. The pack does not
change it. A round-robin queue admits at most eight player/table gestures per
tick, including at most **two costly stack operations**. Eight separate surface
checks per tick handle support changes. Deferred stack input retains its captured action and complete held-item snapshot.
Changing the band or the card being returned cancels the request; releasing Shift
after capture does not reinterpret it. Modifiers are sampled when the server first
observes the use statistic, so a complete press/release between server ticks cannot
be reconstructed; trigger 2 is the explicit shuffle control. This
keeps a crowded table from consuming an unbounded command chain; large
arrangements and busy servers can take several ticks to settle.

## Build a selected master pack

From the repository root, Python 3 with `content/tarot/requirements.txt` installed, and Java 17+ on PATH for the build-time planner:

```powershell
python -B content/tarot/tools/universal.py
python -B content/tarot/tools/universal.py --modules rider
python -B content/tarot/tools/universal.py --modules numbers
python -B -O content/tarot/tools/universal.py --check content/tarot/build/universal
```

The default output is `build/universal/Tabletop-Tarot-Universal.zip`, containing
all 90 cards. Selected variants go under `build/universal-rider/` and
`build/universal-numbers/`. The builder also retains expanded per-target packs,
ZIPs and catalogues under `build/java-VERSION[-MODULE]/`.

The pinned [Mycelium overlay planner](tools/mycelium-overlays/source-lock.json)
is a build-time compiler extension; its complete source archive and licences ship
beside it. It derives exact formats and overlay metadata from Mycelium's era table.
The builder rejects format drift against the official game pins, keeps runtime
functions out of the common root, shares byte-identical assets, and resolves the
actual ZIP for each target. Every effective data/asset byte must match the checked
per-target build. Equal formats cannot carry conflicting content. Fixed ZIP
metadata makes repeated builds reproducible on the same toolchain. Builds stage
and validate before replacing the last good output. No installed Minecraft
profile, live world or Cartomancy checkout is modified.

## Source and limits

`modules/*/pack.json` and `deck.json` retain Cartomancy's pack/sidecar split:
canonical card identity and content stay separate from plate presentation.
`structureRef` retains each source slot; Numbers is not shoehorned into tarot
suits. The canonical source packs and PNGs are preserved byte-for-byte. Runtime
keys use a module plus the source card ID. Generated textures pad the original
pixels without resampling. Card proportions, thickness and display transforms
follow Cartomancy's physical slab; the band has authored thickness variants.

`source-lock.json` records exact Git blobs and SHA-256s checked against private
Cartomancy remote commit `f990fcf610f0a2676e0f29b1231760e08332a167`, using a
read-only local checkout. The public Cartomancy repository is not the asset source.
Original metadata and attribution travel with the modules unchanged. The owner's
explicit distribution grant is [MIT for code and CC BY 4.0 for original artwork](LICENSE.md),
with the public-domain Rider illustrations credited separately. Both full license
texts and the attribution notice ship inside every generated pack. To refresh, explicitly run the read-only importer
with a selected remote ref; the ordinary build requires no GitHub access.

Loose falling items use **vanilla physics**, including hazards and despawn rules;
deliberately placed cards persist. There is no custom flutter, mod shader,
foil/wear simulation, spread UI or enforced tarot game. Placed models show actual
front/back orientation and rotation, with quiet local paper sounds. This is not
a reproduction of Cartomancy's custom renderer or a Folia certification.

New cards and bands use an unbreakable carrot-on-a-stick carrier with its maximum
durability component explicitly removed. They cannot enter vanilla tool-repair
crafting, and cards cannot
substitute for paper in vanilla crafting, while ordinary paper recipes are left
alone. This does not forbid another datapack from deliberately adding recipes
that accept the carrier. The pack never rewrites vanilla recipes or ordinary items.
Existing paper cards remain readable. Drawing, returning or placing one upgrades
its carrier while preserving its name, lore, custom data and other components;
the explicit singleton-stack override becomes unnecessary on the new carrier.
An explicit older durability-capacity override is retained as
`custom_data.tarot.carrier_max_damage`; an existing conflicting history value
refuses the transfer without altering either item. Damage values and repair
history remain intact. Older bands also lose repair eligibility on successful
handling; untouched earlier items still need care around repair crafting.
Until that deliberate handling, an untouched old card remains paper and can still
be consumed by paper recipes. Old loose paper needs a band offhand for physical
use, or `/trigger tarot.action set 4`; new cards need neither.
The 1.20.6/1.21.1/1.21.3 resource overlays use legacy model overrides. Modern
ones use namespaced item definitions, plus a narrow paper/rod model-ID fallback
for cards created on older releases. Another pack replacing those vanilla item
model definitions can conflict.
Actual Modrinth fixtures include Faithful 32x, Bare Bones and 3D Default, with
version-specific downloads and hashes recorded in the resource compatibility
receipt. On legacy-model releases, put Tabletop Tarot **above** 3D Default;
its replacement rod model otherwise wins. Modern namespaced cards resolve in
either priority order. Compatibility with an arbitrary pack is not implied.

## Building on the pack

Keep integrations in your own namespace. Award a deck with
`execute as <player> run function tarot:give/rider` (or `numbers`), and invoke
`tarot:draw`, `tarot:shuffle`, `tarot:return` or `tarot:input/place` **as and at**
the player for the same guarded handling used by normal controls. These calls
are synchronous and retain the inventory-space, cooldown and command-budget checks.
Native loot tables `tarot:decks/rider` and `tarot:decks/numbers` back the grant
functions, so another pack can explicitly include a deck in its own rewards.
The shared tick queue bounds physical inputs; integrations should schedule or
bound their own direct function calls rather than bypassing that work budget.
Use normal recipe IDs `tarot:rider_deck` / `tarot:numbers_deck` and append flat,
full-height table blocks to `tarot:table_surface` without replacing the tag.

The item's own `minecraft:custom_data.tarot` marker distinguishes `kind:card`
from `kind:deck`; card keys remain `module/source_id`. Native
`minecraft:charged_projectiles` is the sole ordered deck payload. Preserve whole
item instances when writing an integration; do not recreate cards from their keys
or treat the carrier item alone as a card. Runtime storage, temporary entity tags
and scoreboards are internal scratch state. Functions outside the entry points
listed above are internal implementation details. New authored modules use the same `pack.json` / `deck.json` / PNG structure as
Cartomancy. Add a descriptor to `core/modules.json`, assign unused persistent
model IDs in `core/item-identities.json`, and rebuild. Python changes are not
needed for an ordinary card module. Modules default to included; `--modules`
selects a collection. Recipe ingredients must be distinct, must exist in all eleven pinned official
item registries, and cannot consume the card carrier. This catches invalid or
ambiguous recipes before export. `vanilla_recipe_contract.py` regenerates that
authoring contract from Mojang’s own registry reports when target pins change. Selected builds have deterministic, distinct
output paths even when several modules are combined.

Treat published module/card keys and model allocations as permanent. Card order
and source `index` changes never reassign artwork: the explicit identity contract
owns those allocations. Keep retired allocations reserved. Newly crafted decks
follow the current authored order; existing bands retain their actual saved items
and order. Additions do not refill or regenerate old decks. Each factory deck
contains 1–128 cards. The registered catalogue is capped at 1,024 cards to keep
command work bounded; larger catalogues need new engineering and measurements.
Canonical printed names are single-line; player names and notes retain their
normal Minecraft component behavior, including multiline notes.

A module omission leaves foreign/mixed contents unchanged and refuses handling;
reinstalling the matching module restores the same items. Removing or renaming
published content is a migration task. Integrations should use the public
functions above and keep their own data in their own namespace.

**Forward world upgrades:** cards live in Minecraft's native
`minecraft:charged_projectiles` item-list component on the band. It is an ordered
list of actual ItemStacks; vanilla's DataFixer traverses it when upgrading a
saved world. It grants no crossbow behaviour to the carrot-on-a-stick. Its
contents tooltip is hidden on the band, preserving other tooltip preferences.
There is one authoritative list, no duplicated opaque card payload or
Minecraft-version stamp. Complete components are checked before committing a
transfer. Exact prototype defaults that Minecraft omits when materializing an
item (such as repair cost zero) compare as their implicit vanilla values; other
components and player annotations still require equality. Modern resource overlays retain old model IDs so upgraded loose cards
also keep their artwork before being handled.

Older prototype key-only/opaque bands convert lazily when handled on a host that
can decode their original data. Unique row/item metadata stays in migration
notes; the live card components move into native storage. A conflicting existing
native component or undecodable payload is left unchanged. Convert old opaque
prototype decks **before** upgrading their world; they were not native items
when the earlier world was saved. Arbitrary world downgrades and unlisted future
releases are not claimed. Preserve backups and test a copy when upgrading or
removing a selected module.

## Verification and reproduction

Building needs Python 3, `pip install -r content/tarot/requirements.txt`, and
Java 17+ on PATH (or `TAROT_BUILD_JAVA`). Game tests additionally need Node.js
with npm, Java 21 and Java 25. Set `TAROT_JAVA_21` / `TAROT_JAVA_25` to the
corresponding executable if automatic discovery cannot find them. The locked
protocol observer installs only into the sibling runtime cache:

```powershell
python -B content/tarot/tools/bootstrap_lab.py
python -B content/tarot/tools/bootstrap_lab.py --check
```

Stock-client tests currently require Windows; server/protocol lanes are separate.
The native runner automatically downloads/hash-checks official client artifacts
and regenerates its launch command. To prepare them ahead of time, use
`bootstrap_lab.py --clients --versions 1.20.6 1.21.11 26.3`. No installed profile
is used. A fresh checkout must build the default and both selected-module packs
before the full release checks below. Their builds are:
`universal.py`, `universal.py --modules rider`, and `universal.py --modules numbers`.

The [accepted gameplay compatibility index](evidence/compatibility.json) binds the
original tested ZIP, effective per-target bytes and complete receipts. The
[Tabletop Tarot packaging proof](evidence/tabletop-packaging.json) binds the current
ZIP to that immutable baseline: all effective data/assets are identical on all
eleven targets. Only the title, install text, credits, license files and an inert
`data/tabletop_tarot/README.txt` marker change. That marker lets Modrinth detect
the root datapack role before its resource assets; no runtime is moved out of
the version overlays. The actual pinned Modrinth parser is exercised with Node.
Its inferred version range still needs the exact supported-version list from
`release.json`. No authenticated Modrinth upload is claimed.

Recheck the packaging with `python -B content/tarot/tools/verify_packaging.py`
(Node.js, Git history and network access for the pinned parser required).
`verify_release.py` routes packaging-only builds through this proof and preserves
the baseline receipts. Ten exact
protocol-supported releases run the **same ZIP** through 50 broad engine checks
plus two whole-instance shuffle regressions. These include non-operator Survival
crafting/use, all 90 printed cards drawn individually, annotated round trips,
mixed/repeated cards, malformed/overfull stacks, command budgets, real two-player
pickup races, supported surfaces, spacing, support loss and restart persistence.
Observer fixtures live in a separate loose pack and cannot override production.

26.3 has a narrower stock-client/RCON backend suite because the pinned protocol
observer does not implement protocol 777. It covers top draw, exact shuffle bags,
annotations, placement/flip/rotation/retrieval, support-loss pickup and explicit
count-two rejection. Default singleton counts omitted by ItemStackTemplate are
accepted. Its fifteen backend checks also exercise ingredient-based recipe discovery
and actual redstone-crafter repair attempts: ordinary rods craft, while card/card,
band/band and mixed pairs retain their complete input items.
Stock resource-loading receipts on 1.20.6, 1.21.11 and 26.3 cover the
combined archive; the earlier native mouse/keyboard screenshot records the same
physical controls before this storage revision, not a new input pass.

The [resource-stack capture](evidence/physical-cards-resource-stack-1.21.11.png)
records the earlier unenchanted factory Sun with Faithful 32x, Bare Bones and
3D Default enabled together. Its original desktop-helper failure remains
historical evidence. The earlier 1.21.11 OS-key checks retain their original archive binding.
The desktop controller’s JavaScript runtime failed during the newer pass. Current
26.3 checks instead use a small, reflection-only test agent to call Minecraft’s
actual raycast and Use dispatch on its main thread. Both clear-offhand placement
and vanilla offhand torch placement preserve the exact expected card. This is
client-engine integration evidence, explicitly not a new OS-input claim. The
agent is confined to the test cache and never ships in either pack.

Focused refinement receipts on 1.20.6, 1.21.11 and 26.1.2 check delayed Shift
release, hotbar/same-slot swaps, changed offhand cards, disconnected input cleanup,
occupied offhands, mounted trigger handling and positive/negative surface shapes.

The focused quiet-integration suite checks real crafting windows, recipe-book
discovery, direct loose-card input, paper substitution, all three tool-repair
combinations, legacy carrier upgrades and conflicting history. Legacy fixtures
carry unique names, quoted notes, damage, custom durability capacity
and repair history; the engine compares the resulting components against the
explicit preservation rules.

Saved-world probes copy official 1.20.6 worlds into 1.21.5 and 26.3, checking
ordered native items, names, multiline/quoted notes, repair history and model
components against an opaque-data negative control. A gameplay upgrade test
from 1.20.6 to 1.21.11 checks the shuffled Numbers deck, all twelve draws and the
marked card's annotations, an untouched 78-card Rider deck, and a loose card.
These are forward-upgrade evidence, separate from fresh-world compatibility.

The [native upgraded-card capture](evidence/native-upgraded-art-1.21.11.png)
shows the actual legacy-model Sun rendering on 1.21.11; its glint comes from a
retained test enchantment. Default cards are unenchanted.

The nine-player pressure suite continuously shuffles 128-card stacks while 144
unique tabletop cards lose support. It checks fair service, the two-heavy-action
and eight-maintenance budgets, and exact conservation. Its measured timing lives
in the receipt; this is not a universal 20 TPS guarantee. Malformed-codec probes
include native-storage collisions. Adversarial CLI tests reject corrupted ZIPs,
wrong overlay selection, differing legacy/modern range fields, changed compiler
pins and failed-preflight replacement of the last good build, including with
optimized Python.

```powershell
python -u -B content/tarot/tools/universal_matrix.py --workers 2
python -u -B content/tarot/tools/resource_compat_lab.py
python -u -B content/tarot/tools/polish_lab.py --stage quiet
python -u -B content/tarot/tools/polish_lab.py --stage resources
python -u -B content/tarot/tools/polish_lab.py --stage supplemental
python -u -B content/tarot/tools/polish_lab.py --stage refinement
python -u -B content/tarot/tools/upgrade_probe.py --target 1.21.5
python -u -B content/tarot/tools/upgrade_probe.py --target 26.3
python -B -O content/tarot/tools/test_universal_integrity.py -v
python -B -O content/tarot/tools/test_build_integrity.py -v
python -B -m unittest discover -s content/tarot/tools -p test_receipts.py -v
python -B -m unittest discover -s content/tarot/tools -p test_lab_environment.py -v
python -B -m unittest discover -s content/tarot/tools -p test_module_registry.py -v
python -B -O content/tarot/tools/verify_release.py
```

To reproduce the current client dispatch check, run
`universal_native_lab.py --version 26.3 --resources-only --receipt-prefix dispatch --client-use-probe`.
It runs automatically without desktop control. For an additional actual keyboard
pass when desktop automation is available, launch
`universal_native_lab.py --version 1.21.11 --resources-only --visual-hold --receipt-prefix native-refinement`.
In another terminal, run `native_input_lab.py --ready <visual-ready.json> --phase setup-clear`,
press **R** once in the test window, then run `--phase check-clear`. Repeat with
`setup-torch`, **R**, and `check-torch`; `--phase finish` records both observed
checks and closes the owned session. The ready-file path is printed by the runner.
These phases set up fixtures and inspect results; they never substitute a function
call for the native input being checked.

The seeded gameplay fuzzer runs two non-operator Survival players through moves,
trades, drops, placement, support loss, reloads, disconnects and server restarts.
An independent server-side oracle canonicalizes real ItemStacks and verifies every
individual instance and all annotations after each action. A completion sentinel
prevents a missing or interrupted oracle from appearing to pass. Each invocation
freezes its production bytes and uses its own server directory. Reproduce with
`fuzz_lab.py --version 1.20.6 --seed 8191 --steps 300`, then the 1.21.11/671083 and
26.1.2/104729 cases. `payload_lab.py --version VERSION --fuzz-cases 96` adds seeded
malformed opaque-item tests that preserve both hands across draw/shuffle/return.

`expansion_lab.py` builds an isolated synthetic third module and tests saved
worlds through addition, mixed decks, omission and reinstallation, including real
Survival crafting. `catalogue_budget_lab.py` builds a synthetic 1,024-card catalogue
and exercises two simultaneous 128-card prototype migrations on 1.20.6 and 26.1.2.
These fixtures remain in the test cache. Factory lookup and name normalization
use keyed templates, avoiding a catalogue scan for every individual legacy card.

Run one matrix controller at a time. It freezes its observers, bounds concurrent
owned servers and preserves timestamped reports. Protocol repairs are observer
only: legacy sneak enums, integer custom-model decoding on 1.21.3, native secondary
interaction flags, and 26.1.2's attack/packed-location packets. No game code is
patched. Targets, worlds, official downloads and logs stay in the sibling
`commonground-microvoxels-runtime/tarot/` cache; only owned processes are stopped.
The small JSON indexes link shared, content-addressed gzip blobs by SHA-256.
History preserves failures and earlier passes without copying the same archive.
`evidence_store.py` verifies every referenced compressed/payload hash before
compacting old copies; unique unreferenced diagnostics are retained too. [Astra/Sol review and fixes](evidence/REDTEAM.md)
records review scope. The accepted index records the date its complete verification actually ran.
