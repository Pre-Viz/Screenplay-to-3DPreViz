#!/usr/bin/env python3
"""
Screenplay to Blender Scene — Fully Automated Pipeline
=======================================================

Reads a screenplay excerpt, uses an LLM (Groq gpt-oss-120b by default) to generate a complete
scene JSON, then runs flexible_scene_generator_optimized.py to build the Blender file.
No manual JSON writing needed.

Setup (one time):
    1. Get a free API key at https://console.groq.com  (no credit card needed)
    2. export GROQ_API_KEY=your_key_here   (or add to ~/.zshrc)

Usage:
    python3 screenplay_to_scene.py --file my_scene.txt
    python3 screenplay_to_scene.py --file my_scene.txt --output my_scene.blend
    python3 screenplay_to_scene.py --file my_scene.txt --json-only
    python3 screenplay_to_scene.py "INT. KITCHEN - DAY ..."
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

# --------------------------------------------------------------------------- #
# Asset + animation reference fed to the LLM with every request               #
# --------------------------------------------------------------------------- #

ASSET_REFERENCE = """
=== CHARACTERS (people: use Ultimate Modular by default) ===
Ultimate Modular packs have "Interact" (talking gesture) and "Wave", and can sit. Use the
Animated packs only for their unique clips (Clapping, Jump). Give each character a different model.

Ultimate Modular Women Pack-glb   armature_filter: CharacterArmature   scale: 2.5
  DEFAULT: Animated Woman.glb, Animated Woman-nIItLV9nxS.glb
  By context: Suit (office, business), Witch (witchcraft, magic), Soldier (military),
  Medieval (historical), Adventurer (explorer), Worker (construction), Punk (street),
  Sci Fi Character (sci-fi, space)
Ultimate Modular Men Pack-glb     armature_filter: CharacterArmature   scale: 2.5
  DEFAULT (in order): Casual Character.glb, Hoodie Character.glb, Beach Character.glb
  (Beach Character first for beach / summer scenes)
  By context: Business Man (office), Swat (police), Astronaut (space), King (royalty,
  fantasy), Farmer (farm), Worker (construction), Adventurer (explorer), Punk (street)
  Animations (both packs, EXACT names): Idle, Idle_Neutral, Walk, Run, Run_Back, Run_Left,
  Run_Right, Death, Roll, Punch_Left, Punch_Right, Kick_Left, Kick_Right, Sword_Slash,
  Idle_Sword, Gun_Shoot, Idle_Gun, Idle_Gun_Pointing, Idle_Gun_Shoot, Run_Shoot,
  HitRecieve, HitRecieve_2, Wave, Interact
  Idle = still/listening; Interact = talking; Wave = hello/goodbye/waving off;
  HitRecieve = flinch; Idle_Gun / Idle_Gun_Pointing / Gun_Shoot = hold / aim / fire.
  Grip bones: Wrist.R / Wrist.L

SITTING (any pack): keep the upper-body clip in action_filter and add
  "lower_body_lock": "Female_Sitting" (women) or "Man_Sitting" (men) on every seated segment.
  e.g. seated woman talking: action_filter "Interact", lower_body_lock "Female_Sitting".

TALKING: for each stretch of conversation give EVERY participant ONE "Interact" segment
  covering the whole stretch (same start/end seconds) and add "speaks_first": true to the
  first speaker's. The system splits these into alternating 0.75 s turns — do NOT write the
  turns yourself. A walk, turn or pause ends a stretch; start new Interact segments after it.
  Silent, sulking or turned-away characters use "Idle".

Animated Men Pack-glb (fallback)    armature_filter: HumanArmature   scale: 1
  Man.glb, Man in Suit.glb, Man in Long Sleeves.glb — Man_Idle, Man_Walk, Man_Run,
  Man_Death, Man_Punch, Man_Jump, Man_Clapping, Man_SwordSlash, (Man_Sitting: lock only).
Animated Women Pack-glb (fallback)  armature_filter: HumanArmature   scale: 1
  Woman.glb, Woman Casual.glb, Woman in Dress.glb, Woman in Tank Top.glb — Female_Idle,
  Female_Walk, Female_Run, Female_Death, Female_Punch, Female_Jump, Female_Clapping,
  Female_SwordSlash, (Female_Sitting: lock only). Grip bones: Palm.R / Palm.L. No Interact/Wave.
Animated Animal Pack-glb            armature_filter: AnimalArmature  scale: 1
  Wolf, Fox, Shiba Inu, Horse, Cow, Dog, Cat — Idle, Walk, Gallop, Death, Eating, Attack,
  Jump_ToIdle, Attack_Headbutt, Attack_Kick
⚠️  NEVER invent animation names. Use only the exact names above for that character's pack.

