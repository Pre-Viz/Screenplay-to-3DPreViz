#!/usr/bin/env python3
"""
build_character_glb.py
======================
Merges all per-animation FBX files from the FreeAnimationPack into two
combined GLB files — one for male, one for female — each containing the
character mesh and ALL animations as separate named clips.

Usage:
    python3 build_character_glb.py

Outputs:
    assets/FreeAnimationPack/Male.glb
    assets/FreeAnimationPack/Female.glb
"""

import subprocess
import sys
import os
from pathlib import Path


BLENDER_SCRIPT = r'''
import bpy
import os
import re
import sys
from pathlib import Path

def log(msg):
    print(f"  {msg}", flush=True)

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for d in list(bpy.data.meshes):    bpy.data.meshes.remove(d)
    for d in list(bpy.data.armatures): bpy.data.armatures.remove(d)
    for d in list(bpy.data.actions):   bpy.data.actions.remove(d)
    for d in list(bpy.data.materials): bpy.data.materials.remove(d)

def import_fbx(path):
    before_objs    = set(bpy.data.objects)
    before_actions = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(path))
    new_objs    = [o for o in bpy.data.objects if o not in before_objs]
    new_actions = [a for a in bpy.data.actions if a not in before_actions]
    return new_objs, new_actions

def get_armature(objs):
    for o in objs:
        if o.type == 'ARMATURE':
            return o
    return None

def clean_name(filepath, prefix):
    """
    Turn  male_phoneTalking_180f.FBX  →  Male_PhoneTalking
          ani_dance_afro_56f.fbx      →  Male_DanceAfro
    Strips gender prefix, 'ani_' prefix, and trailing _NNNf frame count.
    """
    stem = Path(filepath).stem          # e.g. male_phoneTalking_180f
    stem = re.sub(r'^(male_|female_)', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'^ani_', '', stem, flags=re.IGNORECASE)
    stem = re.sub(r'_\d+f$', '', stem, flags=re.IGNORECASE)
    # PascalCase: capitalise first letter of each word, preserve inner caps
    parts = stem.split('_')
    stem = ''.join(p[0].upper() + p[1:] if p else '' for p in parts)
    return f"{prefix}_{stem}"

def push_to_nla(armature, action, action_name):
    """Push an action as a named NLA strip so the GLB exporter sees it."""
    if not armature.animation_data:
        armature.animation_data_create()
    # Rename action cleanly
    action.name = action_name
    action.use_fake_user = True
    track = armature.animation_data.nla_tracks.new()
    track.name = action_name
    fr = action.frame_range
    strip = track.strips.new(action_name, int(fr[0]), action)
    strip.name  = action_name
    strip.mute  = False
    return strip


def build_gender(fbx_dir, gender, output_path):
    """Build one combined GLB for a given gender."""
    prefix = gender.capitalize()   # "Male" or "Female"

    # Collect all FBX files for this gender (case-insensitive match)
    all_fbx = sorted([
        f for f in Path(fbx_dir).iterdir()
        if f.suffix.lower() == '.fbx'
        and f.stem.lower().startswith(gender.lower())
    ])

    # Also pick up gender-neutral animations (ani_*)
    shared_fbx = sorted([
        f for f in Path(fbx_dir).iterdir()
        if f.suffix.lower() == '.fbx'
        and f.stem.lower().startswith('ani_')
    ])

    all_fbx = all_fbx + shared_fbx

    if not all_fbx:
        print(f"❌ No FBX files found for gender '{gender}' in {fbx_dir}")
        return False

    print(f"\n{'='*60}")
    print(f"  Building {prefix}.glb  ({len(all_fbx)} animations)")
    print(f"{'='*60}")

    clear_scene()

    # ── Step 1: import first file as the base (gives us mesh + armature) ──
    base_file  = all_fbx[0]
    base_name  = clean_name(base_file, prefix)
    log(f"Base: {base_file.name}")
    base_objs, base_actions = import_fbx(base_file)
    base_arm = get_armature(base_objs)
    if not base_arm:
        print(f"❌ No armature in base file: {base_file}")
        return False

    base_arm.name = f"{prefix}_Armature"
    log(f"Armature: {base_arm.name}  ({len(base_arm.data.bones)} bones)")

    # Push the base file's action to NLA (keep only the one with most fcurves)
    if base_actions:
        best_base = max(base_actions, key=lambda a: len(a.fcurves))
        push_to_nla(base_arm, best_base, base_name)
        log(f"  ✅ {base_name}  ({int(best_base.frame_range[1])} frames)")
        for a in base_actions:
            if a != best_base:
                bpy.data.actions.remove(a)

    # Deselect everything so we can track new imports cleanly
    bpy.ops.object.select_all(action='DESELECT')

    # ── Step 2: import remaining files, steal action, delete duplicate mesh ──
    for fbx_file in all_fbx[1:]:
        anim_name = clean_name(fbx_file, prefix)
        log(f"→ {fbx_file.name}  →  {anim_name}")

        new_objs, new_actions = import_fbx(fbx_file)

        if not new_actions:
            log(f"  ⚠️  No new action found — skipping")
            for o in new_objs:
                bpy.data.objects.remove(o, do_unlink=True)
            continue

        # Keep only the action with the most fcurves (the armature one, not mesh shape)
        best = max(new_actions, key=lambda a: len(a.fcurves))
        push_to_nla(base_arm, best, anim_name)
        log(f"  ✅ {anim_name}  ({int(best.frame_range[1])} frames)")
        # Remove the other duplicate actions
        for action in new_actions:
            if action != best:
                bpy.data.actions.remove(action)

        # Remove the duplicate mesh/armature objects
        for o in new_objs:
            bpy.data.objects.remove(o, do_unlink=True)

        bpy.ops.object.select_all(action='DESELECT')

    # ── Step 3: clear active action (NLA drives everything) ──────────────────
    base_arm.animation_data.action = None

    # ── Step 4: select all objects and export ────────────────────────────────
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.data.objects:
        obj.select_set(True)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"\n  Exporting → {output_path}")
    bpy.ops.export_scene.gltf(
        filepath       = str(output_path),
        export_format  = 'GLB',
        use_selection  = True,
        export_animations     = True,
        export_nla_strips     = True,
        export_def_bones      = True,
        export_apply          = False,
        export_current_frame  = False,
    )

    # Summary
    action_names = sorted(set(
        t.strips[0].name
        for t in base_arm.animation_data.nla_tracks
        if t.strips
    ))
    print(f"\n  ✅ {len(action_names)} animations exported:")
    for n in action_names:
        print(f"     • {n}")

    return True


# ── Main ─────────────────────────────────────────────────────────────────────
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]

fbx_dir     = argv[0] if len(argv) > 0 else ""
male_out    = argv[1] if len(argv) > 1 else ""
female_out  = argv[2] if len(argv) > 2 else ""

if not fbx_dir:
    print("❌ No fbx_dir passed")
    sys.exit(1)

ok_m = build_gender(fbx_dir, "male",   male_out)
ok_f = build_gender(fbx_dir, "female", female_out)

if ok_m and ok_f:
    print("\n✅ Both GLBs built successfully.")
else:
    print("\n⚠️  One or more builds failed.")
    sys.exit(1)
'''


def main():
    base_dir   = Path(__file__).parent
    fbx_dir    = base_dir / "assets" / "FreeAnimationPack" / "fbx"
    male_out   = base_dir / "assets" / "FreeAnimationPack" / "Male.glb"
    female_out = base_dir / "assets" / "FreeAnimationPack" / "Female.glb"
    import sys as _sys
    blender = os.environ.get("BLENDER_PATH") or {
        "darwin":  "/Applications/Blender.app/Contents/MacOS/Blender",
        "linux":   "blender",
        "win32":   r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    }.get(_sys.platform, "blender")

    script_path = base_dir / "_build_character_glb_blender.py"
    script_path.write_text(BLENDER_SCRIPT)

    print("=" * 60)
    print("  build_character_glb.py")
    print("=" * 60)
    print(f"  FBX dir   : {fbx_dir}")
    print(f"  Male out  : {male_out}")
    print(f"  Female out: {female_out}")
    print()

    result = subprocess.run(
        [
            blender, "--background",
            "--python", str(script_path),
            "--",
            str(fbx_dir),
            str(male_out),
            str(female_out),
        ],
        text=True,
    )

    script_path.unlink(missing_ok=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
