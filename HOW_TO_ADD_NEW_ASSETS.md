# How to Add New Assets

> **Important:** the pipeline's Phase 1 LLM does **not** read `README.md`. It only sees the asset
> list in `ASSET_REFERENCE` at the top of `screenplay_to_scene.py`. When you add assets, update
> **that list** (so the pipeline can use them) **and** the README (so people can find them).
> Only the older helper modules `screenplay_parser.py` and `location_environment_generator.py`
> parse the README, and `pipeline.py` doesn't use them.

When adding a character, give the LLM what it needs to pick it: the file name, pack,
`armature_filter`, scale, the exact animation names, and when to use it (e.g. "Witch.glb —
witchcraft, magic, fantasy"). For Ultimate Modular characters, add the file to the default or
costume list in `ASSET_REFERENCE`.

## Steps

### 1. Add the GLB files to `assets/`

```
assets/
└── My New Pack-glb/
    ├── Item1.glb
    ├── Item2.glb
    └── Item3.glb
```

### 2. Add the pack to the folder structure in `README.md`

Find the **"Complete Asset Folder Structure"** section and add your pack alphabetically:

```markdown
├── My New Pack-glb
│   ├── Item1.glb
│   ├── Item2.glb
│   └── Item3.glb
```

### 3. Add a scaling guideline in `README.md`

Find the **"Asset Scaling Guidelines"** table and add a row:

```markdown
| My New Pack-glb | 1.5x |
```

### 4. (Optional) Add scene-specific usage notes

If your pack is best suited for a particular location type, add a note to the relevant location section (e.g., "Kitchen", "Office") in the **"Common Scene Locations & Required Assets"** section of the README.

### 5. Run the pipeline — that's it

```bash
python3 pipeline.py "INT. MY SCENE - DAY\n\nCharacter does something with Item1."
```

Then add the same pack, files and scale to `ASSET_REFERENCE` in `screenplay_to_scene.py`.
Only after that will the LLM see `My New Pack-glb/Item1.glb` and select it for appropriate scenes.

---

## What Updates Automatically

| Component | Source | Auto-updates? |
|-----------|--------|--------------|
| What the Phase 1 LLM sees (packs, files, scales, animations) | `ASSET_REFERENCE` in `screenplay_to_scene.py` | ❌ Update by hand |
| What people see | README.md | ❌ Update by hand |
| Asset paths exist on disk | Checked by the post-processor | ✅ Warns if missing |
| Location design guidelines | Hardcoded in prompt | ❌ By design |

---

## Adding a Complete Location Scene (pre-built GLB)

If you have a complete pre-built scene GLB (like `Bar scene.glb`), place it in `assets/locations/` and add it to the locations table in the README:

```markdown
| My New Location.glb | 5x |
```

The LLM will use a `location_glb` block in the JSON instead of assembling from parts:

```json
"environment": {
  "location_glb": {
    "asset_path": "assets/locations/My New Location.glb",
    "scale": [5, 5, 5],
    "position": [0, 0, 0]
  }
}
```

Note the correct Z floor offset for your scene — you may need to add it to the `_LOCATION_FLOOR_Z` dictionary in `screenplay_to_scene.py`.

---

## Adding a New Character with Custom Animations

If you have a character GLB with animations already embedded (standard NLA strips):

1. Place the GLB in the appropriate pack folder (or create a new one).
2. List the exact animation action names in the README character section.
3. Add the armature filter name (the name of the Armature object inside the GLB).
4. Add to the scaling table.

The LLM will use the exact names you list. **Animation names must match exactly** (case-sensitive) — they are matched against `bpy.data.actions` by stripping the `ArmatureName|` prefix and `.001` suffixes.

### Building a combined GLB from per-animation FBX files

If you have separate FBX files for each animation (common with asset store packs):

```bash
# Edit build_character_glb.py to point to your FBX folder and gender prefix
python3 build_character_glb.py
```

This merges all FBX animations onto the base character mesh and exports a single `.glb` with all animations as NLA strips — ready for the pipeline.

---

## Common Mistakes

| Mistake | Correct approach |
|---------|-----------------|
| Add GLB but don't update README | Must update README — pipeline reads from it |
| Invent an animation name in JSON | Only use names explicitly listed in README |
| Use a multiplier for `scale_meters` | `scale_meters` is world-space metres, not a ratio |
| Add `base_surface` for a location GLB | Location GLBs have built-in floors — omit `base_surface` |