=== LOCATIONS (one pre-built environment; count 1, scale on all axes) ===
  assets/locations/Cozy Kitchen.glb 7.5 | Living Room.glb 5.0 | bedroom.glb 4.0 |
  Bar scene.glb 1.0 | Beach.glb 0.2 | Gas Station.glb 7.0 | Little Shop.glb 12.0 | Ocean.glb 1.0
  No match? Use props from: Ultimate House Interior Pack-glb (1.5), Stylized Nature
  MegaKit.undefined-glb (1), kenney_city-kit-commercial_2.1 (20), Medieval Village Pack-glb (8).

=== PROPS (only if a character explicitly holds something; otherwise omit "props") ===
  Scale = real size in metres. position_offset ALWAYS [0, 0, 0]. rotation_offset in radians
  (a forward-pointing gun: [1.5708, 0, 0]).
  Ultimate Guns Pack-glb: Pistol 0.20, Revolver 0.22, Assault Rifle 0.70, Sniper Rifle 0.90,
    Shotgun 0.75, Submachine Gun 0.45, Bullpup 0.55, Bayonet 0.30
  Survival Pack-glb: Axe 0.40, Knife 0.25, Pan 0.30, Phone 0.12, Backpack 0.40,
    First Aid Kit 0.20, Gas Can 0.25, Compass 0.08, Matchbox 0.06

=== SPACE, TIME & FACING RULES ===
- Characters face -Y by default. Rotations are Z offsets in radians: 0 = -Y, 3.14159 = +Y,
  1.5708 = turn left, -1.5708 = turn right. Walking forward = Y decreasing.
- Keep Z = 0 (floor). Standing still: start_position == end_position.
- Conversation distance 1.5–2.0 units; passing 1.0–1.5; never closer than 1.0. Separate on X by ≥ 1.
- Seconds, not frames; frame_rate 24; duration_seconds = latest end_second.
  Walk across a room 3–6 s; a turn 0.5–1 s; a wave 2–3 s.
- Reactions come AFTER their trigger (build one shared event timeline first; a walk ends at
  its end_second).
- A character who turns / looks at / becomes aware of someone MUST turn with three segments:
  hold old rotation (CONSTANT) → turn 0.5–1 s (BEZIER) → hold new rotation (CONSTANT).
  A character walking toward someone already faces them. Never change rotation silently.
- Segments are CONTIGUOUS from 0 to duration_seconds (no gaps / overlaps; fill with Idle),
  and each segment starts with the previous one's end_rotation.
"""

JSON_FORMAT = """
=== REQUIRED JSON FORMAT ===
{
  "scene": {"name": "INT. LOCATION - TIME", "duration_seconds": 12, "frame_rate": 24},
  "characters": [
    {
      "name": "CHARACTER_NAME",
      "asset_path": "assets/Ultimate Modular Men Pack-glb/Casual Character.glb",
      "armature_filter": "CharacterArmature",
      "scale": [2.5, 2.5, 2.5],
      "animation_sequence": [
        {"action_filter": "Walk", "start_second": 0, "end_second": 6,
         "start_position": [0, 8, 0], "end_position": [0, 3, 0],
         "start_rotation": [0, 0, 0], "end_rotation": [0, 0, 0], "interpolation": "LINEAR"},
        {"action_filter": "Interact", "speaks_first": true, "lower_body_lock": "Man_Sitting",
         "start_second": 6, "end_second": 12,
         "start_position": [0, 3, 0], "end_position": [0, 3, 0],
         "start_rotation": [0, 0, 0], "end_rotation": [0, 0, 0], "interpolation": "CONSTANT"}
      ]
    }
  ],
  "environment": {"scattered_elements": [
    {"name": "LocationScene", "asset_path": "assets/locations/Cozy Kitchen.glb",
     "scale": [7.5, 7.5, 7.5], "count": 1, "random_seed": 1,
     "scatter_area": {"x_range": [0, 0], "y_range": [0, 0], "z_position": 0}}]},
  "props": [
    {"name": "Pistol", "asset_path": "assets/Ultimate Guns Pack-glb/Pistol.glb",
     "scale": [0.20, 0.20, 0.20], "attach_to": "CHARACTER_NAME", "bone": "Wrist.R",
     "position_offset": [0, 0, 0], "rotation_offset": [1.5708, 0, 0]}],
  "camera": {"position": [7, 2, 3], "rotation": [1.2, 0, 1.4], "lens_mm": 35},
  "lighting": [{"type": "SUN", "position": [5, 5, 10], "energy": 3.0},
               {"type": "POINT", "position": [0, 3, 4], "energy": 800.0}]
}
RULES:
- No "base_surface" key (locations have floors). Omit "props" unless someone holds something.
- interpolation: LINEAR when moving, CONSTANT when still, BEZIER when turning.
- lower_body_lock only on seated segments; value "Man_Sitting" or "Female_Sitting".
- People default to Ultimate Modular ("CharacterArmature", scale 2.5).
- Dialogue: one Interact segment per participant per stretch of talk, first speaker marked
  "speaks_first": true.
