# Tabletop Tarot

![Tabletop Tarot pack icon](pack.png)

**78+ illustrated cards to shuffle, draw, trade and lay on your own tables. You decide what they mean.**

A deck for the little places in your world: the window seat, the garden table, the end of a wooden jetty. Make a small ritual, invent a game, leave a card for a friend, or simply enjoy the artwork.

Tabletop Tarot brings Cartomancy's original illustrated Rider–Waite–Smith deck and Numbers set into vanilla Minecraft Java. Both sets come included, with printed fronts and backs, thin paper edges, and stacks that grow slimmer as you draw.

## Handle them like cards

- **Draw:** use a deck to take its top card.
- **Shuffle:** sneak-use a deck to randomize its remaining cards.
- **Deal blind:** `/trigger tarot.action set 5` deals the top card directly face-down onto a surface without peeking.
- **Return:** hold one card in the offhand and sneak-use the deck to put it on top — or hit a placed card while holding a deck to put it straight back (sneak-hit to gather a spread).
- **Lay out:** use a loose card on a clear, flat surface (blocks, bookshelves, slabs, carpets, closed trapdoors, or upside-down stairs) to place it face-down, including tight side-by-side spreads.
- **Turn and arrange:** use a placed card to turn it over; sneak-use to rotate it.
- **Take it with you:** hit a placed card with an empty hand to pick it up. Trade, store, drop and frame cards using ordinary Minecraft interactions.

Cards lift gently as they turn, settle onto the table when dealt, and glide through each 45-degree rotation. Another player's input can change a turn in progress; taking a card still transfers it immediately.

There are no spells, powers or enforced games. The guide offers optional reading prompts; the cards are yours to give meaning to. Nothing is granted or announced when you join a world.

## Craft a deck

Use a crafting table: **eight paper** around **an ink sac** makes the Rider deck; eight paper around **lapis lazuli** makes the Numbers deck. The normal recipe book learns the recipes when you have the ingredients.

## A guide for your table

Craft **one plain book + one amethyst shard** for **Steve's Tarot Guide**; **add a feather** for **Alex's (better) Tarot Guide**. Both fit the inventory crafting grid. Steve's has 109 linked pages, including a tucked-away P.S.; Alex's has 108. Both cover the same controls, all 78 tarot cards (22 Major and 56 Minor Arcana), the 12 Numbers, and a signed closing note.

Steve's practical notes draw on making, mending and trying again; Alex's observations follow journeys, discoveries and changing perspectives. Read as yourself or someone you play. These are the pack's imagined journals, with distinct readings for every card, rather than official character biographies. Some passages leave a feeling unresolved; others offer a question or a scene to try. The Numbers use modern numerology motifs for reflection. Lapis and ochre distinguish Steve's edition; spruce and copper distinguish Alex's. Coloured chapter headings, italic scenes and dark parchment ink keep both books readable.

Underlined contents and card names jump directly to their pages; each card links back to its index. The reading page can copy the blind-deal command. Read the guide in your hand, keep it on a shelf, or share it on a lectern. It is a signed written book so those native links work; bring a separate book and quill for your own notes. No tutorial, book grant or extra command is required on joining.

Each guide has a matte 3D cover, stitched leather binding, paper edges and a ribbon bookmark. Steve's lapis-and-ochre cover carries a star and threshold; Alex's spruce-and-copper cover carries a crescent and trail. The resource pack supplies these item appearances; the reading screen and lectern's open-book rendering use vanilla Minecraft. Craft fresh copies for the new covers and wording.

## Build & Verify from Source

```bash
python3 -m pip install -r requirements.txt
python3 tools/build.py
python3 tools/verify.py
python3 tests/test_live.py
```

