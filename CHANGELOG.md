# Tabletop Tarot 1.1.0

A little more room at the table, and two guides to read beside it.

### Two guides, two perspectives

Craft a book with an amethyst shard for **Steve’s Tarot Guide**, or add a feather for **Alex’s (better) Tarot Guide**. Both cover all 78 tarot cards and the 12 Numbers, with their own readings, linked pages and custom 3D covers. They don’t always see things quite the same way.

Read them in your hand or share one on a lectern. The guides offer ideas for reflection or roleplay. What the cards mean is still yours to decide.

### Around the table

- **Play in Survival with normal clicks.** Craft decks and guides, then draw, shuffle, place, flip, rotate and collect cards without typing commands.
- **Deal blind.** Hold a deck, aim at a clear tabletop, and use `/trigger tarot.action set 5` to deal the top card face-down without seeing it first. Survival players can use it without operator permissions. Either guide can copy the command for you.
- Hit a placed card while holding a deck to return it, or sneak-hit to gather a nearby spread.
- Make tighter spreads on more surfaces, including carpets, bookshelves, closed trapdoors and upside-down stairs.
- Cards now lift, turn and settle with small animations and quiet interaction sounds.
- Improved multiplayer handling, card preservation and compatibility across supported versions.

### Installing and updating

Use **Tabletop-Tarot-1.1.0.zip** in both your world’s `datapacks/` folder and Minecraft’s `resourcepacks/` folder. Enable the resource pack, then reload or reopen the world. Keep the ZIP intact.

If you’re updating, back up your world and replace the old ZIP in both folders. Existing signed guides keep their pages. Craft fresh copies for the new covers and wording.

Supports Minecraft Java **1.20.6, 1.21.1, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.8, 1.21.10, 1.21.11, 26.1.2 and 26.3**.

### Technical changes

- Add matching matte 3D guidebooks: lapis/ochre with a star and threshold for Steve, spruce/copper with a crescent and trail for Alex. Compile independent front/back art into compact atlases, with stitched binding, paper edges and ribbon bookmarks. Preserve normal written-book appearances outside the reserved legacy model IDs.
- Refine 22 passages after a read-only semantic review of both complete books: give Alex more private observations, separate paired interpretations, preserve room for help and unresolved feelings, and ground the Tower in a wooden-spire fire. Clarify repeated digit sums, modern numerology, and the held-deck/table requirements for blind dealing.
- **Simpler transaction and shuffle work:** reuse the transaction-local comparison buffer instead of cloning another complete native array. Replace the forward shuffle's repeated bound arithmetic with a bounded descending Fisher-Yates chain of literal random ranges; preserve exact item instances and uniform permutations.
- Capture one fresh selected-item snapshot for native validation and commit preparation, consuming it during preparation and discarding leftover drafts on reload. Avoid repeated full-player NBT serialization without caching validation across operations.
- **Cozy tabletop surfaces:** cards now sit cleanly on wool/moss carpets (`0.0625` height with fine raycast stepping so carpets on planks never clip), closed top and bottom trapdoors (`1.0` and `0.1875` height), upside-down stairs, bookshelves, chiseled bookshelves, terracotta, concrete, blackstone, basalt, calcite, tuff/copper/resin blocks (version-gated per overlay), moss blocks, hay bales, note blocks, jukeboxes, and more. Opening a trapdoor or breaking a carpet drops any supported card cleanly.
- **Tighter spreads & crisper clickboxes:** reduced side-by-side placement clearance from `0.60` to `0.24` blocks for close 3-card spreads and layered layouts, paired with a tighter `0.42 × 0.08` clickbox and sub-millimeter neighbor anti-z-fighting lift.
- **Direct return & spread scoop:** left-click a placed card while holding a deck to slip it straight back on top of the deck; sneak-left-click with a deck to gather up to 16 nearby placed cards back into the deck in one smooth motion.
- **Blind deal (`/trigger tarot.action set 5`):** deal the top card of a held deck directly face-down onto a surface within reach without peeking or touching a hotbar slot, with atomic rollback if placement fails.
- **Hardened drop physics & subtle sounds:** replaced macro-interpolated drop summoning with direct NBT copy so arbitrary custom card names drop safely, and tuned distinct quiet sound cues for placing, flipping, rotating, drawing, and scooping cards.
- **Original-source builds & multi-version test harness:** imported runtime generators and authoring inputs, explicit `src/` extensions, deterministic pack builder `tools/build.py`, headless server verifier `tools/verify.py`, and two-client live integration suite `tests/test_live.py`.

### Behaviour and evidence refinements

