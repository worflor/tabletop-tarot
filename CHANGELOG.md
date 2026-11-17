# Tabletop Tarot 1.1.0

A little more room at the table, and two guides to read beside it.

### Two guides, two perspectives

Craft a book with an amethyst shard for **Steve’s Tarot Guide**, or add a feather for **Alex’s (better) Tarot Guide**. Each has its own readings for all 78 tarot cards and 12 Numbers, with linked pages and a custom 3D cover. They don’t always see things quite the same way.

Read in hand or share a guide on a lectern. What the cards mean is still yours to decide.

### Around the table

Draw, shuffle, place, flip, rotate and collect cards with normal Survival controls.

- **Deal blind.** Hold a deck, aim at a clear tabletop, and use `/trigger tarot.action set 5` to deal the top card face-down without seeing it first. Any player can run it, and either guide can copy it.
- Hit a placed card while holding a deck to return it, or sneak-hit to gather a nearby spread.
- Make tighter spreads on more surfaces, including carpets, bookshelves, closed trapdoors and upside-down stairs.
- Cards now lift, turn and settle with small animations and quiet interaction sounds.

### Installing and updating

Use **Tabletop-Tarot-1.1.0.zip** in both your world’s `datapacks/` folder and Minecraft’s `resourcepacks/` folder. Keep it zipped, enable the resource pack, then reload or reopen the world.

If you’re updating, back up your world and replace the old ZIP in both folders. Craft fresh guides for the new covers and wording. Existing signed copies keep their pages.

Supports Minecraft Java **1.20.6, 1.21.1, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.8, 1.21.10, 1.21.11, 26.1.2 and 26.3**.

### Technical changes

- Preserve exact card data through shuffles, drops and legacy upgrades. Failed deals leave the deck intact. Placement and shuffle sounds follow a successful commit.
- Bound each scoop to 16 cards on the same surface within reach. Deferred clicks recheck reach and obstructions, and using an offhand item can take priority over a Tarot click.
- Reduce repeated item reads and shuffle work. Build from pinned original sources and check all eleven overlays. See the [build and verification instructions](README.md#build--verify-from-source).

---

# Tabletop Tarot 1.0.0

- The illustrated 78-card Rider–Waite–Smith deck and 12-card Numbers set.
- Craft, shuffle and draw from physical stacks. Lay cards face-down, reveal or rotate them, and pick them up with their names and notes intact.
- One combined datapack and resource pack with automatic version overlays.