The implementation is imported from [`worflor/commonground-server`, tag `tabletop-tarot-v1.0.0`](https://github.com/worflor/commonground-server/tree/4bfadd221f89a1031d19a78ab875b05adf995742/content/tarot), not reconstructed from the ZIP. Its original runtime generators, authoring inputs and test tools live in `vendor/commonground-server/content/tarot/`; the adjacent `source-lock.json` records the exact commit and SHA-256 of every imported file. Historical upstream evidence receipts are not copied or presented as current validation.

`tools/build.py` verifies that source lock, runs the original generators for each target, then applies only the 1.1.0 extensions listed in `src/overrides.json`. The base engine is maintained in the pinned original source; `src/` contains the reviewed additions and overrides, not a second copy of generated assets and base functions. Builds emit `dist/source-provenance.json` alongside the archives. A parity receipt for different archive bytes is explicitly marked stale; duplicate ZIP member names are rejected rather than silently choosing one copy. Source updates must deliberately update the pin and recheck parity.

To compare the imported original generators with the released 1.0.0 ZIP:

```bash
python3 tools/verify_source.py --baseline /path/to/Tabletop-Tarot-1.0.0.zip
```

The comparison checks all eleven targets, parsed JSON, function lines and decoded PNG pixels. Different ZIP metadata, line endings or PNG compression do not count as runtime changes. Optional `--reference /path/to/checkpoint-1.1.0.zip` also compares the current pack with that checkpoint; later gameplay refinements are reported as differences. Each receipt records exactly which comparisons ran and binds them to the current archive hash. The original test tooling is preserved with its original platform requirements; passing its source/build contract tests does not imply its historical gameplay suites were rerun against 1.1.0.

Use `dist/Tabletop-Tarot-<version>.zip` for both installation locations. The build also emits a resource-only ZIP for development and server test tooling. The GitHub release supplies one combined ZIP with its hashes in the release notes.

The builder needs Python 3.10+ and Pillow (`requirements.txt`). Server checks need cached vanilla server JARs at `$TAROT_MC_CACHE/<version>/minecraft-server.jar` (default: `~/.gradle/caches/fabric-loom`), Java 21 for 1.x and Java 25 for 26.x. Set `TAROT_JAVA21` and `TAROT_JAVA25` to Java executable paths if needed. The live suite additionally needs cached vanilla clients, their Mojang metadata and Gradle library/assets cache, Xvfb, xdotool, ImageMagick's `import`, xclip, and FFmpeg with its built-in FFV1 encoder; it launches two graphical clients using software rendering and retains lossless motion recordings. Use `--versions` to select installed versions and `--artifacts-dir` to retain separate runs. The default server matrix checks all eleven supported releases and reports missing caches as failures.

For a focused feedback/preservation pass, run `python3 tests/test_live.py --polish-only --versions 26.3 1.21.1`. It pairs a valid legacy deck with the same payload carrying conflicting migration history, then checks exact item preservation, provisional entity cleanup and commit-bound sound dispatch in server traces. It also checks occupied-table refusal and accepted/rejected shuffles. This is transaction feedback evidence; it does not rate how the sounds feel.

The live suite exercises real client clicks and non-operator trigger commands; RCON arranges fixtures and reads authoritative state. It also runs deterministic server-function regressions for scoop boundaries and delayed interactions. Released 1.0.0 loot fixtures and their provenance live in `tests/fixtures/1.0.0/`. Screenshot rendering requires human inspection; a passing server smoke test alone does not establish gameplay correctness.

The full live run includes the physical deck cycle, successful offhand torch placement from both a full stack and its last item, and the transaction-feedback controls. Select every supported release with `--versions` for the complete client matrix. Hotbar switches wait for server acknowledgement; join failures retain screenshots and thread diagnostics. Stock clients use bounded JVM HTTP waits so an unavailable Mojang blocklist service cannot hang local-server connection indefinitely; the blocklist check remains enabled.

The original protocol-based engine labs can also test the final ZIP through `tests/test_engine.py`. Prepare their locked Node.js observer with `python3 tests/test_engine.py --versions 1.20.6 1.21.11 26.1.2 --prepare`, then use the same command with `--suite broad` to run the complete engine suite on those releases. `--versions` accepts all ten protocol-supported targets; 26.3 instead has `python3 tests/test_live.py --backend-only --versions 26.3` for its additional server-backend checks with stock clients connected.

Additional engine suites are `quiet` (crafting and vanilla recipe safety), `refinement` (deferred inputs and surface boundaries), `payload` (malformed items), and `fuzz` (two-player whole-item custody with reloads, reconnects and restarts; use `--seed` and `--steps`). `--suite pressure --versions 1.21.11` runs nine protocol players with full 128-card stacks while 144 unique tabletop cards lose support. Its observer brackets the unchanged production tick to measure work budgets and conservation; its timing is not a general TPS guarantee. Every invocation freezes the final ZIP, checks that observer fixtures do not override production functions, and retains receipts in `tests/artifacts/final-global/`.

`--suite dimensions --versions 1.21.11` checks two non-operator players at identically positioned tables in the Overworld and Nether, including blind deals, isolated flip/rotate/pickup, and support loss. Malformed-item runs retain narrowly classified native codec diagnostics and require a valid draw after the rejected batch; unrelated engine errors still fail verification.

For motion alone, use `python3 tests/test_live.py --motion-only --versions 1.20.6 1.21.11 26.3`. Both clients operate the same card through native input. Checks include a second player's interruption, exact final pose and item, pickup and support loss during a turn, reload, older saved displays, and reduced command-budget pause/resume. Motion uses a finite per-card state and Minecraft's display interpolation, with no extra entities or scheduled callbacks. Its visual offset leaves the authoritative support position fixed. The complete live suite includes these checks.

`--suite native` in the engine harness targets the factored native validator: foreign carriers, mismatched key/module pairs, complementary invalid rows, invalid counts beside valid defaults, and successful mixed-module/default-count controls. Rejections must preserve both held items exactly, leave no staging entities, and still capture the request. The 26.3 backend suite runs the same cases using queued server probes.

`--suite optimization` checks matched accepted/rejected native staging: a changed payload or cardinality must reject before committing, preserving both held items. It also checks complete instance bijections at shuffle sizes 0, 1, 2, 3, 127 and 128. The descending Fisher-Yates loop uses literal uniform bounds, with exhaustive generated-path checks for small decks. Exact array verification reuses a transaction-local scratch buffer; a mismatch can change that scratch buffer only, and revokes commit admission.

Native stack handling captures the selected item once at validation, reads its metadata and contents from that transaction snapshot, and consumes the snapshot when preparing a commit. Every new validation clears the previous draft; reload also discards it. This avoids repeatedly serializing the player's full entity NBT to read a single field, while keeping deferred-input checks and full item codec comparisons. It is an operation-local snapshot, not a cross-player or cross-tick validation cache.

`python3 tests/test_live.py --guidebook-only --versions 1.20.6 1.21.11 26.3` tests native survival crafting, linked page changes on a shared lectern, the actual clipboard command, reload, and taking back the complete exact book. RCON response continuation is delimited with a separate request ID. The protocol observer has an explicit 1.20.6 adapter correcting a stale recipe serializer registry; it decodes all recipes and book components, rather than filtering recipe packets. The pinned original test sources remain unchanged.

Guide text lives in `src/guidebook/steve.json` and `alex.json`; `content.json` retains the first guide's shared control text and authoring baseline. `tools/guidebook.py` checks exact catalogue coverage, identical instructions, native bitmap font widths, 14-line page fit and per-version event encoding, and emits a per-edition `guidebook-index.json` sidecar. Written books use Minecraft's native page-list codec; the writable-book editor's 100-page limit does not constrain these signed guides. They add no tick work, entity or trigger objective. `tools/guidebook_models.py` compiles separate front/back art into two 256x128 texture atlases and five-cuboid models, with per-item model IDs on modern versions and bounded numeric overrides on legacy versions. Source artwork and prompts live in `src/guidebook/art/`. The original `tarot:guidebook` recipe and loot ID now produce Steve's edition; already signed guides retain their original pages.

To repeat the performance experiment against a frozen ZIP:

```bash
python3 tests/profile_engine.py --zip dist/Tabletop-Tarot-1.1.0.zip --label local-timing --mode timing --repeats 3
python3 tests/profile_engine.py --zip dist/Tabletop-Tarot-1.1.0.zip --label local-jfr --mode jfr
```

Timing uses the same nine-player, full-stack pressure fixture after two warm-up cycles; each measured cycle also releases 144 unique supported cards. Run comparisons sequentially with other test servers and clients stopped. Receipts bind the supplied archive hash, full conservation/work-bound checks, elapsed 80-tick workload, and Minecraft's rolling 100-tick timing query. JFR runs diagnose hotspots separately and are excluded from timing comparisons. The optimization factors universal per-card validation rules and hoists invariant codec-dispatch branches; it retains every item codec and preservation check. Local runs write their receipts under `tests/artifacts/`.

Scooping gathers up to 16 reachable, unobstructed cards on the same tabletop level within 2.5 blocks of the clicked card. Dense layouts inspect at most 15 neighboring candidates per scoop; repeat to gather more. Stack model components belong to the pack and update with the card count. Vanilla interaction entities retain only the most recent attack/use record, so simultaneous clicks on the same card may resolve to one player's action; the card itself is transferred once.


## Install

### One download, two places

1. Put **Tabletop-Tarot-1.1.0.zip** in your world's `datapacks/` folder.
2. Put **the same ZIP** in your client's `resourcepacks/` folder and enable it for the illustrated cards.
3. Run `/reload` or restart the world.

Keep it zipped. No mods or plugins are required. On multiplayer servers, each player needs the resource pack enabled; the server can offer the same ZIP as its resource pack (`resource-pack=` and `resource-pack-sha1=`).

When upgrading, back up the world and replace the previous ZIP in both locations. For removal, retrieve any laid-out cards first. Stored card items remain in the world, and their handling actions and artwork depend on the pack. The ZIP includes further server instructions in `INSTALL.txt`.

Supports Java **1.20.6, 1.21.1, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.8, 1.21.10, 1.21.11, 26.1.2 and 26.3**. Minecraft selects the matching version automatically from the same file. Bedrock is unsupported.

Keep your offhand clear when using cards, except when returning a card to a deck. If a workstation takes the click, sneak-use to place on its top. For alternate controls, `/trigger tarot.action set 1` draws, `2` shuffles, `3` returns the offhand card, `4` places a loose card and `5` deals the top card face-down.

When combining resource packs, keep Tabletop Tarot above packs that replace the carrot-on-a-stick item model. The original art needs the included resource assets.

## Reuse and credits

Original code is MIT. Original Numbers artwork, backs, textures and icon composition are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), credited to woflo (worflor), Tabletop Tarot; indicate changes when adapting them. Rider–Waite–Smith 1909 illustrations by Pamela Colman Smith with Arthur Edward Waite are public domain. The complete license notice and texts are included in the ZIP.

See [the license notice](LICENSE.md), [full MIT terms](licenses/MIT.txt), [full CC BY 4.0 terms](licenses/CC-BY-4.0.txt), and [art credits](CREDITS.txt).

## Updates and bugs

[Releases](https://github.com/worflor/tabletop-tarot/releases) has downloads and updates. If something goes wrong, [open an issue](https://github.com/worflor/tabletop-tarot/issues) with your Minecraft version, pack version, what happened, and steps to reproduce it.

Not an official Minecraft product; not affiliated with Mojang or Microsoft.