- Profile the full-stack multiplayer pressure fixture with JFR and matched warm timing runs. Reduce repeated deep NBT matching by factoring independent per-card invariants, and decide transaction codec branches once before the item loop. Keep complete codec round-trip and malformed-item rejection checks.
- Animate flips with a short lift and turn, interpolate exact 45-degree rotations, and settle newly committed cards onto their surface. A finite state on each display accepts interruptions and cleans up on pickup or support loss; older saved displays acquire the rotation defaults. Pause visual progression safely below the supported command budget.
- Record actual two-client motion and check final pose, item custody, interruption, reload, legacy display initialization, and command-budget recovery. Add targeted native validation controls and cross-dimension motion assertions.

- Keep successful vanilla offhand block use from also operating the Tarot item, including when placing the last torch empties the offhand before the next tick. Use the native block-use event to consume that click's handling statistic.

- Refuse live verification when Python assertions are disabled, so optimization cannot silently turn scenario checks into a pass.
- Placement feedback for blind deals and shuffle feedback now follow the successful deck commit. Refused legacy migrations preserve the original item and stay quiet; provisional card displays and hitboxes are removed.
- Add a small outcome-focused client/server pass with matched acceptance and refusal controls, exact card identities and feedback trace checks, instead of another broad scenario cross-product.
- Reject duplicate ZIP member names in both archive verification paths. Mark comparisons stale when new archive bytes supersede their candidate, preserving the old comparison's identity and status.
- Give both server harnesses the same explicit flat-world layers and verify their actual floor, avoiding a malformed empty generator setting and fallback world generation.
- Capture a stock client's thread dump on join timeout where the JDK tool is available, retaining the failure and its screenshot for diagnosis.
- Run the pinned original gameplay labs against a frozen final ZIP, with separate observer fixtures and strict check completion. Add the complete protocol engine suite, nine-player queue pressure, and seeded whole-item custody coverage.
- Strengthen full-client checks for real boat mounting, exact multiplayer flip targets, spread spacing and actual server resource-pack application. Acknowledge hotbar changes before RCON-driven actions, wait for input eligibility, and isolate the exhausted-budget fixture from normal tick replenishment.
- Classify deliberate malformed-item codec diagnostics by owned world, exact fixture identity and rejection reason; retain them in evidence while still rejecting unrelated errors. Check a valid draw after each malformed batch to verify recovery.

### Original source integration

- Import the original implementation and authoring inputs from `commonground-server/content/tarot` at release tag `tabletop-tarot-v1.0.0` (`4bfadd221f89a1031d19a78ab875b05adf995742`), with per-file provenance hashes and original licenses.
- Build the base engine using its original generators. Keep the 1.1.0 additions and review fixes as explicit overrides; remove duplicated generated base functions, catalogues and assets from `src/`.
- Add eleven-target source/release parity checks and reviewed-1.1.0 preservation checks, including exact decoded artwork pixels. Restore the original build/module/lab test tooling without importing historical receipts as new evidence.

### Peer-review hardening

- Allocate distinct local height layers for overlapping neighbors rather than deriving four possible heights from unrelated entity IDs.

- Bound spread-scoop candidate work and require one tabletop plane, unobstructed eye reach, and the shared deck-operation allowance. Recheck obstruction/reach when delayed table events are served.
- Charge blind deal against the existing heavy-work queue allowance; leave deferred pickup events intact.
- Verify dropped-card components through the item codec before discarding the placed copy. Exclude wall-only pale moss carpet from horizontal support.
- Add released 1.0.0 item fixtures, non-operator client triggers, multiplayer pickup races, reload and failed-deal regressions. Strengthen chat, pack-load, flip and placement-height assertions.
- Require all eleven overlay entries during static verification, expose cache/Java configuration, and emit SHA-1/SHA-256 sidecars matching the installation instructions.

---

# Tabletop Tarot 1.0.0

First release.

- Original illustrated Rider–Waite–Smith deck and Numbers set, both included by default.
- Physical ordered stacks: shuffle, draw the top card, and return an individual card to the top. Cards retain their own names and notes.
- Place cards face-down on your own flat surfaces, turn them over, rotate them and take them back. Removing their support releases the actual card into vanilla item physics.
- Printed fronts, backs, slender edges and count-sensitive deck models. Quiet Survival recipes and normal crafting-book discovery.
- One combined datapack/resource-pack ZIP with automatic overlays for eleven exact supported Java versions.
- Verified version adapters, saved-item expansion, resource-pack combinations, malformed items, multiplayer conservation and seeded gameplay fuzzing.

- MIT for original code; CC BY 4.0 for original artwork; public-domain Rider illustrations credited separately. Full licenses travel inside the pack.
- Modrinth import detects the datapack role through an inert root marker while all runtime stays in automatic version overlays.
