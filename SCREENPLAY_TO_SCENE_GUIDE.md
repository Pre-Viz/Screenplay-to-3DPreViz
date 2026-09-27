# Screenplay-to-Scene Guide

A complete reference for how the pipeline interprets screenplays and what you can control.

---

## How the LLM Reads a Screenplay

### What it extracts

From the raw screenplay text, the LLM identifies:

1. **Scene heading** → location name, INT/EXT, time of day
2. **Characters** → names, approximate positions, initial facing direction
3. **Actions** → movement (walk, run, sit), gestures (wave, punch), emotional states
4. **Props** → objects that characters interact with or carry
5. **Scene duration** → inferred from the amount of action described

### What it outputs

A validated scene JSON (see README.md for the full format) with:
- `scene` block (name, duration, frame rate)
- `characters` array (each with `animation_sequence`)
- `props` array (with bone attachment info)
- `environment` block (location GLB or scattered elements)
- `camera` block (initial Phase 1 placeholder camera)
- `lighting` block

---

## Writing Screenplays That Work Well

### Character Names

Use ALL-CAPS for character names exactly as they appear in action lines:

```
DAVID sits at the bar.          ← DAVID will be a character
The BARTENDER hands him a drink. ← BARTENDER will be a character
```

The LLM uses these as character identifiers in the JSON. Avoid naming characters with spaces (e.g. prefer `JOHN` over `JOHN DOE` — the post-processor sanitises names but it's cleaner to keep them simple).

### Describing Movement

Be explicit. The LLM maps descriptions to available animations:

| Screenplay phrase | Animation used |
|-------------------|---------------|
| "walks toward", "walks in" | `Man_Walk` / `Female_Walk` |
| "runs", "sprints" | `Man_Run` / `Female_Run` |
| "sits", "is seated", "on a stool" | `Man_Sitting` / `Female_Sitting` |
| "waves", "clapping", "greets" | `Man_Clapping` / `Female_Clapping` |
| "punches", "hits", "attacks" | `Man_Punch` / `Female_Punch` |
| "stands", "is standing" (default) | `Man_Idle` / `Female_Idle` |
| "jumps" | `Man_Jump` / `Female_Jump` |
| "falls", "collapses" | `Man_Death` / `Female_Death` |
| "draws a gun", "shoots" | `Man_Idle` + prop attachment (upper only can use `Idle_Gun` via lower_body_lock) |

### Describing Props

Mention props clearly and in relation to a character:

```
Amanda slowly reveals a pistol under the counter.
← LLM attaches a Pistol.glb to Amanda's RightHand with reveal_at_second near end
```

```
Raul pulls out a knife.
← LLM attaches a Knife.glb to Raul's RightHand
```

### Describing Location

Use standard screenplay sluglines:

```
INT. BAR - NIGHT
INT. KITCHEN - DAY
EXT. CITY STREET - DAY
```

The LLM maps these to:
- `locations/` GLBs for known pre-built scenes (bar, kitchen, living room, bedroom, etc.)
- Assembled environment from packs for generic locations

---

## The Two-Phase Workflow

### Phase 1: Screenplay → Scene

```bash
python3 pipeline.py "INT. BAR - NIGHT\n\nDAVID sits at the bar..."
```

1. `screenplay_to_scene.py` calls the LLM with your screenplay + README asset lists
2. LLM returns a JSON scene description
3. Post-processor validates and auto-corrects it
4. `flexible_scene_generator_optimized.py` generates Blender Python code
5. Blender runs in background mode and saves `<scene>.blend`

Output files: `<scene>.json`, `<scene>.blend`, `<scene>_screenplay.txt`

### Manual Adjustment (between phases)

Open `<scene>.blend` in Blender and:
- Reposition characters (select armature → G to grab, move)
- Adjust scale if needed
- Fix rotation (R → Z → angle)
- Move props if they look off

Save the `.blend` file. Phase 2 will read the **adjusted positions** (not the JSON positions).

You can also edit `<scene>.json` directly to fix:
- Animation names (must match exactly what's in the GLB)
- Timing (adjust `start_second` / `end_second`)
- Rotations (adjust `start_rotation` / `end_rotation` in degrees)
- `lower_body_lock` (add or remove for seated characters)

After editing JSON, regenerate without re-calling the LLM:
```bash
python3 pipeline.py --regen <scene>.json
```

### Phase 2: Scene → Cameras

```bash
python3 pipeline.py --cameras-only \
  --blend <scene>.blend \
  --json <scene>.json
```

1. `camera_setup.py` calls the LLM with the scene JSON + screenplay
2. LLM returns a camera shots plan
3. The plan is converted to a Blender script
4. Blender opens the adjusted `.blend`, reads evaluated character positions, places cameras
5. Saves `<scene>_cameras.blend` with timeline markers for auto-switching

---

## Timing Reference

The pipeline works in seconds. Blender uses frames (default: 24 fps).

| Action | Typical duration |
|--------|----------------|
| Entering a room (walk-in) | 1.5–3s |
| Short dialogue line | 1–2s |
| Turning to face someone | 0.75s (injected automatically) |
| Reaching for an object | 0.5–1s |
| Full scene | 10–20s typical |

The LLM tries to space events naturally. You can always edit `duration_seconds` and the `start_second`/`end_second` values in the JSON to match your intended pacing.

---

## Lower-Body Lock: Seated + Active

To have a character sit while their upper body does something (wave, hold a gun, gesture):

```json
{
  "action_filter":   "Man_Idle",
  "lower_body_lock": "Man_Sitting",
  "start_second":    0,
  "end_second":      15
}
```

- Lower body (hips, legs, feet) → locked to `Man_Sitting` pose
- Upper body (spine, chest, arms, head) → plays `Man_Idle`

For the final action reveal (e.g. pulling out a gun):
```json
{
  "action_filter":   "Female_Punch",
  "lower_body_lock": "Female_Sitting",
  "start_second":    14,
  "end_second":      15
}
```

---

## Troubleshooting Common Output Issues

### Character is lying flat on the ground
The initial Z-rotation from the GLB import is captured and preserved. This shouldn't happen with Animated Men/Women packs. If it occurs, the armature's rest rotation is being overridden — check the `start_rotation` field in the JSON.

### Character walks backward
Check that `end_position Y < start_position Y`. Characters face −Y, so forward movement decreases Y.

### Characters standing on top of each other
The post-processor separates characters that are too close, but sometimes they still overlap. Edit their `start_position` X values to be at least 0.8m apart.

### Wrong character is using the wrong animation
Action lookup matches by stripping `ArmatureName|` prefix and `.001` suffixes from NLA action names. If a character picks up another character's blended action, it's because the blended action name contains a matching substring — check that character names in the JSON are unique.

### Prop is floating or inside the hand mesh
Props are parented to the named bone with `matrix_parent_inverse = Identity`. Small offsets come from the bone tip position. Adjust in Blender after Phase 1 (the adjustment is visual only; Phase 2 doesn't move props).

### Gun is visible from the start (should be hidden)
Ensure `reveal_at_second` is set in the props array. The pipeline keyframes `hide_viewport` and `hide_render` on the prop object.

### LLM gives wrong timing / narrative doesn't flow
Use a more capable LLM backend: `--backend anthropic --model claude-sonnet-4-5`. Groq (free, default) is fast but less coherent on complex multi-character scenes. Alternatively, edit the JSON manually after Phase 1.