- Camera rotation in radians (interior side angle ≈ [1.2, 0, 1.4]).
- Output ONLY raw valid JSON — no explanation, no markdown fences.
"""



class ScreenplayToScene:
    """screenplay text  →  LLM JSON generation  →  .blend file"""

    def __init__(self, backend: str = "auto", model: str = None):
        self.script_dir = Path(__file__).parent.absolute()
        sys.path.insert(0, str(self.script_dir))
        from llm_client import LLMClient
        self.llm = LLMClient(backend=backend, model=model)

    # ------------------------------------------------------------------ #
    # JSON extraction + validation                                         #
    # ------------------------------------------------------------------ #

    def _extract_json(self, text: str) -> dict | None:
        candidates = []

        # fenced code block first
        for m in re.finditer(r'```(?:json)?\s*([\s\S]*?)\s*```', text):
            candidates.append(m.group(1).strip())

        # bare JSON object
        for m in re.finditer(r'(\{[\s\S]*\})', text):
            candidates.append(m.group(1).strip())

        for c in candidates:
            try:
                data = json.loads(c)
                if self._validate(data):
                    return data
            except json.JSONDecodeError:
                continue
        return None

    def _validate(self, data: dict) -> bool:
        for key in ['scene', 'characters', 'environment', 'camera', 'lighting']:
            if key not in data:
                print(f"  ⚠️  Missing key: '{key}'")
                return False
        if not data['characters']:
            print("  ⚠️  No characters in JSON")
            return False
        for c in data['characters']:
            if 'animation_sequence' not in c:
                print(f"  ⚠️  '{c.get('name','?')}' missing animation_sequence")
                return False
        return True

    # ------------------------------------------------------------------ #
    # Prompt                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _direction_block(direction: str | None) -> str:
        if not direction or not direction.strip():
            return ""
        return f"""
=== DIRECTOR'S NOTES (FOLLOW THESE EXACTLY) ===

{direction.strip()}

These notes override the defaults above: use the characters, positions, beats and timings
they give (e.g. "A and B talk for 3 s, then A turns away for 2 s, then B walks past A").
Build the shared event timeline from these beats first, then fill in the dialogue turns.
"""

    def _build_prompt(self, screenplay: str, direction: str | None = None) -> str:
        return f"""You are a pre-visualization system that converts screenplay scenes into 3D Blender scene configurations.

{ASSET_REFERENCE}

{JSON_FORMAT}

=== SCREENPLAY ===

{screenplay}
{self._direction_block(direction)}
=== TASK ===

Analyze the screenplay and generate the complete JSON configuration.

Before writing JSON, reason through these steps in order:

STEP 1 — LOCATION & CHARACTERS
  - Pick the best pre-built environment.
  - Pick each character's GLB: Ultimate Modular by default — Animated Woman /
    Animated Woman-nIItLV9nxS for women; Casual, Hoodie, Beach Character for men —
    unless the context calls for a costume (Business Man for an office, Witch for
    witchcraft, Swat for police, ...). Give each character a different model.

STEP 2 — SHARED EVENT TIMELINE
  - List every event and the EXACT second it happens.
    e.g. "RAUL walk ends → second 4.0", "ADRIANA hears footsteps → second 4.0"
  - No character may react before the event that triggers them.
  - Derive all segment boundaries from this timeline.

STEP 3 — POSITIONS & DISTANCES
  - Place characters with realistic Y separation (1.5–2.0 units for conversation).
  - Separate on X by at least 1 unit.
  - Forward direction = decreasing Y (rot_z=0 faces -Y, rot_z=3.14159 faces +Y).
  - A character WALKING TOWARD another is already facing them — no extra turn needed.
  - A character DOING SOMETHING ELSE who then becomes aware of another person MUST turn.

STEP 4 — ROTATION AUDIT (do this before writing sequences)
  For EACH character, ask:
    a) What direction are they facing at the START? (default 0.0 = facing -Y)
    b) Does the screenplay say they turn, look at someone, or become aware of someone nearby?
    c) If yes: at what SECOND does the trigger happen?
    d) Insert a BEZIER turn segment (0.5–1s) at that second.
    e) After the turn, ALL subsequent segments hold the new rotation.
  Write out this audit in your reasoning before producing the JSON.

STEP 5 — ANIMATION SEQUENCES
  - Each character's segments must be CONTIGUOUS from second 0 to duration_seconds.
  - Fill all waiting time with Idle.
  - Rotation must be CONSISTENT: end_rotation of seg[i] = start_rotation of seg[i+1].
  - Only use EXACT animation names from the asset list above.
  - Dialogue: one "Interact" segment per participant spanning each stretch of talk, with
    "speaks_first": true on the first speaker's (the system splits it into turns).

