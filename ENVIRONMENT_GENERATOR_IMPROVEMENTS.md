# Environment Generator — Location Support Reference

`location_environment_generator.py` handles the environment assembly part of Phase 1. It determines which asset pack items to scatter for a given location type when a pre-built `locations/` GLB is not available.

---

## Supported Location Types

### Indoor — Residential
- Bedroom, Kitchen, Bathroom, Living Room, Home Office, Guest Room, Dining Room

### Indoor — Professional / Public
- Office, Store, Shop, Restaurant, Cafe, Library, Museum, Gallery, Lobby

### Outdoor — Nature
- Forest, Woods, Park, Beach, Shore, Garden, Wilderness, Jungle, Meadow, Field

### Outdoor — Urban
- Street, City, Downtown, Urban Area, Parking Lot, Plaza, Courtyard

### Outdoor — Special
- Medieval Village, Castle, Fortress, Farm, Barn, Countryside
- Cave, Dungeon, Laboratory, Warehouse, Spaceship / Sci-Fi

---

## Object Quantity Targets by Location Type

| Location category | Target count |
|-------------------|-------------|
| Indoor intimate (bedroom, office) | 10–20 objects |
| Indoor public (restaurant, store) | 25–100 objects |
| Outdoor nature (forest, beach) | 150–300 objects |

---

## Asset Selection Rules

The LLM is instructed to:

1. **Match the location** — no trees in bathrooms, no beds in forests
2. **Use variety** — 5–15 different asset types per scene
3. **Be realistic** — quantities match real-world density
4. **Prioritise packs** — indoor → Furniture Pack + Interior Pack first; outdoor → Nature Packs first
5. **Show lived-in detail** — multiple instances of common items (chairs around a table, trees at varying positions)

---

## Pack Priority by Location

| Location type | Primary packs |
|---------------|--------------|
| Office | `office/`, `Furniture Pack-glb` |
| Bedroom / Living Room / Kitchen | `Ultimate House Interior Pack-glb`, `Furniture Pack-glb` |
| Restaurant / Cafe | `Ultimate House Interior Pack-glb`, `Food Kit-glb` |
| Forest / Park / Beach | `Stylized Nature MegaKit.undefined-glb`, `Ultimate Stylized Nature Pack-glb` |
| City / Street | `kenney_city-kit-commercial_2.1`, `kenney_city-kit-suburban_20`, `Cars Bundle-glb` |
| Medieval | `Medieval Village Pack-glb`, `Stylized Nature MegaKit.undefined-glb` |
| Space / Sci-Fi | `Ultimate Space Kit-glb` |
| Camping / Wilderness | `Survival Pack-glb`, `Stylized Nature MegaKit.undefined-glb` |

---

## Pre-Built Location GLBs

For the locations listed below, the pipeline uses a **complete pre-built scene GLB** instead of assembling from parts. The environment section uses `location_glb` rather than `scattered_elements`.

| Location keyword | GLB | Scale |
|-----------------|-----|-------|
| bar, pub | `assets/locations/Bar scene.glb` | 1x |
| kitchen | `assets/locations/Cozy Kitchen.glb` | 7.5x |
| living room | `assets/locations/Living Room.glb` | 5x |
| bedroom | `assets/locations/bedroom.glb` | 4x |
| beach | `assets/locations/Beach.glb` | 0.2x |
| shop, store | `assets/locations/Little Shop.glb` | 12x |
| gas station | `assets/locations/Gas Station.glb` | 7x |
| ocean | `assets/locations/Ocean.glb` | 1x |

When a pre-built GLB is used:
- Do NOT add a `base_surface` plane (the scene already has a floor)
- Characters are placed at the correct floor Z offset automatically by post-processing

---

## How It Works in the Pipeline

`location_environment_generator.py` is called internally by `screenplay_to_scene.py` as part of Phase 1. It:

1. Receives the parsed location string (e.g. `"INT. KITCHEN - DAY"`)
2. Checks if a matching `locations/` GLB exists
3. If yes: returns a `location_glb` block
4. If no: calls the LLM to select appropriate scattered environment assets from the README asset lists
5. Returns the `environment` JSON block to the main scene generator

---

## Adding Support for a New Location Type

1. If you have a complete scene GLB, add it to `assets/locations/` and to the table in `README.md`
2. If assembling from parts, ensure the relevant asset pack is listed in `README.md` — the environment generator reads from there dynamically
3. If a specific Z floor offset is needed, add it to `_LOCATION_FLOOR_Z` in `screenplay_to_scene.py`
