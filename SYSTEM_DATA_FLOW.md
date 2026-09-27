# System Data Flow

## End-to-End Pipeline Overview

```
Screenplay Text / PDF / .txt / .fountain
          │
          ▼
┌─────────────────────────────────────────┐
│            pipeline.py                  │
│         (orchestrator)                  │
└───────────────┬─────────────────────────┘
                │
        ┌───────▼────────┐
        │   PHASE 1       │
        │screenplay_to_   │
        │  scene.py       │
        └───────┬────────┘
                │  sends screenplay + ASSET_REFERENCE (+ --direction notes)
                ▼
        ┌───────────────┐
        │  LLM Backend  │  (Groq / Anthropic / Gemini / OpenAI)
        │  llm_client.py│
        └───────┬───────┘
                │  returns structured JSON
                ▼
        ┌──────────────────────────────────┐
        │  _postprocess()                  │
        │  • Auto-correct animation names  │
        │  • Enforce character spacing     │
        │  • Inject face-turn segments     │
        │  • Apply floor Z offsets         │
        │  • Remove hallucinated assets    │
        └───────┬──────────────────────────┘
                │  validated scene JSON
                ▼
        ┌──────────────────────────────────┐
        │  flexible_scene_generator_       │
        │     optimized.py                 │
        │  • Generates Blender Python code │
        │  • Imports GLB characters/props  │
        │  • Sets up NLA animation strips  │
        │  • Builds lower-body-lock blend  │
        │  • Attaches props to bones       │
        │  • Sets keyframes for visibility │
        │  • Adds lighting                 │
        └───────┬──────────────────────────┘
                │  runs:  blender --background --python ...
                ▼
        ┌──────────────────┐
        │  scene.blend     │   ← Phase 1 output
        │  scene.json      │
        │  scene_screenplay│
        │       .txt       │
        └───────┬──────────┘
                │
        [USER MANUALLY ADJUSTS .blend IN BLENDER]
        Reposition characters, fix scale, fix rotations
                │
        ┌───────▼────────┐
        │   PHASE 2       │
        │ camera_setup.py │
        └───────┬────────┘
                │  reads scene.json + screenplay
                ▼
        ┌───────────────┐
        │  LLM Backend  │  (same or different backend)
        └───────┬───────┘
                │  returns camera_shots JSON
                ▼
        ┌──────────────────────────────────┐
        │  _generate_blender_camera_script │
        │  • Opens existing scene.blend    │
        │  • Evaluates NLA at frame 1      │
        │  • Reads EVALUATED object locs   │
        │    (respects manual repositioning│
        │     done after Phase 1)          │
        │  • Places cameras per shot type  │
        │  • Applies movement keyframes    │
        │  • Adds timeline markers for cuts│
        └───────┬──────────────────────────┘
                │  runs:  blender --background --python ...
                ▼
        ┌──────────────────────────┐
        │  scene_cameras.blend     │   ← Phase 2 output
        │  scene_cameras_cameras   │
        │       .json              │
        └──────────────────────────┘
```

---

## Data Sources: What Comes From Where

### ASSET_REFERENCE → LLM Prompt (Phase 1)

`screenplay_to_scene.py` builds the Phase 1 prompt from constants in the file itself (it does
**not** read `README.md`):

- `ASSET_REFERENCE`: character packs with default / costume picks, exact animation names,
  sitting via `lower_body_lock`, the turn-taking dialogue rules, locations, props and grip bones,
  and the coordinate, timing and rotation rules
- `JSON_FORMAT`: the JSON schema and formatting rules
- optional **director's notes** (`pipeline.py --direction`) with blocking and beat timings

So **adding a new asset pack means updating `ASSET_REFERENCE`** (and the README for people).
Phase 2 similarly takes an optional plain-language shot list (`--shotlist`).

### scene.json → Blender (Phase 1 → Phase 1 execution)

`flexible_scene_generator_optimized.py` reads the validated JSON and generates a complete Python script that Blender executes in `--background` mode. The script:

1. Clears the default scene
2. Imports each character GLB, scales it, positions it
3. Builds an `animation_sequence` by:
   - For each segment: finds the named action in the armature
   - If `lower_body_lock` is set: creates a runtime-blended action merging lower/upper FCurves
   - Pushes onto NLA with CYCLES modifier for looping
4. If props are defined: imports GLB, parents to the named bone with `matrix_parent_inverse = Identity`, sets `scale_meters` in world space, keyframes visibility for `reveal_at_second`
5. Imports environment (either a single `location_glb` or `scattered_elements`)
6. Adds camera and lighting

### scene.blend → Phase 2 (evaluated positions)

Phase 2 does NOT use the `start_position`/`end_position` from the JSON directly. Instead:

```python
# From camera_setup.py
dg = bpy.context.evaluated_depsgraph_get()
obj.evaluated_get(dg).matrix_world.translation
```

This reads the **actual evaluated world-space position** of each character after:
- All NLA animation strips are applied at frame 1
- Any manual transforms the user applied in Blender after Phase 1

This is why repositioning characters in Blender before running Phase 2 is effective — the camera code sees the corrected positions.

---

## LLM Client: How Backend Selection Works

```python
# llm_client.py auto-detection order:
AUTO_ORDER = ["groq", "anthropic", "gemini", "openai"]

# Picks the first backend whose API key env var is set:
for backend in AUTO_ORDER:
    if os.environ.get(BACKENDS[backend]["env"]):
        use(backend)
        break
```

Override with CLI: `--backend groq` / `--backend anthropic` etc.  
Override model: `export GROQ_MODEL=openai/gpt-oss-20b`

---

## Post-Processing: What Gets Auto-Corrected

`screenplay_to_scene.py`'s `_postprocess()` function runs after every LLM response:

| Check | What it does |
|-------|-------------|
| Animation fixups (`_ANIM_FIXUPS`) | Replaces invented names (e.g. `Female_Wave` → `Female_Clapping`) |
| Character overlap check | If two chars share the same X, offsets one by ±0.8m |
| Minimum distance enforcement | If chars are < 1.0m apart in Y, separates them |
| Face-turn injection | Detects large rotation changes and injects a 0.75s BEZIER turn segment |
| Floor Z offset | Applies per-location Z corrections (e.g. Cozy Kitchen floor is 3.7m below default) |
| `base_surface` removal | Deletes any LLM-generated ground plane for `location_glb` scenes |
| Asset path validation | Warns if a referenced GLB does not exist on disk |

---

## Animation System: NLA + Lower Body Lock

### Standard animation segment
```
NLA Track
└── Strip: action_filter (e.g. Man_Walk)
    ├── start_frame → end_frame
    └── CYCLES modifier (for looping)
```

### Lower body lock (blended action)
```
At runtime, flexible_scene_generator builds a new action:
  new_action = merge(
      lower:  FCurves from lower_body_lock action   (hips, legs, feet)
      upper:  FCurves from action_filter action     (spine, chest, arms, head)
  )

Bone classification uses armature hierarchy:
  - Walk spine chain up from Hips → mark descendants as "upper"
  - Everything else (pelvis, legs, feet) → "lower"
```

This allows, for example, `Man_Idle` upper body + `Man_Sitting` lower body, so a character can gesture or hold a weapon while staying in a natural seated pose.