STEP 6 — PROPS
  - Only include props if a character is explicitly holding something in the scene.
  - Use the correct grip bone for the character's pack (Palm.R or Wrist.R).
  - Omit the "props" key entirely if no props are needed.

STEP 7 — CAMERA
  - Position to frame the main action from a cinematic angle.

Output ONLY the raw JSON object. No explanation. No markdown. Nothing else.
"""

    # ------------------------------------------------------------------ #
    # Post-processing: fix known LLM mistakes before writing to disk      #
    # ------------------------------------------------------------------ #

    # Per-location floor Z offset: characters are placed at Z=0 by the LLM but each
    # pre-built GLB has its own internal floor height after scaling.
    # These values lower characters so they stand on the actual visible floor surface.
    # Key = substring of asset_path (lowercase), value = Z offset to ADD to all character positions.
    _LOCATION_FLOOR_Z = {
        "cozy kitchen":  -3.7,
        # Other locations default to 0.0 — user adjusts manually in Blender if needed.
    }

    # Animated-pack clip (without Man_/Female_) → Ultimate Modular clip, and back.
    _TO_MODULAR = {
        "Idle": "Idle", "Walk": "Walk", "Run": "Run", "Death": "Death",
        "Punch": "Punch_Right", "SwordSlash": "Sword_Slash", "Clapping": "Wave",
        "Wave": "Wave", "Talk": "Interact", "Talking": "Interact", "Jump": "Idle",
    }
    _TO_ANIMATED = {
        "Idle": "Idle", "Idle_Neutral": "Idle", "Walk": "Walk", "Run": "Run", "Death": "Death",
        "Punch_Left": "Punch", "Punch_Right": "Punch", "Sword_Slash": "SwordSlash",
        "Wave": "Clapping", "Interact": "Idle",
    }

    # Map of invented / incorrect animation names → correct names
    _ANIM_FIXUPS = {
        # Animated packs have no Wave — map to Clapping
        "Female_Wave":       "Female_Clapping",
        "Female_Greeting":   "Female_Clapping",
        "Female_Hello":      "Female_Clapping",
        "Female_Waving":     "Female_Clapping",
        "Man_Wave":          "Man_Clapping",
        "Man_Greeting":      "Man_Clapping",
        "Man_Hello":         "Man_Clapping",
        "Man_Waving":        "Man_Clapping",
        # Animated packs have no Hit/Shocked/Surprised/Draw
        "Female_Hit":        "Female_Idle",
        "Female_Shocked":    "Female_Idle",
        "Female_Surprised":  "Female_Idle",
        "Female_DrawGun":    "Female_Idle",
        "Female_AimGun":     "Female_Idle",
        "Female_Shoot":      "Female_Idle",
        "Man_Hit":           "Man_Idle",
        "Man_Shocked":       "Man_Idle",
        "Man_Surprised":     "Man_Idle",
        "Man_DrawGun":       "Man_Idle",
        "Man_AimGun":        "Man_Idle",
        "Man_Shoot":         "Man_Idle",
        # Animated packs have no Crouch/Duck/Dodge
        "Female_Crouch":     "Female_Idle",
        "Man_Crouch":        "Man_Idle",
        "Female_Dodge":      "Female_Run",
        "Man_Dodge":         "Man_Run",
        # Talking / gesturing — map to idle (no dedicated talk anim)
        "Female_Talk":       "Female_Idle",
        "Female_Talking":    "Female_Idle",
        "Female_Speak":      "Female_Idle",
        "Man_Talk":          "Man_Idle",
        "Man_Talking":       "Man_Idle",
        "Man_Speak":         "Man_Idle",
    }

    TALK_TURN_SECONDS = 0.75

    @classmethod
    def _split_dialogue_turns(cls, chars: list) -> None:
        """
        The LLM gives each participant one stationary "Interact" segment spanning a stretch
        of conversation. Split those into alternating turns on a shared grid: in each
        TALK_TURN_SECONDS slot one participant plays Interact and the others Idle, starting
        with the segment marked "speaks_first" (else the first character listed).
        A lone Interact segment (monologue) alternates Interact with short Idle beats.
        """
        T = cls.TALK_TURN_SECONDS
        spans = []   # (char_index, seg_index, start, end)
        for ci, char in enumerate(chars):
            for si, seg in enumerate(char.get("animation_sequence", [])):
                if (seg.get("action_filter") == "Interact"
                        and seg.get("start_position") == seg.get("end_position")
                        and seg.get("start_rotation") == seg.get("end_rotation")):
                    spans.append((ci, si, float(seg["start_second"]), float(seg["end_second"])))
        if not spans:
            return

        # group spans that overlap in time into conversations
        spans.sort(key=lambda s: s[2])
        groups, cur, cur_end = [], [], -1.0
        for sp in spans:
            if cur and sp[2] < cur_end - 1e-6:
                cur.append(sp); cur_end = max(cur_end, sp[3])
            else:
                if cur:
                    groups.append(cur)
                cur, cur_end = [sp], sp[3]
        groups.append(cur)

        replace = {}  # (ci, si) -> list of new segments
        for group in groups:
            t0 = min(s[2] for s in group)
            members = sorted({s[0] for s in group},
                             key=lambda ci: (not any(chars[s[0]]["animation_sequence"][s[1]].get("speaks_first")
                                                     for s in group if s[0] == ci), ci))
            for ci, si, a, b in group:
                seg = chars[ci]["animation_sequence"][si]
                pieces, t = [], a
                while t < b - 1e-6:
                    k = int((t - t0 + 1e-6) // T)
                    e = min(t0 + (k + 1) * T, b)
                    if len(members) == 1:          # monologue: talk, pause, talk, ...
                        talking = k % 3 != 2
                    else:
                        talking = members[k % len(members)] == ci
                    piece = dict(seg, start_second=round(t, 3), end_second=round(e, 3),
                                 action_filter="Interact" if talking else "Idle")
                    piece.pop("speaks_first", None)
                    pieces.append(piece)
                    t = e
                # merge consecutive pieces with the same action
                merged = []
                for p in pieces:
                    if merged and merged[-1]["action_filter"] == p["action_filter"]:
                        merged[-1]["end_second"] = p["end_second"]
                    else:
                        merged.append(p)
                replace[(ci, si)] = merged
            names = [chars[m]["name"] for m in members]
            print(f"  🔧 Dialogue turns: {' / '.join(names)} alternate every {T}s "
                  f"from {t0:.2f}s to {max(s[3] for s in group):.2f}s")

        for ci, char in enumerate(chars):
            seq = char.get("animation_sequence", [])
            new_seq = []
            for si, seg in enumerate(seq):
                new_seq.extend(replace.get((ci, si), [seg]))
            char["animation_sequence"] = new_seq

    def _postprocess(self, data: dict) -> dict:
        """Auto-correct common LLM errors in generated JSON."""
        chars = data.get("characters", [])

        # 0a. Remove base_surface — pre-built GLBs already have floors
        env = data.get("environment", {})
        if "base_surface" in env:
            del env["base_surface"]
            print("  🔧 Removed redundant base_surface (pre-built GLB has its own floor)")

        # 0b. Apply per-location floor Z offset so characters land on the actual floor
        floor_z = 0.0
        for element in env.get("scattered_elements", []):
            asset_lower = element.get("asset_path", "").lower()
            for key, offset in self._LOCATION_FLOOR_Z.items():
                if key in asset_lower:
                    floor_z = offset
                    print(f"  🔧 Applying floor Z offset {offset:+.1f}m for '{key}'")
                    break
            if floor_z != 0.0:
                break

        if floor_z != 0.0:
            for char in chars:
                for seg in char.get("animation_sequence", []):
                    for key in ["start_position", "end_position"]:
                        seg[key][2] += floor_z

        # 1. Fix invented animation names (Animated packs; Ultimate Modular is handled in 1b)
        for char in chars:
            if "Ultimate Modular" in char.get("asset_path", "") or char.get("armature_filter") == "CharacterArmature":
                continue
            for seg in char.get("animation_sequence", []):
                af = seg.get("action_filter", "")
                if af in self._ANIM_FIXUPS:
                    fixed = self._ANIM_FIXUPS[af]
                    print(f"  🔧 Auto-fixed animation: '{af}' → '{fixed}' ({char['name']})")
                    seg["action_filter"] = fixed

        # 1b. Make animation names match the character's pack (the two packs name clips
        #     differently; a wrong-pack name silently leaves the character frozen).
        for char in chars:
            modular = ("Ultimate Modular" in char.get("asset_path", "")
                       or char.get("armature_filter") == "CharacterArmature")
            if modular:
                char["armature_filter"] = "CharacterArmature"
                if char.get("scale") in (None, [1, 1, 1], [1.0, 1.0, 1.0]):
                    char["scale"] = [2.5, 2.5, 2.5]
                    print(f"  🔧 Set Ultimate Modular scale 2.5 ({char['name']})")
            female = "Wom" in char.get("asset_path", "")
            prefix = "Female_" if female else "Man_"
            for seg in char.get("animation_sequence", []):
                af = seg.get("action_filter", "")
                fixed = af
                if modular and af.startswith(("Man_", "Female_")):
                    base = af.split("_", 1)[1]
                    if base == "Sitting":
                        seg["lower_body_lock"] = af
                        fixed = "Idle"
                    else:
                        fixed = self._TO_MODULAR.get(base, "Idle")
                elif not modular and not af.startswith(("Man_", "Female_")):
                    fixed = prefix + self._TO_ANIMATED.get(af, "Idle")
                if fixed != af:
                    print(f"  🔧 Pack-matched animation: '{af}' → '{fixed}' ({char['name']})")
                    seg["action_filter"] = fixed
                lbl = seg.get("lower_body_lock")
                if lbl and lbl not in ("Man_Sitting", "Female_Sitting"):
                    seg["lower_body_lock"] = prefix + "Sitting"

        # 1c. Turn-taking dialogue: split overlapping "Interact" spans into alternating turns
        self._split_dialogue_turns(chars)

        # 2. Fix character X overlap (same X position)
        x_positions = {}
        for char in chars:
            seq = char.get("animation_sequence", [])
            if not seq:
                continue
            x = seq[0].get("start_position", [0, 0, 0])[0]
            while x in x_positions:
                x += 1.0
            if x != seq[0]["start_position"][0]:
                print(f"  🔧 Auto-fixed X overlap for '{char['name']}': offset to X={x}")
                for seg in seq:
                    seg["start_position"][0] = x
                    seg["end_position"][0]   = x
            x_positions[x] = char["name"]

        # 3. Inject missing BEZIER turn segments
        for char in chars:
            seq = char.get("animation_sequence", [])
            i = 0
            while i < len(seq) - 1:
                cur  = seq[i]
                nxt  = seq[i + 1]
                cur_rot = cur.get("end_rotation",   [0, 0, 0])
                nxt_rot = nxt.get("start_rotation", [0, 0, 0])
                # If Z rotation changes and the next segment is not already a BEZIER turn
                if abs(cur_rot[2] - nxt_rot[2]) > 0.01 and nxt.get("interpolation") != "BEZIER":
                    turn_dur  = 0.75  # seconds for the turn
                    turn_end  = nxt["start_second"]
                    turn_start = max(cur["start_second"], turn_end - turn_dur)
                    pos = nxt.get("start_position", [0, 0, 0])[:]
                    turn_seg = {
                        "action_filter":  cur.get("action_filter", "Female_Idle"),
                        "start_second":   turn_start,
                        "end_second":     turn_end,
                        "start_position": pos,
                        "end_position":   pos,
                        "start_rotation": [0, 0, cur_rot[2]],
                        "end_rotation":   [0, 0, nxt_rot[2]],
                        "interpolation":  "BEZIER",
                    }
                    # Shorten the preceding segment to end where the turn starts
                    cur["end_second"] = turn_start
                    cur["end_rotation"] = [0, 0, cur_rot[2]]
                    seq.insert(i + 1, turn_seg)
                    print(f"  🔧 Injected turn segment for '{char['name']}' "
                          f"({cur_rot[2]:.2f}→{nxt_rot[2]:.2f} rad) "
                          f"at {turn_start:.1f}–{turn_end:.1f}s")
                    i += 2  # skip over the newly inserted segment
                else:
                    i += 1

        # 4. Enforce default prop scales (bone-local space, not multiplicative)
        # Prop scale = desired world size in metres. These are defaults per prop name;
        # the generator divides by the armature's world scale automatically.
        _prop_default_scales = {
            "pistol":         0.20,
            "revolver":       0.22,
            "assault rifle":  0.70,
            "sniper rifle":   0.90,
            "shotgun":        0.75,
            "submachine gun": 0.45,
            "bullpup":        0.55,
            "bayonet":        0.30,
            "axe":            0.40,
            "knife":          0.25,
            "pan":            0.30,
            "phone":          0.12,
            "backpack":       0.40,
            "first aid kit":  0.20,
            "gas can":        0.25,
            "compass":        0.08,
            "matchbox":       0.06,
        }
        for prop in data.get("props", []):
            prop_name_lower = prop.get("name", "").lower()
            current = prop.get("scale", [1, 1, 1])
            # Apply default scale if still at generic [1,1,1]
            if current == [1, 1, 1]:
                for key, default_m in _prop_default_scales.items():
                    if key in prop_name_lower:
                        prop["scale"] = [default_m, default_m, default_m]
                        print(f"  🔧 Set prop scale to {default_m}m for '{prop.get('name')}'")
                        break
            # Always force position_offset to [0,0,0] — any non-zero value in
            # bone-local space gets amplified by the armature's ~100x scale
            if prop.get("position_offset", [0, 0, 0]) != [0, 0, 0]:
                print(f"  🔧 Forced position_offset to [0,0,0] for '{prop.get('name')}'")
                prop["position_offset"] = [0, 0, 0]

        # 5. Validate prop bone names match the pack used by that character

        _pack_bones = {
            "animated men pack":    {"right": "Palm.R",  "left": "Palm.L"},
            "animated women pack":  {"right": "Palm.R",  "left": "Palm.L"},
            "ultimate modular men": {"right": "Wrist.R", "left": "Wrist.L"},
            "ultimate modular women":{"right": "Wrist.R","left": "Wrist.L"},
        }
        char_pack_map = {}
        for char in chars:
            ap = char.get("asset_path", "").lower()
            for pack_key in _pack_bones:
                if pack_key in ap:
                    char_pack_map[char["name"]] = pack_key
                    break

        for prop in data.get("props", []):
            attach_to = prop.get("attach_to", "")
            bone      = prop.get("bone", "")
            pack      = char_pack_map.get(attach_to)
            if pack:
                valid_bones = list(_pack_bones[pack].values())
                if bone not in valid_bones:
                    # Pick the correct right-hand bone from the actual pack
                    correct = _pack_bones[pack]["right"]
                    print(f"  🔧 Fixed prop bone '{bone}' → '{correct}' "
                          f"(correct for {pack})")
                    prop["bone"] = correct

        # 7. Enforce minimum Y distance between stationary characters (1.5 units)
        # Find final resting Y positions for all chars
        resting = {}
        for char in chars:
            seq = char.get("animation_sequence", [])
            if seq:
                last = seq[-1]
                resting[char["name"]] = last.get("end_position", [0, 0, 0])[1]

        names = list(resting.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                yi = resting[names[i]]
                yj = resting[names[j]]
                if abs(yi - yj) < 1.5:
                    # Push apart to 1.5 units
                    mid = (yi + yj) / 2
                    new_yi = mid - 0.75
                    new_yj = mid + 0.75
                    diff_i = new_yi - yi
                    diff_j = new_yj - yj
                    print(f"  🔧 Enforced Y distance: '{names[i]}' shifted by {diff_i:+.2f}, "
                          f"'{names[j]}' shifted by {diff_j:+.2f}")
                    for char in chars:
                        if char["name"] == names[i]:
                            for seg in char.get("animation_sequence", []):
                                for key in ["start_position", "end_position"]:
                                    seg[key][1] += diff_i
                        if char["name"] == names[j]:
                            for seg in char.get("animation_sequence", []):
                                for key in ["start_position", "end_position"]:
                                    seg[key][1] += diff_j

        # 8. Facing check: if two characters end up interacting close together,
        #    make sure they are facing each other rather than both facing the same way.
        #    "Interacting" = final action is NOT Walk/Run (they've stopped and are doing something).
        import math
        _WALK_ANIMS = {"Female_Walk", "Man_Walk", "Female_Run", "Man_Run"}
        interactive_chars = []
        for char in chars:
            seq = char.get("animation_sequence", [])
            if not seq:
                continue
            last_anim = seq[-1].get("action_filter", "")
            if last_anim not in _WALK_ANIMS:
                last_y = seq[-1].get("end_position", [0, 0, 0])[1]
                last_rot = seq[-1].get("end_rotation", [0, 0, 0])[2]
                interactive_chars.append({"char": char, "y": last_y, "rot_z": last_rot})

        if len(interactive_chars) == 2:
            a, b = interactive_chars[0], interactive_chars[1]
            # Expected: character at lower Y should face +Y (π), higher Y should face -Y (0)
            lower, higher = (a, b) if a["y"] < b["y"] else (b, a)
            expected_lower  = math.pi   # face +Y (toward higher)
            expected_higher = 0.0       # face -Y (toward lower)

            def _needs_face_fix(actual_rot, expected_rot, tol=0.3):
                return abs(actual_rot - expected_rot) > tol

            def _inject_face_turn(char_entry, from_rot, to_rot):
                seq = char_entry["char"].get("animation_sequence", [])
                if not seq:
                    return
                # Find the first non-Walk segment from the end
                for i in range(len(seq) - 1, -1, -1):
                    seg = seq[i]
                    if seg.get("action_filter", "") not in _WALK_ANIMS:
                        # Insert a BEZIER turn at the start of this segment
                        turn_dur   = 0.75
                        turn_start = seg["start_second"]
                        turn_end   = min(turn_start + turn_dur, seg["end_second"])
                        pos = seg.get("start_position", [0, 0, 0])[:]

                        turn_seg = {
                            "action_filter":  seg.get("action_filter", "Female_Idle"),
                            "start_second":   turn_start,
                            "end_second":     turn_end,
                            "start_position": pos,
                            "end_position":   pos,
                            "start_rotation": [0, 0, from_rot],
                            "end_rotation":   [0, 0, to_rot],
                            "interpolation":  "BEZIER",
                        }
                        # Shift the existing segment to start after the turn
                        seg["start_second"] = turn_end
                        seg["start_rotation"] = [0, 0, to_rot]
                        # Also patch end_rotation on the segment right after the turn
                        # so it stays consistent (start=to_rot, end=to_rot)
                        if seg.get("end_rotation", [0, 0, 0])[2] != to_rot:
                            seg["end_rotation"] = [0, 0, to_rot]
                        seq.insert(i, turn_seg)
                        # Propagate the new rotation to ALL later segments
                        for k in range(i + 2, len(seq)):
                            seq[k]["start_rotation"] = [0, 0, to_rot]
                            seq[k]["end_rotation"]   = [0, 0, to_rot]
                        print(f"  🔧 Facing fix: '{char_entry['char']['name']}' "
                              f"turn {from_rot:.2f}→{to_rot:.2f} rad at {turn_start:.1f}s "
                              f"(faces other character)")
                        return

            if _needs_face_fix(lower["rot_z"], expected_lower):
                _inject_face_turn(lower, lower["rot_z"], expected_lower)
            if _needs_face_fix(higher["rot_z"], expected_higher):
                _inject_face_turn(higher, higher["rot_z"], expected_higher)

        return data

    # ------------------------------------------------------------------ #
    # Pipeline                                                             #
    # ------------------------------------------------------------------ #

    def generate_json(self, screenplay: str, direction: str | None = None) -> dict | None:
        print("\n📜 Sending screenplay to the LLM..." + (" (with director's notes)" if direction else ""))

        for attempt in range(1, 4):
            try:
                print(f"  🤖 Attempt {attempt}/3")
                raw  = self.llm.call(self._build_prompt(screenplay, direction))
                data = self._extract_json(raw)
                if data:
                    print("  ✅ Valid JSON received")
                    return data
                print("  ⚠️  Could not parse JSON from response — retrying...")
            except Exception as e:
                print(f"  ⚠️  {e}")

        print("\n❌ Failed after 3 attempts.")
        return None

    def run(
        self,
        screenplay:   str,
        output_blend: str  = None,
        json_path:    str  = None,
        json_only:    bool = False,
    ) -> bool:

        # Step 1 — generate JSON
        data = self.generate_json(screenplay)
        if not data:
            return False

        # Step 1b — auto-fix common LLM mistakes
        data = self._postprocess(data)

        # Step 2 — save JSON
        if json_path is None:
            safe = re.sub(r'[^a-zA-Z0-9_]', '_', data['scene']['name']).lower().strip('_')
            json_path = str(self.script_dir / f"{safe}.json")

        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 JSON saved: {json_path}")

        if json_only:
            print("   (--json-only: stopping here)")
            return True

        # Step 3 — generate .blend
        print("\n🎬 Generating Blender scene...")
        sys.path.insert(0, str(self.script_dir))
        from flexible_scene_generator_optimized import OptimizedSceneGenerator

        if output_blend is None:
            output_blend = json_path.replace('.json', '.blend')

        ok = OptimizedSceneGenerator(json_path).generate_scene(output_blend, render_video=False)
        print(f"\n{'✅ Done:' if ok else '❌ Failed.'} {output_blend if ok else json_path}")
        return ok


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Screenplay → Blender scene, fully automated via LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 screenplay_to_scene.py --file my_scene.txt
  python3 screenplay_to_scene.py --file my_scene.txt --output scene.blend
  python3 screenplay_to_scene.py --file my_scene.txt --json-only
  python3 screenplay_to_scene.py "INT. KITCHEN - DAY\\nRICK walks in."
        """,
    )
    parser.add_argument('screenplay',  nargs='?',            help='Screenplay as inline text')
    parser.add_argument('--file',  '-f',                     help='Path to screenplay .txt file')
    parser.add_argument('--output', '-o',                    help='Output .blend path')
    parser.add_argument('--json-out', '-j',                  help='Output JSON path')
    parser.add_argument('--json-only', action='store_true',  help='Stop after saving JSON')
    parser.add_argument('--backend', default='auto',          help='LLM backend: groq | anthropic | gemini | openai (default: auto)')
    parser.add_argument('--model',   default=None,            help='Override model name for chosen backend')
    args = parser.parse_args()

    if args.file:
        try:
            screenplay = Path(args.file).read_text()
        except FileNotFoundError:
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
    elif args.screenplay:
        screenplay = args.screenplay
    else:
        print("📝 Paste screenplay (Ctrl+D when done):")
        try:
            screenplay = sys.stdin.read()
        except KeyboardInterrupt:
            print("\n👋 Cancelled.")
            sys.exit(0)

    if not screenplay.strip():
        print("❌ No screenplay text provided.")
        sys.exit(1)

    print("=" * 60)
    print("🎬  SCREENPLAY → BLENDER  (Groq)")
    print("=" * 60)
    print(f"Input  : {len(screenplay)} characters")
    print()

    ok = ScreenplayToScene(backend=args.backend, model=args.model).run(
        screenplay,
        output_blend=args.output,
        json_path=args.json_out,
        json_only=args.json_only,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
