// Observer-only adapter. Never changes a server packet or production datapack.
// The pinned 1.20.6 schema contains the removed banner-add-pattern serializer,
// shifting all subsequent recipe IDs. Match Mojang's 23-entry registry exactly.
;(function correctLegacyRecipeRegistry () {
  if (process.argv[4] !== '1.20.6') return
  const protocol = require('minecraft-data')('1.20.6').protocol
  const expected = ['crafting_shaped', 'crafting_shapeless', 'crafting_special_armordye',
    'crafting_special_bookcloning', 'crafting_special_mapcloning', 'crafting_special_mapextending',
    'crafting_special_firework_rocket', 'crafting_special_firework_star', 'crafting_special_firework_star_fade',
    'crafting_special_tippedarrow', 'crafting_special_bannerduplicate', 'crafting_special_shielddecoration',
    'crafting_special_shulkerboxcoloring', 'crafting_special_suspiciousstew', 'crafting_special_repairitem',
    'smelting', 'blasting', 'smoking', 'campfire_cooking', 'stonecutting', 'smithing_transform',
    'smithing_trim', 'crafting_decorated_pot'].map(name => 'minecraft:' + name)
  let found = 0
  function visit (value) {
    if (!value || typeof value !== 'object') return
    if (value.mappings && Object.values(value.mappings).includes('minecraft:crafting_decorated_pot')) {
      const rows = Object.entries(value.mappings).sort((a, b) => Number(a[0]) - Number(b[0])).map(row => row[1])
      const corrected = rows.filter(name => name !== 'minecraft:crafting_special_banneraddpattern')
      if (JSON.stringify(corrected) !== JSON.stringify(expected)) throw Error('Unknown 1.20.6 recipe registry schema')
      value.mappings = Object.fromEntries(corrected.map((name, id) => [String(id), name]))
      found++
    }
    for (const child of Object.values(value)) visit(child)
  }
  visit(protocol.play.toClient.types.packet_declare_recipes)
  if (found !== 1) throw Error('Expected one 1.20.6 recipe serializer registry')
})()
