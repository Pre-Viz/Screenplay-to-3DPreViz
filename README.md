# 🎬 Screenplay-to-Blender Pre-Visualization Pipeline

> **Automated 3D pre-visualization for low-budget filmmakers** — paste a screenplay scene, get a Blender file with animated characters, props, environment, and a multi-camera cut sequence.

---

## What It Does

This pipeline takes a raw screenplay excerpt (or a PDF / .fountain file) and produces a fully animated Blender pre-visualization in two phases:

```
Phase 1 ── Screenplay text
           │
           ▼ (LLM interprets scene)
           Blender scene (.blend)
           • Characters with multi-segment animations
           • Props attached to character hands
           • Environment (pre-built or procedural)
           • Lower-body-lock for seated characters
           │
           [You review & adjust in Blender]
           │
Phase 2 ── Blender scene
           │
           ▼ (LLM plans camera work)
           Camera-ready scene (_cameras.blend)
           • Multiple cinematic cameras
           • Shot types: ECU / CU / MCU / LS / WA
           • Movements: crane, tilt, push-in, orbit…
           • Timeline markers for automatic cuts
```

---

## Setup

### 1. Install Blender

Download and install **Blender 4.4+ or 5.x** (tested on 5.2) from [blender.org](https://www.blender.org/download/).  
The pipeline calls Blender in background mode — make sure the `blender` command is on your PATH, or that it lives at `/Applications/Blender.app/Contents/MacOS/Blender` (macOS default).

### 2. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set an LLM API key

The pipeline uses an LLM to convert screenplay text into a structured scene. At least one API key is required. **Groq is free and the default.**

```bash
export GROQ_API_KEY=your_key_here        # https://console.groq.com  (free)
export ANTHROPIC_API_KEY=your_key_here   # https://console.anthropic.com
export GEMINI_API_KEY=your_key_here      # https://aistudio.google.com
export OPENAI_API_KEY=your_key_here      # https://platform.openai.com
```

Add the export to your `~/.zshrc` (or `~/.bashrc`) to make it permanent.

### 4. Add the asset library

The `assets/` folder is not included in this repository (binary GLB files, ~200 MB). You need to obtain the asset packs and place them in `assets/` following the folder structure documented in the [Asset Folder Structure](#-complete-asset-folder-structure) section below.

The pipeline reads `README.md` at runtime to know which assets are available, so the folder names must match exactly.

---

## Optional: BlenderMCP (Recommended for Best Results)

**[BlenderMCP](https://github.com/ahujasid/blender-mcp)** connects Blender directly to Claude AI via the Model Context Protocol, letting an AI agent interact with your open Blender scene in real time. This is very useful for:

- Fine-tuning character positions and rotations after Phase 1 without manually hunting through Blender's UI
- Diagnosing why an animation looks off ("what is the Z position of the DAVID armature?")
- Quickly applying transforms by describing them in plain English

### Installing BlenderMCP

**Step 1 — Install `uv`** (required by BlenderMCP):

```bash
# macOS
brew install uv
```

**Step 2 — Add to Cursor** (Settings → MCP → Add new global MCP server):

```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["blender-mcp"]
    }
  }
}
```

**Step 3 — Install the Blender addon**:

1. Download `addon.py` from [github.com/ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)
2. In Blender: **Edit → Preferences → Add-ons → Install…** → select `addon.py`
3. Enable "Interface: Blender MCP"
4. In the 3D View sidebar (**N** key) → **BlenderMCP** tab → **Connect to Claude**

Once connected, you can ask Cursor's AI to inspect or adjust your open Blender scene directly — no Python console required.

---

## Quick Start

### Run the full pipeline

```bash
python3 pipeline.py "INT. BAR - NIGHT

DAVID sits at the bar. The BARTENDER walks over.
AMANDA sits beside David.
AMANDA: Buy me a drink, cowboy?
Amanda slowly reveals a pistol."
```

This runs both phases and writes everything to `output/`:
- `int__bar___night.json` — editable scene configuration
- `int__bar___night.blend` — Phase 1 Blender scene
- `int__bar___night_cameras.blend` — Phase 2 scene with cameras

Add `--scene-only` to stop after Phase 1 so you can adjust the scene before adding cameras.

### Review and adjust in Blender

Open `output/int__bar___night.blend`. Reposition characters, fix scales, adjust rotations. Save the file.

### Add cameras (Phase 2)

```bash
python3 pipeline.py --cameras-only \
  --blend output/int__bar___night.blend \
  --json output/int__bar___night.json
```

This produces `int__bar___night_cameras.blend` — fully camera-ready with timeline markers.

### Other useful flags

```bash
# Use a different LLM (better narrative coherence)
python3 pipeline.py --backend anthropic "INT. KITCHEN - DAY ..."

# Read screenplay from a file
python3 pipeline.py --file my_scene.pdf

# Tell Phase 1 the blocking and timing you want (see "Recommended Workflow" below)
python3 pipeline.py --file my_scene.txt --scene-only \
  --direction "A and B talk for 3 s, then A walks to B, they talk for 2 s,
  B turns to face A, 3 s of talk, then B walks past A and A stays put."

# Tell Phase 2 the shots you want, in plain words
python3 pipeline.py --cameras-only --blend scene.blend --json scene.json \
  --shotlist "A wide until A arrives, then a CU on A, then a CU on B, then follow B
  from behind as B walks past A, and settle on A until the end."

# Rebuild .blend from a manually edited JSON (no LLM re-call)
python3 pipeline.py --regen --json output/int__bar___night.json

# Use your own hand-crafted camera shots file
python3 pipeline.py --cameras-only --blend scene.blend --json scene.json \
  --cameras-json my_cameras.json
```

---

## 🎬 Recommended Workflow & Tips (read this first)

The pipeline is built to give you a usable base quickly; you then direct it and make targeted
fixes (by hand or through BlenderMCP). These habits avoid the most common mistakes.

### 1. Characters: Ultimate Modular by default

The pipeline picks characters from the **Ultimate Modular** packs by default, because they
have `Interact` (a talking / explaining gesture) and `Wave`, which the Animated packs don't.
They can also sit (see [Lower-body lock](#-animation-quick-reference)).

| Who | Default models (priority order) |
|-----|---------------------------------|
| Women | `Animated Woman.glb`, `Animated Woman-nIItLV9nxS.glb` |
| Men | `Casual Character.glb`, `Hoodie Character.glb`, `Beach Character.glb` |

Costumes are picked from context instead: `Business Man` / `Suit` for an office, `Witch` for
witchcraft, `Swat` for police, `Soldier` for military, `King` / `Medieval` for fantasy,
`Astronaut` / `Sci Fi Character` for space, `Farmer`, `Worker`, `Adventurer`, `Punk`.
Each character in a scene gets a different model. If you want specific ones, say so in
`--direction` (e.g. "A is the Hoodie Character").

### 2. Talking scenes: characters take turns

In dialogue the pipeline alternates short `Interact` turns (0.5–0.75 s) between speakers,
following the line order, while the listener stays `Idle`. Both characters gesturing at the
same time looks like they are shouting over each other, so ask for this explicitly if you
edit the JSON by hand. Seated characters do the same with `lower_body_lock` on every turn.

### 3. Describe the blocking and timing before adjusting by hand

Before touching the scene manually, describe **who does what, when, and for how long** —
through `--direction`, or by telling your MCP agent. For example:

> A and B talk for 3 seconds, then A turns away from B for 2 seconds and turns back to B.
> B then walks past A in anger (3 seconds).

This gives the pipeline a clear timeline to build from, and it gives Phase 2 named beats
to cut on. You can then refer to them when directing cameras ("cut to B as he starts walking").
The most useful beats to spell out are **facing** (who looks at whom, who turns away),
**walking** (from where to where, and past whom), and **the order of events**; the pipeline
fills the talking in between.

### 4. Phase 2: describe your shot list, then adjust

Instead of accepting the automatic shot plan, describe the shots you want with `--shotlist`
(or to your MCP agent), referencing the beats from step 3:

> A wide as he walks in; a close-up of him once he's there; then her; then follow her from
> behind as she walks past him, and settle on him until the end.

The camera code handles placement, framing on the characters' heads, following moving
characters, and keeping cameras out of walls and furniture. Then make the final manual
tweaks. This is much faster than building cameras by hand. Shot options the camera code
understands, beyond the basic movements: `movement_end_second` (a move finishes early and
holds), `pan_to` (the camera turns from one character to another), and `height_offset`
(raise the camera to see over counters or tables).

### 5. Manual adjustments: move the RootNode, not the character

Each imported character is parented to an unanimated Empty (`RootNode`, `RootNode.001`, ...).
Characters' location and rotation are keyframed, so **moving a character directly reverts as
soon as the timeline plays**. Move or rotate its `RootNode` instead — the whole animation moves
with it. To rotate in place, first set the pivot to the character (Shift+S → Cursor to
Selected, Pivot Point → 3D Cursor).

Change **timing** through the JSON and `--regen`, not by dragging keyframes: Phase 2 plans its
cuts from the JSON's timeline. Do timing changes first, then placement, since `--regen`
rebuilds the scene.

### 6. Adding characters and locations

If you need a specific character or set, import it into `assets/`, then update **both** this
README and the asset list the Phase 1 LLM actually reads (`ASSET_REFERENCE` at the top of
`screenplay_to_scene.py`) — see `HOW_TO_ADD_NEW_ASSETS.md`.

To choose what to use or add, browse the source libraries:
[Quaternius on Poly Pizza](https://poly.pizza/u/Quaternius) (characters and animation packs;
also [quaternius.com](https://quaternius.com)) and [Kenney](https://kenney.nl/assets) (sets and
props). Looking there first lets you name specific characters for a scene, and the exact
animations you want, when you direct it.

---

## Documentation

| File | Contents |
|------|----------|
| This README | Setup, Quick Start, full asset reference, JSON format |
| `SCREENPLAY_TO_SCENE_GUIDE.md` | How the LLM reads screenplays, writing tips, troubleshooting |
| `SYSTEM_DATA_FLOW.md` | Technical architecture, data flow, post-processing |
| `HOW_TO_ADD_NEW_ASSETS.md` | Adding new GLB packs or character models |
| `ENVIRONMENT_GENERATOR_IMPROVEMENTS.md` | Location support reference |

---

## 📁 Core Files

| File | Purpose |
|------|---------|
| `pipeline.py` | **Main entry point** — orchestrates Phase 1 + Phase 2 |
| `screenplay_to_scene.py` | Phase 1: Screenplay text → scene JSON via LLM |
| `camera_setup.py` | Phase 2: Scene JSON + .blend → multi-camera .blend |
| `flexible_scene_generator_optimized.py` | Blender scene builder (called by pipeline) |
| `llm_client.py` | Unified LLM interface (Groq / Anthropic / Gemini / OpenAI) |
| `location_environment_generator.py` | Generates environment asset lists for a location |
| `screenplay_parser.py` | Lightweight screenplay text utilities |
| `build_character_glb.py` | Utility: merge per-animation FBX files into a single GLB |
| `honorsCamera/` | Blender camera plugin scripts (Phase 2 uses these internally) |

## 🎭 Character Assets & Animations

### Ultimate Modular Women Pack (default for women)

- **Default**: `Animated Woman.glb`, `Animated Woman-nIItLV9nxS.glb`
- **Costumes**: `Suit`, `Witch`, `Soldier`, `Medieval`, `Adventurer`, `Worker`, `Punk`, `Sci Fi Character`
- **Path**: `assets/Ultimate Modular Women Pack-glb/<name>.glb`
- **Armature**: `CharacterArmature` · **Scale**: `2.5x` · **Grip bones**: `Wrist.R` / `Wrist.L`
- **Animations**: same as the Men pack below

### Ultimate Modular Men Pack (default for men)

- **Default** (priority order): `Casual Character.glb`, `Hoodie Character.glb`, `Beach Character.glb`
- **Costumes**: `Business Man`, `Swat`, `Astronaut`, `King`, `Farmer`, `Worker`, `Adventurer`, `Punk`
- **Path**: `assets/Ultimate Modular Men Pack-glb/<name>.glb`
- **Armature**: `CharacterArmature` · **Scale**: `2.5x` · **Grip bones**: `Wrist.R` / `Wrist.L`
- **Animations** (all 21 Ultimate Modular characters share these 24): `Idle`, `Idle_Neutral`, `Walk`,
  `Run`, `Run_Back`, `Run_Left`, `Run_Right`, `Death`, `Roll`, `Punch_Left`, `Punch_Right`,
  `Kick_Left`, `Kick_Right`, `Sword_Slash`, `Idle_Sword`, `Gun_Shoot`, `Idle_Gun`,
  `Idle_Gun_Pointing`, `Idle_Gun_Shoot`, `Run_Shoot`, `HitRecieve`, `HitRecieve_2`, `Wave`, `Interact`

### Animated Men Pack (fallback)

- **Path**: `assets/Animated Men Pack-glb/Man.glb` (or Man in Suit, Man in Long Sleeves)
- **Armature**: `HumanArmature` · **Scale**: `1x` · **Grip bones**: `Palm.R` / `Palm.L`
- **Animations**: `Man_Idle`, `Man_Walk`, `Man_Run`, `Man_Death`, `Man_Punch`, `Man_Jump`, `Man_Clapping`, `Man_Sitting`, `Man_SwordSlash`

### Animated Women Pack (fallback)

- **Path**: `assets/Animated Women Pack-glb/Woman.glb` (or Woman Casual, Woman in Dress, Woman in Tank Top)
- **Armature**: `HumanArmature` · **Scale**: `1x` · **Grip bones**: `Palm.R` / `Palm.L`
- **Animations**: `Female_Idle`, `Female_Walk`, `Female_Run`, `Female_Death`, `Female_Punch`, `Female_Jump`, `Female_Clapping`, `Female_Sitting`, `Female_SwordSlash`

Use the Animated packs only when a scene needs one of their unique clips (Clapping, Jump).
Animation names differ between the packs; if the LLM mixes them up, post-processing maps
them to the right pack (e.g. `Man_Walk` → `Walk` on an Ultimate Modular character).

### Animals (Wolf, Fox, Shiba Inu, Horse, Cow, etc.)

- **Armature**: `AnimalArmature`
- **Scale**: `1x`
- **Animations**: `Idle`, `Walk`, `Gallop`, `Death`, `Eating`, `Attack`, `Jump_ToIdle`, `Attack_Headbutt`, `Attack_Kick`

## 🎯 Animation Quick Reference

| Action       | Ultimate Modular (CharacterArmature) — default | Animated Pack (HumanArmature) | Animals  |
|--------------|---------------------------------------|-------------------------------|----------|
| Stand still  | Idle                                  | Man_Idle / Female_Idle        | Idle     |
| **Talk**     | **Interact** (0.5–0.75 s turns, alternating) | *(none — Idle)*        | *(none)* |
| Walk         | Walk                                  | Man_Walk / Female_Walk        | Walk     |
| Run          | Run                                   | Man_Run / Female_Run          | Gallop   |
| Sitting      | lower_body_lock `Man_Sitting` / `Female_Sitting` | Man_Sitting / Female_Sitting (as lower_body_lock) | *(none)* |
| Punch/Fight  | Punch_Left, Kick_Right                | Man_Punch / Female_Punch      | Attack   |
| Wave/Greet   | Wave                                  | Man_Clapping / Female_Clapping| *(none)* |
| Hit / flinch | HitRecieve                            | *(none)*                      | *(none)* |
| Die          | Death                                 | Man_Death / Female_Death      | Death    |
| Shoot (stand)| Gun_Shoot, Idle_Gun                   | *(none)*                      | *(none)* |

> **Lower-body lock**: To have a character sit while their upper body performs another animation
> (talking, idling, shooting), set `lower_body_lock` to `Man_Sitting` / `Female_Sitting` on each
> seated segment. This works for **both** packs: for Ultimate Modular characters the pipeline
> imports the sitting legs from the Animated pack and fits them to the rig automatically.

## ⚠️ CRITICAL: Character Movement Rules

### Default Character Orientation

**ALL CHARACTERS FACE NEGATIVE Y DIRECTION (-Y axis) BY DEFAULT**

### Movement Direction Rules

**ALWAYS use these rules to avoid backward movement:**

| Movement Type   | Start Position Y | End Position Y | Result                   |
| --------------- | ---------------- | -------------- | ------------------------ |
| **Forward** ✅  | Higher number    | Lower number   | Character moves forward  |
| **Backward** ❌ | Lower number     | Higher number  | Character moves backward |

### Correct Examples

```json
// ✅ FORWARD MOVEMENT (Natural running/walking)
"start_position": [0, 10, 0],
"end_position": [0, 0, 0]      // 10 → 0 = Forward

"start_position": [0, 5, 0],
"end_position": [0, -5, 0]     // 5 → -5 = Forward

// ❌ BACKWARD MOVEMENT (Avoid unless intentional)
"start_position": [0, 0, 0],
"end_position": [0, 10, 0]     // 0 → 10 = Backward
```

### Quick Check

- **If end_position Y > start_position Y → Character runs BACKWARD**
- **If end_position Y < start_position Y → Character runs FORWARD**

## 🏃‍♀️ Chase Scene Positioning

### Positioning Rules

**Higher Y values = Further back, Lower Y values = Closer to camera**

### Chase Scene Examples

```json
// ✅ WOMAN CHASING DOG
{
  "name": "DOG",
  "start_position": [0, 5, 0],    // Dog ahead (closer to camera)
  "end_position": [0, 0, 0]       // Dog runs forward
},
{
  "name": "WOMAN",
  "start_position": [0, 10, 0],   // Woman behind (further from camera)
  "end_position": [0, 5, 0]       // Woman chases dog
}
```

### ⚠️ CRITICAL: Complete Fix Checklist

When fixing movement issues, check BOTH:

1. **✅ Direction**: Ensure forward movement (start_Y > end_Y)
2. **✅ Positioning**: Ensure correct object relationships (chaser behind target)
3. **✅ Scene Logic**: Verify the scene makes narrative sense

## 🌍 Environment Assets by Location

### 🌲 Nature/Forest/Park Locations

- **Trees**: `assets/Stylized Nature MegaKit.undefined-glb/Twisted Tree.glb`
- **Plants**: `assets/Stylized Nature MegaKit.undefined-glb/Bush with Flowers.glb`
- **Ground**: `assets/Stylized Nature MegaKit.undefined-glb/Grass.glb`
- **Rocks**: `assets/Stylized Nature MegaKit.undefined-glb/Rock Medium.glb`
- **Paths**: `assets/Stylized Nature MegaKit.undefined-glb/Rock Path Round Wide.glb`

### 🏢 City/Urban Locations

- **Buildings**: `assets/kenney_city-kit-commercial_2.1/building-a.glb`
- **Skyscrapers**: `assets/kenney_city-kit-commercial_2.1/building-skyscraper-a.glb`
- **Vehicles**: `assets/Cars Bundle-glb/Police Car.glb`, `assets/Cars Bundle-glb/Taxi.glb`

### 🏠 Indoor/House Locations

- **Furniture**: `assets/Ultimate House Interior Pack-glb/Couch Large.glb`
- **Tables**: `assets/Ultimate House Interior Pack-glb/Table Round Large.glb`
- **Lights**: `assets/Ultimate House Interior Pack-glb/Light Ceiling.glb`

### 🏰 Medieval/Fantasy Locations

- **Buildings**: `assets/Medieval Village Pack-glb/Fantasy House.glb`
- **Props**: `assets/Medieval Village Pack-glb/Well.glb`, `assets/Medieval Village Pack-glb/Cart.glb`

## 🎬 Common Scene Locations & Required Assets

### 🛏️ **BEDROOM** (INT. BEDROOM)

**Essential Assets:**

- **Bed**: `assets/Ultimate House Interior Pack-glb/Bed King.glb` or `assets/Ultimate House Interior Pack-glb/Bed Single.glb`
- **Night Stand**: `assets/Ultimate House Interior Pack-glb/Night Stand.glb`
- **Drawer**: `assets/Ultimate House Interior Pack-glb/Drawer.glb`
- **Chair**: `assets/Ultimate House Interior Pack-glb/Chair.glb`
- **Table**: `assets/Ultimate House Interior Pack-glb/Table Round Small.glb`
- **Lighting**: `assets/Ultimate House Interior Pack-glb/Light Ceiling.glb`
- **Decor**: `assets/Ultimate House Interior Pack-glb/Houseplant.glb`

**Ground Material**: Wooden floor (brown/beige colors)

### 🌲 **FOREST/PARK** (EXT. FOREST/PARK)

**Essential Assets:**

- **Trees**: `assets/Stylized Nature MegaKit.undefined-glb/Twisted Tree.glb`, `assets/Stylized Nature MegaKit.undefined-glb/Tree.glb`
- **Bushes**: `assets/Stylized Nature MegaKit.undefined-glb/Bush with Flowers.glb`, `assets/Stylized Nature MegaKit.undefined-glb/Bush.glb`
- **Path**: `assets/Stylized Nature MegaKit.undefined-glb/Rock Path Round Wide.glb`
- **Rocks**: `assets/Stylized Nature MegaKit.undefined-glb/Rock Medium.glb`
- **Ground Cover**: `assets/Stylized Nature MegaKit.undefined-glb/Grass.glb`, `assets/Stylized Nature MegaKit.undefined-glb/Clover.glb`
- **Flowers**: `assets/Stylized Nature MegaKit.undefined-glb/Flower Group.glb`
- **Plants**: `assets/Stylized Nature MegaKit.undefined-glb/Fern.glb`

**Ground Material**: Green grass (natural green colors)

### 🏢 **OFFICE** (INT. OFFICE)

**Essential Assets:**

- **Desk**: `assets/Furniture Pack-glb/Desk.glb`
- **Office Chair**: `assets/Furniture Pack-glb/Office Chair.glb`
- **Regular Chair**: `assets/Ultimate House Interior Pack-glb/Chair.glb`
- **Table**: `assets/Ultimate House Interior Pack-glb/Table Round Large.glb`
- **Bookcase**: `assets/Furniture Pack-glb/Bookcase with Books.glb`
- **Lighting**: `assets/Ultimate House Interior Pack-glb/Light Ceiling.glb`
- **Trashcan**: `assets/Ultimate House Interior Pack-glb/Trashcan.glb`

**Ground Material**: Office carpet (gray/blue colors)

### ☕ **CAFE/RESTAURANT** (INT. CAFE)

**Essential Assets:**

- **Tables**: `assets/Ultimate House Interior Pack-glb/Table Round Small.glb`, `assets/Furniture Pack-glb/Table.glb`
- **Chairs**: `assets/Ultimate House Interior Pack-glb/Chair.glb`, `assets/Furniture Pack-glb/Chair.glb`
- **Counter**: `assets/Ultimate House Interior Pack-glb/Kitchen Sink.glb` (as counter)
- **Stools**: `assets/Ultimate House Interior Pack-glb/Stool.glb`
- **Lighting**: `assets/Ultimate House Interior Pack-glb/Light Ceiling.glb`, `assets/Ultimate House Interior Pack-glb/Table Lamp.glb`
- **Plants**: `assets/Ultimate House Interior Pack-glb/Houseplant.glb`
- **Decor**: `assets/Ultimate House Interior Pack-glb/Cactus.glb`

**Ground Material**: Tile floor (light brown/cream colors)

### 🛣️ **HIGHWAY/STREET** (EXT. HIGHWAY)

**Essential Assets:**

- **Vehicles**: `assets/Cars Bundle-glb/Car.glb`, `assets/Cars Bundle-glb/Police Car.glb`, `assets/Cars Bundle-glb/Taxi.glb`
- **Buildings**: `assets/kenney_city-kit-commercial_2.1/building-a.glb`, `assets/kenney_city-kit-commercial_2.1/building-b.glb`
- **Street Elements**: `assets/Stylized Nature MegaKit.undefined-glb/Rock Path Square Wide.glb` (as road)
- **Urban Nature**: `assets/Stylized Nature MegaKit.undefined-glb/Tree.glb` (sparse)
- **Props**: `assets/Medieval Village Pack-glb/Barrel.glb` (as street barriers)

**Ground Material**: Asphalt/concrete (dark gray colors)

### 🏠 **LIVING ROOM** (INT. LIVING ROOM)

**Essential Assets:**

- **Couch**: `assets/Ultimate House Interior Pack-glb/Couch Large.glb`, `assets/Ultimate House Interior Pack-glb/L Couch.glb`
- **Coffee Table**: `assets/Ultimate House Interior Pack-glb/Table Round Small.glb`
- **TV Stand**: `assets/Ultimate House Interior Pack-glb/Shelf Large.glb`
- **Chairs**: `assets/Ultimate House Interior Pack-glb/Chair.glb`
- **Lighting**: `assets/Ultimate House Interior Pack-glb/Light Floor.glb`, `assets/Ultimate House Interior Pack-glb/Table Lamp.glb`
- **Decor**: `assets/Ultimate House Interior Pack-glb/Houseplant.glb`, `assets/Ultimate House Interior Pack-glb/Round Rug.glb`
- **Fireplace**: `assets/Ultimate House Interior Pack-glb/Fireplace.glb`

**Ground Material**: Wooden floor with rugs (warm brown colors)

### 🍳 **KITCHEN** (INT. KITCHEN)

**Essential Assets:**

- **Appliances**: `assets/Ultimate House Interior Pack-glb/Kitchen Fridge.glb`, `assets/Ultimate House Interior Pack-glb/Oven.glb`
- **Sink**: `assets/Ultimate House Interior Pack-glb/Kitchen Sink.glb`
- **Table**: `assets/Ultimate House Interior Pack-glb/Table Round Large.glb`
- **Chairs**: `assets/Ultimate House Interior Pack-glb/Chair.glb`, `assets/Ultimate House Interior Pack-glb/Stool.glb`
- **Storage**: `assets/Ultimate House Interior Pack-glb/Shelf Large.glb`
- **Lighting**: `assets/Ultimate House Interior Pack-glb/Light Ceiling.glb`
- **Trashcan**: `assets/Ultimate House Interior Pack-glb/Trashcan.glb`

**Ground Material**: Tile floor (white/light colors)

### 🏰 **MEDIEVAL VILLAGE** (EXT. VILLAGE)

**Essential Assets:**

- **Buildings**: `assets/Medieval Village Pack-glb/Fantasy House.glb`, `assets/Medieval Village Pack-glb/Fantasy Inn.glb`
- **Market**: `assets/Medieval Village Pack-glb/Market Stand.glb`
- **Props**: `assets/Medieval Village Pack-glb/Well.glb`, `assets/Medieval Village Pack-glb/Cart.glb`
- **Storage**: `assets/Medieval Village Pack-glb/Barrel.glb`, `assets/Medieval Village Pack-glb/Crate.glb`
- **Seating**: `assets/Medieval Village Pack-glb/Bench.glb`
- **Paths**: `assets/Medieval Village Pack-glb/Path Straight.glb`
- **Natural**: `assets/Medieval Village Pack-glb/Hay.glb`, `assets/Stylized Nature MegaKit.undefined-glb/Tree.glb`

**Ground Material**: Dirt/stone (brown/gray colors)

### 🏙️ **CITY STREET** (EXT. CITY)

**Essential Assets:**

- **Buildings**: `assets/kenney_city-kit-commercial_2.1/building-skyscraper-a.glb`, `assets/kenney_city-kit-commercial_2.1/building-c.glb`
- **Vehicles**: `assets/Cars Bundle-glb/Taxi.glb`, `assets/Cars Bundle-glb/Police Car.glb`, `assets/Cars Bundle-glb/SUV.glb`
- **Street Furniture**: `assets/Medieval Village Pack-glb/Bench.glb` (as city bench)
- **Urban Trees**: `assets/Stylized Nature MegaKit.undefined-glb/Tree.glb` (minimal, along sidewalks)
- **Props**: `assets/Ultimate House Interior Pack-glb/Trashcan Large.glb`

**Ground Material**: Concrete/asphalt (gray colors)

### 🏕️ **CAMPING/WILDERNESS** (EXT. CAMPSITE)

**Essential Assets:**

- **Shelter**: `assets/Survival Pack-glb/Tent.glb`
- **Fire**: `assets/Survival Pack-glb/Bonfire.glb`
- **Tools**: `assets/Survival Pack-glb/Axe.glb`, `assets/Survival Pack-glb/Shovel.glb`
- **Supplies**: `assets/Survival Pack-glb/Backpack.glb`, `assets/Survival Pack-glb/Water Bottle.glb`
- **Cooking**: `assets/Survival Pack-glb/Pan.glb`, `assets/Survival Pack-glb/Pot.glb`
- **Nature**: `assets/Stylized Nature MegaKit.undefined-glb/Pine.glb`, `assets/Stylized Nature MegaKit.undefined-glb/Rock Medium.glb`
- **Ground**: `assets/Stylized Nature MegaKit.undefined-glb/Grass.glb`

**Ground Material**: Natural grass/dirt (green/brown colors)

## 🎯 Location Asset Selection Rules

### **Asset Count Guidelines:**

- **Small Rooms** (bedroom, office): 5-8 assets
- **Large Rooms** (living room, kitchen): 8-12 assets
- **Outdoor Scenes** (forest, city): 10-15 assets
- **Complex Scenes** (village, campsite): 12-20 assets

### **Scattering Patterns:**

- **Indoor**: Organized placement (furniture against walls)
- **Outdoor Natural**: Random scattering (trees, rocks, bushes)
- **Urban**: Grid-like placement (buildings, vehicles)
- **Paths**: Linear placement (road elements, street furniture)

### **Material Colors by Location:**

- **Indoor**: Warm colors (browns, creams, soft lighting)
- **Forest**: Natural greens and browns
- **City**: Cool grays and blues
- **Medieval**: Earth tones (browns, grays, muted colors)
- **Beach/Desert**: Sandy yellows and blues

## 📁 Complete Asset Folder Structure

```
assets/
├── Animated Animal Pack-glb
│   ├── Alpaca.glb
│   ├── Bull.glb
│   ├── Cow.glb
│   ├── Deer.glb
│   ├── Donkey.glb
│   ├── Fox.glb
│   ├── Horse.glb
│   ├── Husky.glb
│   ├── Shiba Inu.glb
│   ├── Stag.glb
│   ├── White Horse.glb
│   └── Wolf.glb
├── Animated Men Pack-glb
│   ├── Man in Long Sleeves.glb
│   ├── Man in Suit.glb
│   ├── Man-fjHyMd5Wxw.glb
│   └── Man.glb
├── Animated Women Pack-glb
│   ├── Woman Casual.glb
│   ├── Woman in Dress.glb
│   ├── Woman in Tank Top.glb
│   └── Woman.glb
├── Cars Bundle-glb
│   ├── Car-unqqkULtRU.glb
│   ├── Car.glb
│   ├── Police Car.glb
│   ├── SUV.glb
│   ├── Sports Car-1mkmFkAz5v.glb
│   ├── Sports Car.glb
│   └── Taxi.glb
├── Food Kit-glb
│   ├── Apple Half.glb
│   ├── Apple.glb
│   ├── Avocado Half.glb
│   ├── Bacon.glb
│   ├── Bag Flat.glb
│   ├── Bag.glb
│   ├── Banana.glb
│   ├── Barrel.glb
│   ├── Beet.glb
│   ├── Bottle Ketchup.glb
│   ├── Bottle Musterd.glb
│   ├── Bowl Broth.glb
│   ├── Bowl Cereal.glb
│   ├── Bowl Soup.glb
│   ├── Bread.glb
│   ├── Broccoli.glb
│   ├── Burger Cheese.glb
│   ├── Burger.glb
│   ├── Cabbage.glb
│   ├── Cake Birthday.glb
│   ├── Cake Slicer.glb
│   ├── Cake.glb
│   ├── Can Open.glb
│   ├── Can Small.glb
│   ├── Can.glb
│   ├── Candy Bar Wrapper.glb
│   ├── Capsicum.glb
│   ├── Carrot.glb
│   ├── Carton Small.glb
│   ├── Carton.glb
│   ├── Cauliflower.glb
│   ├── Cheese Cut.glb
│   ├── Cheese Slicer.glb
│   ├── Cherries.glb
│   ├── Chinese.glb
│   ├── Chocolate Wrapper.glb
│   ├── Chocolate.glb
│   ├── Chopstick Fancy.glb
│   ├── Cocktail.glb
│   ├── Coconut Half.glb
│   ├── Cookie Chocolate.glb
│   ├── Cookie.glb
│   ├── Cooking Fork.glb
│   ├── Cooking Knife Chopping.glb
│   ├── Cooking Knife.glb
│   ├── Cooking Spatula.glb
│   ├── Cooking Spoon.glb
│   ├── Corn Dog.glb
│   ├── Corn.glb
│   ├── Croissant.glb
│   ├── Cup Tea-M2sVC8jbmi.glb
│   ├── Cup Tea.glb
│   ├── Cup.glb
│   ├── Cupcake.glb
│   ├── Cutting Board.glb
│   ├── Donut Chocolate.glb
│   ├── Donut Sprinkles.glb
│   ├── Egg Cooked.glb
│   ├── Egg Cup.glb
│   ├── Egg.glb
│   ├── Eggplant.glb
│   ├── Fish Bones.glb
│   ├── Fish.glb
│   ├── Frappe.glb
│   ├── Fries.glb
│   ├── Frying Pan.glb
│   ├── Ginger Bread Cutter.glb
│   ├── Ginger Bread.glb
│   ├── Glass Wine.glb
│   ├── Grapes.glb
│   ├── Honey.glb
│   ├── Hot Dog.glb
│   ├── Ice Cream.glb
│   ├── Knife Block.glb
│   ├── Leek.glb
│   ├── Lemon Half.glb
│   ├── Lemon.glb
│   ├── Loaf Baguette.glb
│   ├── Loaf Round.glb
│   ├── Loaf.glb
│   ├── Lollypop.glb
│   ├── Meat Patty.glb
│   ├── Meat Raw.glb
│   ├── Meat Ribs.glb
│   ├── Meat Sausage.glb
│   ├── Meat Tenderizer.glb
│   ├── Mincemeat Pie.glb
│   ├── Muffin.glb
│   ├── Mug.glb
│   ├── Mushroom Half.glb
│   ├── Mushroom.glb
│   ├── Mussel Open.glb
│   ├── Onion Half.glb
│   ├── Onion.glb
│   ├── Orange.glb
│   ├── Pan Stew.glb
│   ├── Pan.glb
│   ├── Pancakes.glb
│   ├── Peanut Butter.glb
│   ├── Pear Half.glb
│   ├── Pear.glb
│   ├── Pepper Mill.glb
│   ├── Pepper.glb
│   ├── Pie.glb
│   ├── Pineapple.glb
│   ├── Pizza Box.glb
│   ├── Pizza Cutter.glb
│   ├── Pizza.glb
│   ├── Popsicle Chocolate.glb
│   ├── Popsicle.glb
│   ├── Pot Stew.glb
│   ├── Pudding.glb
│   ├── Pumpkin Basic.glb
│   ├── Pumpkin.glb
│   ├── Radish.glb
│   ├── Rice Ball.glb
│   ├── Rolling Pin.glb
│   ├── Salad.glb
│   ├── Sandwich.glb
│   ├── Sausage.glb
│   ├── Shaker Salt.glb
│   ├── Skewer Vegetables.glb
│   ├── Soda Can Crushed.glb
│   ├── Soda Can.glb
│   ├── Soda Glass.glb
│   ├── Soda.glb
│   ├── Soy.glb
│   ├── Steamer.glb
│   ├── Strawberry.glb
│   ├── Styrofoam Dinner.glb
│   ├── Styrofoam.glb
│   ├── Sub.glb
│   ├── Sundae.glb
│   ├── Sushi Egg.glb
│   ├── Sushi Salmon.glb
│   ├── Taco.glb
│   ├── Tomato Slice.glb
│   ├── Tomato.glb
│   ├── Turkey.glb
│   ├── Utensil Fork.glb
│   ├── Utensil Knife.glb
│   ├── Utensil Spoon.glb
│   ├── Waffle.glb
│   ├── Watermelon.glb
│   ├── Whipped Cream.glb
│   ├── Whisk.glb
│   ├── Whole Ham.glb
│   └── Wine Red.glb
├── Furniture Pack-glb
│   ├── Bed Double.glb
│   ├── Bed Twin.glb
│   ├── Bookcase with Books.glb
│   ├── Chair-9kIjuRFMFw.glb
│   ├── Chair.glb
│   ├── Closet.glb
│   ├── Desk.glb
│   ├── Door-JuTzNjtD54.glb
│   ├── Door-QiMLelTBId.glb
│   ├── Door.glb
│   ├── Night Stand.glb
│   ├── Office Chair.glb
│   ├── Short Closet.glb
│   ├── Sofa-X5kQPKzAWp.glb
│   ├── Sofa-vuo7KBehok.glb
│   ├── Sofa.glb
│   ├── Stool.glb
│   ├── Table-yYEEJzKxb4.glb
│   └── Table.glb
├── Medieval Village Pack-glb
│   ├── Bag Open.glb
│   ├── Bag.glb
│   ├── Bags.glb
│   ├── Barrel.glb
│   ├── Bell Tower.glb
│   ├── Bell.glb
│   ├── Bench-7uSlZo3n9Y.glb
│   ├── Bench.glb
│   ├── Blacksmith.glb
│   ├── Bonfire.glb
│   ├── Cart.glb
│   ├── Cauldron.glb
│   ├── Crate.glb
│   ├── Door Round.glb
│   ├── Door Straight.glb
│   ├── Fantasy Barracks.glb
│   ├── Fantasy House-BH2XHWUNmF.glb
│   ├── Fantasy House-dcPho4SUA3.glb
│   ├── Fantasy House.glb
│   ├── Fantasy Inn.glb
│   ├── Fantasy Sawmill.glb
│   ├── Fantasy Stable.glb
│   ├── Fence.glb
│   ├── Gazebo.glb
│   ├── Hay.glb
│   ├── Market Stand-DGIM5HGISb.glb
│   ├── Market Stand.glb
│   ├── Mill.glb
│   ├── Package-kYvD6QCQRd.glb
│   ├── Package.glb
│   ├── Path Straight.glb
│   ├── Rocks.glb
│   ├── Round Window.glb
│   ├── Sawmill Saw.glb
│   ├── Smoke.glb
│   ├── Stairs.glb
│   ├── Well.glb
│   ├── Window-EY1zrFcme9.glb
│   └── Window.glb
├── Stylized Nature MegaKit.undefined-glb
│   ├── Bush with Flowers.glb
│   ├── Bush.glb
│   ├── Clover-u5SOgBFiut.glb
│   ├── Clover.glb
│   ├── Dead Tree-CD4edbPSGm.glb
│   ├── Dead Tree-Mcd2zYqyww.glb
│   ├── Dead Tree-MlmK5488ou.glb
│   ├── Dead Tree-n8FhMgMldD.glb
│   ├── Dead Tree.glb
│   ├── Fern.glb
│   ├── Flower Group-LqTljN6Wg2.glb
│   ├── Flower Group.glb
│   ├── Flower Petal-LqvxG9OBOU.glb
│   ├── Flower Petal-eVE0j49ux9.glb
│   ├── Flower Petal-niuBUEJdvM.glb
│   ├── Flower Petal-tzG4JcqYWs.glb
│   ├── Flower Petal.glb
│   ├── Flower Single-GvfHo0roi3.glb
│   ├── Flower Single.glb
│   ├── Grass Wispy-Msr9zx66VU.glb
│   ├── Grass Wispy.glb
│   ├── Grass.glb
│   ├── Mushroom Laetiporus.glb
│   ├── Mushroom.glb
│   ├── Pebble Round-KYtJ6JNXh2.glb
│   ├── Pebble Round-icVsN3lmVy.glb
│   ├── Pebble Round-kAMfq1uJUY.glb
│   ├── Pebble Round-nMf8LHOsbM.glb
│   ├── Pebble Round.glb
│   ├── Pebble Square-2YtLzwgsWp.glb
│   ├── Pebble Square-6juX57sLHe.glb
│   ├── Pebble Square-Mm4RMgwNO8.glb
│   ├── Pebble Square-l5XiYQj1oD.glb
│   ├── Pebble Square-s71L3q1nXN.glb
│   ├── Pebble Square.glb
│   ├── Pine-699sFuLCN2.glb
│   ├── Pine-79gmlLnweB.glb
│   ├── Pine-Zt62gceKXZ.glb
│   ├── Pine-rfnxJv0Rqa.glb
│   ├── Pine.glb
│   ├── Plant Big-MbhbP7JrTI.glb
│   ├── Plant Big.glb
│   ├── Plant-xH5gNlQxAZ.glb
│   ├── Plant.glb
│   ├── Rock Medium-JQxF95498B.glb
│   ├── Rock Medium-s1OJ3bBzqc.glb
│   ├── Rock Medium.glb
│   ├── Rock Path Round Small-GMttpOEFKT.glb
│   ├── Rock Path Round Small-yHEdadj5I0.glb
│   ├── Rock Path Round Small.glb
│   ├── Rock Path Round Thin.glb
│   ├── Rock Path Round Wide.glb
│   ├── Rock Path Square Smal-cI9XBpVijV.glb
│   ├── Rock Path Square Smal-w4TKZMjjcw.glb
│   ├── Rock Path Square Smal.glb
│   ├── Rock Path Square Thin.glb
│   ├── Rock Path Square Wide.glb
│   ├── Tall Grass.glb
│   ├── Tree-QVOop92WmG.glb
│   ├── Tree-aVOxaHRPWe.glb
│   ├── Tree-qZtx0AHhcy.glb
│   ├── Tree-t9KbsfYdXz.glb
│   ├── Tree.glb
│   ├── Twisted Tree-7PDBpElkQr.glb
│   ├── Twisted Tree-8oraKn9m0x.glb
│   ├── Twisted Tree-9aWlx82xUf.glb
│   ├── Twisted Tree-GVTsMmuzv7.glb
│   └── Twisted Tree.glb
├── Survival Pack-glb
│   ├── Axe.glb
│   ├── Backpack.glb
│   ├── Battery-MYa3uWdwPU.glb
│   ├── Battery.glb
│   ├── Bear Trap.glb
│   ├── Bonfire.glb
│   ├── Can Broken.glb
│   ├── Can Red.glb
│   ├── Can.glb
│   ├── Compass.glb
│   ├── First Aid Kit-wP00rePSRD.glb
│   ├── First Aid Kit.glb
│   ├── Flare Gun.glb
│   ├── Gas Can.glb
│   ├── Knife.glb
│   ├── Match Burnt.glb
│   ├── Match.glb
│   ├── Matchbox.glb
│   ├── Pan.glb
│   ├── Phone.glb
│   ├── Pot-fyweVKYu0K.glb
│   ├── Pot.glb
│   ├── Propane Tank.glb
│   ├── Radio.glb
│   ├── Raft Paddle.glb
│   ├── Raft.glb
│   ├── Shovel.glb
│   ├── Tent.glb
│   ├── Torch.glb
│   ├── Water Bottle.glb
│   ├── Wood Log.glb
│   └── Wooden Torch.glb
├── Ultimate Guns Pack-glb
│   ├── Assault Rifle-Bgvuu4CUMV.glb
│   ├── Assault Rifle-fpLucho45C.glb
│   ├── Assault Rifle.glb
│   ├── Bayonet.glb
│   ├── Bipod.glb
│   ├── Bullpup.glb
│   ├── Pistol-52kQzphmeF.glb
│   ├── Pistol-J3i9KDQ3kt.glb
│   ├── Pistol-Z7aOjJu583.glb
│   ├── Pistol.glb
│   ├── Revolver-9C26wSpMS0.glb
│   ├── Revolver-XrnLUz6kQj.glb
│   ├── Revolver.glb
│   ├── Scope.glb
│   ├── Shotgun Sawed Off.glb
│   ├── Shotgun Short Stock.glb
│   ├── Shotgun-ZmPTnh7njL.glb
│   ├── Shotgun.glb
│   ├── Sniper Rifle-ASOMZIErq3.glb
│   ├── Sniper Rifle-TKaBjAEofL.glb
│   ├── Sniper Rifle-i65hEldsw6.glb
│   ├── Sniper Rifle.glb
│   ├── Submachine Gun-nsP3JukU73.glb
│   ├── Submachine Gun.glb
│   └── Tripod.glb
├── Ultimate House Interior Pack-glb
│   ├── Bathroom Sink.glb
│   ├── Bathroom Toilet Paper.glb
│   ├── Bathtub.glb
│   ├── Bed King.glb
│   ├── Bed Single.glb
│   ├── Bunk Bed.glb
│   ├── Cactus.glb
│   ├── Ceiling Light.glb
│   ├── Chair-Rlyhe93NNe.glb
│   ├── Chair.glb
│   ├── Column Round.glb
│   ├── Couch Large.glb
│   ├── Couch Medium-mWgQ94zhDZ.glb
│   ├── Couch Medium.glb
│   ├── Couch Small-X9msj0gtb5.glb
│   ├── Couch Small.glb
│   ├── Curtains Double.glb
│   ├── Dead Houseplant.glb
│   ├── Door Double.glb
│   ├── Door-8it1hH1oRu.glb
│   ├── Door-KGt4ztcKrM.glb
│   ├── Door-LI93WgnjyS.glb
│   ├── Door-atrxVW0q9N.glb
│   ├── Door-b0AIfzp6VL.glb
│   ├── Door-ihXwSN12P1.glb
│   ├── Door-xuFNaNLzfE.glb
│   ├── Door.glb
│   ├── Drawer-8xZQEZL2w3.glb
│   ├── Drawer-G1H0wnCHQf.glb
│   ├── Drawer-N3ERi89OeO.glb
│   ├── Drawer-T4uDbyP90C.glb
│   ├── Drawer.glb
│   ├── Fireplace.glb
│   ├── Houseplant-IBLX2Jz90O.glb
│   ├── Houseplant-VtJh4Irl4w.glb
│   ├── Houseplant-bfLOqIV5uP.glb
│   ├── Houseplant-dveIJ0xNpX.glb
│   ├── Houseplant-f6GPjbEgg0.glb
│   ├── Houseplant.glb
│   ├── Kitchen Fridge.glb
│   ├── Kitchen Sink.glb
│   ├── L Couch.glb
│   ├── Lamp.glb
│   ├── Light Ceiling Single.glb
│   ├── Light Ceiling-NNlnaiDJIh.glb
│   ├── Light Ceiling-ToOLJDO5FI.glb
│   ├── Light Ceiling.glb
│   ├── Light Chandelier.glb
│   ├── Light Cube-gJpALEpLcy.glb
│   ├── Light Cube.glb
│   ├── Light Desk.glb
│   ├── Light Floor-eBQtooeh43.glb
│   ├── Light Floor.glb
│   ├── Light Icosahedron.glb
│   ├── Light Stand.glb
│   ├── Night Stand-08S1j15Jcx.glb
│   ├── Night Stand-7cobkfclNv.glb
│   ├── Night Stand.glb
│   ├── Oven.glb
│   ├── Round Rug.glb
│   ├── Rug.glb
│   ├── Shelf Large.glb
│   ├── Shelf Small-TfdgUV2RYe.glb
│   ├── Shelf Small.glb
│   ├── Square Plate.glb
│   ├── Stool.glb
│   ├── Table Lamp.glb
│   ├── Table Round Large.glb
│   ├── Table Round Small-57W671WvS2.glb
│   ├── Table Round Small.glb
│   ├── Toilet Paper stack.glb
│   ├── Toilet.glb
│   ├── Towel Rack.glb
│   ├── Trashcan Large.glb
│   ├── Trashcan Small-ZWYTK2SmBA.glb
│   ├── Trashcan Small.glb
│   ├── Trashcan-XSwahu252t.glb
│   ├── Trashcan.glb
│   ├── Washing Machine.glb
│   ├── Window Large.glb
│   ├── Window Round.glb
│   └── Window Small.glb
├── Ultimate Modular Men Pack-glb
│   ├── Adventurer.glb
│   ├── Astronaut.glb
│   ├── Beach Character.glb
│   ├── Business Man.glb
│   ├── Casual Character.glb
│   ├── Farmer.glb
│   ├── Hoodie Character.glb
│   ├── King.glb
│   ├── Punk.glb
│   ├── Swat.glb
│   └── Worker.glb
├── Ultimate Modular Women Pack-glb
│   ├── Adventurer.glb
│   ├── Animated Woman-nIItLV9nxS.glb
│   ├── Animated Woman.glb
│   ├── Medieval.glb
│   ├── Punk.glb
│   ├── Sci Fi Character.glb
│   ├── Soldier.glb
│   ├── Suit.glb
│   ├── Witch.glb
│   └── Worker.glb
├── Ultimate Space Kit-glb
│   ├── Astronaut-0D54W8yfrA.glb
│   ├── Astronaut-OgeSH89Nmx.glb
│   ├── Astronaut.glb
│   ├── Base Large.glb
│   ├── Building L.glb
│   ├── Bullets Pickup.glb
│   ├── Bush-RfUP3gXj69.glb
│   ├── Bush-tX1aT9IB1P.glb
│   ├── Bush.glb
│   ├── Connector.glb
│   ├── Enemy Flying.glb
│   ├── Enemy Large.glb
│   ├── Enemy Small.glb
│   ├── Geodesic Dome.glb
│   ├── Grass-Db4UVcNWnF.glb
│   ├── Grass-iw6l7gqcdQ.glb
│   ├── Grass.glb
│   ├── House Cylinder.glb
│   ├── House Long.glb
│   ├── House Open.glb
│   ├── House Pod.glb
│   ├── House Single Support.glb
│   ├── House Single.glb
│   ├── Mech-4UvIHxnoSR.glb
│   ├── Mech-D5wW2jDO42.glb
│   ├── Mech-o3Ps8z8ByP.glb
│   ├── Mech.glb
│   ├── Metal Support.glb
│   ├── Pickup Crate.glb
│   ├── Pickup Health.glb
│   ├── Pickup Jar.glb
│   ├── Pickup Key Card.glb
│   ├── Pickup Sphere.glb
│   ├── Pickup Thunder.glb
│   ├── Planet-18Uxrb2dIc.glb
│   ├── Planet-4NxxeyYMPJ.glb
│   ├── Planet-5zzi8WUMXj.glb
│   ├── Planet-9g1aIbfR9Y.glb
│   ├── Planet-B7xd3SZq0z.glb
│   ├── Planet-EC1Lk2IamI.glb
│   ├── Planet-IVnmauIgWX.glb
│   ├── Planet-hKZtOOMadH.glb
│   ├── Planet-pHZz4EMvVM.glb
│   ├── Planet-rYguWNNPvA.glb
│   ├── Planet.glb
│   ├── Plant-VwXvoIpCHP.glb
│   ├── Plant-s0joFFrQoy.glb
│   ├── Plant.glb
│   ├── Ramp.glb
│   ├── Rock Large-d2VWOdthtR.glb
│   ├── Rock Large-li0YBlBEMz.glb
│   ├── Rock Large.glb
│   ├── Rock-34W5ymEePk.glb
│   ├── Rock-R2UjZAX3By.glb
│   ├── Rock-b7gRkv0cEa.glb
│   ├── Rock.glb
│   ├── Roof Antenna.glb
│   ├── Roof Radar.glb
│   ├── Round Rover.glb
│   ├── Rover-WRd1piJOfh.glb
│   ├── Rover.glb
│   ├── Solar Panel Ground.glb
│   ├── Solar Panel Structure.glb
│   ├── Solar Panel.glb
│   ├── Spaceship-Jqfed124pQ.glb
│   ├── Spaceship-VSxUAFhzbA.glb
│   ├── Spaceship-u105mYHLHU.glb
│   ├── Spaceship.glb
│   ├── Stairs.glb
│   ├── Tree Blob-QHYRrAnKzW.glb
│   ├── Tree Blob-j0byyoIGOv.glb
│   ├── Tree Blob.glb
│   ├── Tree Floating-sdtjU7iczl.glb
│   ├── Tree Floating-tj2fePl8Eu.glb
│   ├── Tree Floating.glb
│   ├── Tree Lava-9gRfmVKx9W.glb
│   ├── Tree Lava-sTYjmQObr1.glb
│   ├── Tree Lava.glb
│   ├── Tree Light-om4BJAL82T.glb
│   ├── Tree Light.glb
│   ├── Tree Spikes-a6Vo1seJw9.glb
│   ├── Tree Spikes.glb
│   ├── Tree Spiral-gI3kqnqg80.glb
│   ├── Tree Spiral-kBomlgZ5xu.glb
│   ├── Tree Spiral.glb
│   ├── Tree Swirl-iLxXSXIx2t.glb
│   └── Tree Swirl.glb
├── Ultimate Stylized Nature Pack-glb
│   ├── Birch Trees.glb
│   ├── Bushes.glb
│   ├── Dead Trees-F5I0Q7TwO5.glb
│   ├── Dead Trees.glb
│   ├── Flower Bushes.glb
│   ├── Flowers.glb
│   ├── Grass.glb
│   ├── Maple Trees.glb
│   ├── Palm Trees.glb
│   ├── Pine Trees.glb
│   ├── Rocks.glb
│   └── Trees.glb
├── kenney_city-kit-commercial_2.1
│   ├── building-a.glb
│   ├── building-b.glb
│   ├── building-c.glb
│   ├── building-d.glb
│   ├── building-e.glb
│   ├── building-f.glb
│   ├── building-g.glb
│   ├── building-h.glb
│   ├── building-i.glb
│   ├── building-j.glb
│   ├── building-k.glb
│   ├── building-l.glb
│   ├── building-m.glb
│   ├── building-n.glb
│   ├── building-skyscraper-a.glb
│   ├── building-skyscraper-b.glb
│   ├── building-skyscraper-c.glb
│   ├── building-skyscraper-d.glb
│   ├── building-skyscraper-e.glb
│   ├── detail-awning-wide.glb
│   ├── detail-awning.glb
│   ├── detail-overhang-wide.glb
│   ├── detail-overhang.glb
│   ├── detail-parasol-a.glb
│   ├── detail-parasol-b.glb
│   ├── low-detail-building-a.glb
│   ├── low-detail-building-b.glb
│   ├── low-detail-building-c.glb
│   ├── low-detail-building-d.glb
│   ├── low-detail-building-e.glb
│   ├── low-detail-building-f.glb
│   ├── low-detail-building-g.glb
│   ├── low-detail-building-h.glb
│   ├── low-detail-building-i.glb
│   ├── low-detail-building-j.glb
│   ├── low-detail-building-k.glb
│   ├── low-detail-building-l.glb
│   ├── low-detail-building-m.glb
│   ├── low-detail-building-n.glb
│   ├── low-detail-building-wide-a.glb
│   └── low-detail-building-wide-b.glb
├── kenney_city-kit-suburban_20
│   ├── building-type-a.glb
│   ├── building-type-b.glb
│   ├── building-type-c.glb
│   ├── building-type-d.glb
│   ├── building-type-e.glb
│   ├── building-type-f.glb
│   ├── building-type-g.glb
│   ├── building-type-h.glb
│   ├── building-type-i.glb
│   ├── building-type-j.glb
│   ├── building-type-k.glb
│   ├── building-type-l.glb
│   ├── building-type-m.glb
│   ├── building-type-n.glb
│   ├── building-type-o.glb
│   ├── building-type-p.glb
│   ├── building-type-q.glb
│   ├── building-type-r.glb
│   ├── building-type-s.glb
│   ├── building-type-t.glb
│   ├── building-type-u.glb
│   ├── driveway-long.glb
│   ├── driveway-short.glb
│   ├── fence-1x2.glb
│   ├── fence-1x3.glb
│   ├── fence-1x4.glb
│   ├── fence-2x2.glb
│   ├── fence-2x3.glb
│   ├── fence-3x2.glb
│   ├── fence-3x3.glb
│   ├── fence-low.glb
│   ├── fence.glb
│   ├── path-long.glb
│   ├── path-short.glb
│   ├── path-stones-long.glb
│   ├── path-stones-messy.glb
│   ├── path-stones-short.glb
│   ├── planter.glb
│   ├── tree-large.glb
│   └── tree-small.glb
├── indoors
│   ├── Oven.glb
│   ├── Television.glb
│   ├── Wall Corner.glb
│   └── Wall.glb
├── locations
│   ├── Bar scene.glb
│   ├── Beach.glb
│   ├── Cozy Kitchen.glb
│   ├── Gas Station.glb
│   ├── Little Shop.glb
│   ├── Living Room.glb
│   ├── Ocean.glb
│   └── bedroom.glb
├── miscellaneous
│   ├── Animated Base Character.glb
│   ├── Boat.glb
│   └── Dragon.glb
├── office
│   ├── Cubicle.glb
│   ├── Desk.glb
│   ├── Message board.glb
│   ├── Office Phone.glb
│   └── Printer.glb
└── outdoors
    ├── Fountain.glb
    ├── Road.glb
    └── Statue.glb
```

## 📏 Asset Scaling Guidelines

### General Asset Packs

| Asset Pack                            | Recommended Scale |
| ------------------------------------- | ----------------- |
| Animated Animal Pack-glb              | 1x                |
| Animated Men Pack-glb                 | 1x                |
| Animated Women Pack-glb               | 1x                |
| Cars Bundle-glb                       | 5x                |
| Food Kit-glb                          | 1x                |
| Furniture Pack-glb                    | 2x                |
| Ultimate Modular Men Pack-glb         | 2.5x              |
| Ultimate Modular Women Pack-glb       | 2.5x              |
| Ultimate Guns Pack-glb                | 0.5x              |
| Ultimate House Interior Pack-glb      | 1.5x              |
| Ultimate Space Kit-glb                | 1x                |
| Survival Pack-glb                     | 0.7x              |
| Stylized Nature MegaKit.undefined-glb | 1x                |
| Ultimate Stylized Nature Pack-glb     | 2x                |
| Medieval Village Pack-glb             | 8x                |
| kenney_city-kit-suburban_20           | 25x               |
| kenney_city-kit-commercial_2.1        | 20x               |

### Specific Asset Scaling (locations folder)

| Asset File       | Recommended Scale |
| ---------------- | ----------------- |
| Beach.glb        | 0.2x              |
| Cozy Kitchen.glb | 7.5x              |
| Bar scene.glb    | 1x                |
| Little Shop.glb  | 12x               |
| Gas Station.glb  | 7x                |
| Living Room.glb  | 5x                |
| bedroom.glb      | 4x                |
| Ocean.glb        | 1x                |

**Note:** If a scene is in locations folder (like Beach, Bar scene, etc.), you don't need to assemble additional environment - these are complete scenes.

### Specific Asset Scaling (indoors folder)

| Asset File      | Recommended Scale |
| --------------- | ----------------- |
| Wall.glb        | 3x                |
| Wall Corner.glb | 3x                |
| Oven.glb        | 1x                |
| Television.glb  | 6x                |

### Specific Asset Scaling (outdoors folder)

| Asset File   | Recommended Scale |
| ------------ | ----------------- |
| Fountain.glb | 6x                |
| Statue.glb   | 4x                |
| Road.glb     | 0.5x              |

### Specific Asset Scaling (miscellaneous folder)

| Asset File | Recommended Scale |
| ---------- | ----------------- |
| Boat.glb   | 0.075x            |
| Other      | 1x                |

### Specific Asset Scaling (office folder)

| Asset File        | Recommended Scale |
| ----------------- | ----------------- |
| Message board.glb | 0.030x            |
| Office Phone.glb  | 0.2x              |
| Cubicle.glb       | 3x                |
| Printer.glb       | 1x                |
| Desk.glb          | 2x                |

**Note:** Office `Desk.glb` already includes a computer and chair built-in. Use `Furniture Pack-glb/Desk.glb` if you need a desk without a computer.

## 🎯 Asset Pack Priority Rules

### Office Scenes

**⚠️ IMPORTANT:** For office scenes, prioritize using props from the `office` folder:

- `office/Desk.glb` - Office-style desks with built-in computer and chair (scale 2x)
- `office/Cubicle.glb` - Cubicle walls and dividers (scale 3x)
- `office/Printer.glb` - Office printers (scale 1x)
- `office/Office Phone.glb` - Desk phones (scale 0.2x)
- `office/Message board.glb` - Wall-mounted message boards (scale 0.030x)

**Why?** The office pack contains modern, office-specific items that are more appropriate than generic furniture. Use Furniture Pack for supplementary items like chairs, bookcases, and sofas.

**Note:** Do NOT use standalone computer models - `office/Desk.glb` already includes a computer built into the desk.

### Kitchen/Restaurant Scenes

For kitchen or restaurant scenes, prioritize using items from the `Food Kit-glb` folder:

- 148+ food items, cooking tools, utensils, and dining props
- Perfect for food preparation, dining, and restaurant settings

### Space/Sci-Fi Scenes

For space or sci-fi scenes, use the `Ultimate Space Kit-glb` folder:

- 87+ space-themed assets including spaceships, planets, astronauts, mechs
- Alien environments with unique trees and vegetation

### Pre-built Complete Scenes

The `locations` folder contains complete pre-built scenes:

- Bar scene, Beach, Kitchen, Living Room, Shop, Gas Station, Ocean, bedroom
- Use these when you need a complete environment setup
- Scale: 0.2x (these are large complete scenes)

## 🔧 JSON Configuration Structure

The LLM in Phase 1 auto-generates this JSON. You can also edit it manually before Phase 2.

### Full Example

```json
{
  "scene": {
    "name": "INT. BAR - NIGHT",
    "duration_seconds": 15,
    "frame_rate": 24
  },
  "characters": [
    {
      "name": "DAVID",
      "asset_path": "assets/Animated Men Pack-glb/Man.glb",
      "armature_filter": "HumanArmature",
      "scale": [1, 1, 1],
      "start_position": [-1, 2.5, 0],
      "end_position":   [-1, 2.5, 0],
      "animation_sequence": [
        {
          "action_filter":   "Man_Idle",
          "lower_body_lock": "Man_Sitting",
          "start_second":    0,
          "end_second":      15,
          "start_rotation":  180,
          "end_rotation":    180,
          "interpolation":   "CONSTANT"
        }
      ]
    },
    {
      "name": "BARTENDER",
      "asset_path": "assets/Animated Men Pack-glb/Man in Long Sleeves.glb",
      "armature_filter": "HumanArmature",
      "scale": [1, 1, 1],
      "start_position": [-1, 4.5, 0],
      "end_position":   [-1, 4.5, 0],
      "animation_sequence": [
        {
          "action_filter": "Man_Idle",
          "start_second":  0,
          "end_second":    1,
          "start_rotation": 270,
          "end_rotation":   270,
          "interpolation": "CONSTANT"
        },
        {
          "action_filter": "Man_Walk",
          "start_second":  1,
          "end_second":    2.5,
          "start_rotation": 270,
          "end_rotation":   270,
          "interpolation": "LINEAR"
        },
        {
          "action_filter": "Man_Idle",
          "start_second":  2.5,
          "end_second":    15,
          "start_rotation": 270,
          "end_rotation":   270,
          "interpolation": "CONSTANT"
        }
      ]
    }
  ],
  "props": [
    {
      "name": "Pistol",
      "asset_path": "assets/Ultimate Guns Pack-glb/Pistol.glb",
      "attached_to": "AMANDA",
      "bone_name": "RightHand",
      "scale_meters": [0.2, 0.2, 0.2],
      "reveal_at_second": 14
    }
  ],
  "environment": {
    "location_glb": {
      "asset_path": "assets/locations/Bar scene.glb",
      "scale": [1, 1, 1],
      "position": [0, 0, 0]
    },
    "scattered_elements": []
  },
  "camera": {
    "position": [0, -6, 3],
    "rotation": [1.2, 0, 0],
    "lens_mm": 50
  },
  "lighting": [
    {
      "type": "POINT",
      "position": [0, 0, 5],
      "energy": 500
    }
  ]
}
```

### Key Field Reference

| Field | Description |
|-------|-------------|
| `animation_sequence` | Array of animation segments for a character (replaces single `animation` field) |
| `action_filter` | **Exact** animation name from the character's GLB (e.g. `Man_Idle`, `Female_Sitting`) |
| `lower_body_lock` | Freeze lower body on this animation while upper body plays `action_filter` (for seated+active poses) |
| `start_second` / `end_second` | When this segment begins/ends (seconds) |
| `start_rotation` / `end_rotation` | Z-axis rotation in degrees. 0=+Y, 90=−X, 180=−Y, 270=+X |
| `interpolation` | `CONSTANT` (snap), `LINEAR` (linear move), `BEZIER` (smooth curve) |
| `bone_name` | Bone to attach prop to (e.g. `RightHand`, `LeftHand`) |
| `scale_meters` | Prop size in world-space meters `[x, y, z]` |
| `reveal_at_second` | Prop is hidden until this time (e.g. gun reveal) |
| `location_glb` | Use a complete pre-built scene GLB instead of assembling from parts |

### ⚠️ Critical Rules

- **EXACT animation names** — never invent names. Use only names from the animation tables above.
- **Characters face −Y by default.** `start_rotation: 180` = faces camera (toward +Y). `0` = away from camera.
- When `lower_body_lock` is set, the named action drives legs/hips; `action_filter` drives spine and above.
- The `scale_meters` for props is the **desired world-space size in metres**, not a multiplier.
- `location_glb` scenes (Bar scene, Cozy Kitchen, etc.) already include floors — do NOT add a `base_surface` plane.

### Camera Shots JSON (Phase 2)

When using `--cameras-json`, the file format is:

```json
{
  "camera_shots": [
    {
      "name": "Shot_01_WA_Establish",
      "subject": ["DAVID", "AMANDA"],
      "shot_type": "WA",
      "composition": "CENTER",
      "angle": 270,
      "movement": "CRANE",
      "start_second": 0,
      "end_second": 2.5,
      "crane_start_z": 5.5,
      "crane_end_z": 2.8
    },
    {
      "name": "Shot_02_OTS",
      "subject": "AMANDA",
      "shot_type": "MCU",
      "composition": "RIGHT",
      "angle": 270,
      "movement": "STATIC",
      "start_second": 2.5,
      "end_second": 9
    },
    {
      "name": "Shot_03_TILT",
      "subject": "AMANDA",
      "shot_type": "ECU",
      "composition": "CENTER",
      "angle": 0,
      "movement": "TILT",
      "start_second": 13.5,
      "end_second": 15,
      "tilt_start_z": 0.5,
      "tilt_end_z": 2.8
    }
  ]
}
```

**Shot types**: `ECU`, `CU`, `MCU`, `MS`, `MLS`, `LS`, `WA`  
**Movements**: `STATIC`, `PUSH_IN`, `PUSH_OUT`, `TRUCK`, `PAN`, `TILT`, `CRANE`, `ORBIT`  
**Compositions**: `CENTER`, `LEFT`, `RIGHT`  
**Angle**: degrees around subject (0=front, 90=right, 180=back, 270=left)

## 🛠️ System Requirements

- **Blender 4.4+ or 5.x** installed at `/Applications/Blender.app/Contents/MacOS/Blender` (macOS) or `blender` on PATH
- **Python 3.9+**
- At least one LLM API key (see Prerequisites above)
- Python packages: `groq`, `anthropic`, `google-generativeai`, `openai`, `pypdf`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Supported LLM Backends

| Backend | Env Var | Default Model | Cost |
|---------|---------|---------------|------|
| Groq | `GROQ_API_KEY` | `openai/gpt-oss-120b` | Free tier available |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-4-5` | Paid |
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` | Free tier available |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` | Paid |

Auto-detection order when `--backend auto` (default): Groq → Anthropic → Gemini → OpenAI

Override model: `export GROQ_MODEL=openai/gpt-oss-20b` (or `ANTHROPIC_MODEL`, `GEMINI_MODEL`, `OPENAI_MODEL`).

**Groq free tier:** requests are capped at 8,000 tokens per minute, counting the prompt *plus*
the response budget, so the Phase 1 prompt is kept compact (~3.3k tokens) and gpt-oss models
run with `reasoning_effort=low` (override with `export GROQ_REASONING_EFFORT=medium`). At the
default effort gpt-oss can spend its whole output budget reasoning and return truncated JSON.
Run scripts one at a time; the client waits out rate limits automatically.

## 🔍 Troubleshooting

### LLM invents animation names

The post-processor auto-corrects common mistakes. If a hallucinated name slips through, edit the generated JSON manually before running Phase 2. Use only names from the animation tables in this README.

### Characters face the wrong direction

All characters face **−Y** by default. Use `start_rotation: 180` in the animation segment to make a character face the camera (+Y direction). Rotations are Z-axis degrees: 0=+Y, 90=−X, 180=−Y, 270=+X.

### Characters move backward

For walking characters, `end_position Y` must be **lower** than `start_position Y` for forward motion (characters face −Y).

### Gun/prop is too large or misaligned

Use `scale_meters` (world-space metres, not a multiplier). Set `bone_name` to the correct hand bone (typically `RightHand` or `LeftHand` depending on the rig). Leave `position_offset` at `[0,0,0]`.

### Lower body lock not working

Verify the `action_filter` and `lower_body_lock` names exactly match action names in the GLB. Use the exact names from the Animation Quick Reference table (including capitalisation).

### Phase 2 cameras aimed wrong

Phase 2 reads evaluated object positions **after NLA animation** using the depsgraph. Make sure you have manually repositioned characters in Blender and saved before running `--cameras-only`. The code reads the live `.blend`, not the JSON positions.

### Asset Not Found Errors

Verify asset paths match the exact file names in the `assets/` folder (case-sensitive on Linux/macOS).

### `assets/` folder not present

The assets folder is not tracked in git. You must obtain the GLB packs separately and place them in `assets/` following the folder structure in this README.

## 🎯 Best Practices

1. **Use `pipeline.py` as the single entry point** — it handles both phases and passes shared context.
2. **Edit the generated JSON before Phase 2** — fix timing, rotations, or animation names after Phase 1.
3. **Reposition characters in Blender after Phase 1** — Phase 2 reads the actual evaluated positions, so manual tweaks are preserved.
4. **Use pre-built `locations/` scenes for interiors** — they already include floors, walls, and lighting. Do not add a `base_surface` for these.
5. **Seated characters** need `lower_body_lock` to look natural. See the JSON example above.
6. **Use `reveal_at_second` for prop reveals** — keeps props hidden until the right dramatic moment.
7. **Run with Groq first** (free) — switch to Anthropic/Gemini if the scene timing or logic needs more coherent output.

## 📊 System Capabilities

✅ **Full screenplay → Blender pipeline** via single command  
✅ **Multi-segment character animation** with per-segment actions and rotations  
✅ **Lower-body lock** — seated lower half + active upper half simultaneously  
✅ **Prop attachment** to character hand bones with timeline reveal control  
✅ **Multi-camera Phase 2** with cinematic shot types, movements, and timeline markers  
✅ **LLM-planned camera cuts** (Groq / Anthropic / Gemini / OpenAI)  
✅ **Human-in-the-loop** — user reviews and adjusts between Phase 1 and Phase 2  
✅ **Multiple input formats** — inline text, .pdf, .txt, .fountain  
✅ **Pluggable LLM backends** — swap providers via CLI flag or env var  
✅ **`--regen` mode** — rebuild .blend from edited JSON without LLM re-call  
✅ **Environment generation** — complete pre-built scenes or procedurally assembled assets  

## 🚨 Known Limitations

- Limited to available GLB assets in the `assets/` folder
- Character interactions are purely animation-based (no physics, no IK solving at runtime)
- LLM may occasionally hallucinate asset names — post-processing auto-corrects common cases
- Camera movements are keyframe-based approximations, not true cinematography rig simulation
- No audio support
- No particle effects

---
