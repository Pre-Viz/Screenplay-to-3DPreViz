#!/usr/bin/env python3
"""
🎬 Optimized Flexible Scene Generator

Fully JSON-driven scene generator with no hardcoded elements.
Efficient, modular, and configurable for any scene type.
"""

import subprocess
import sys
import os
import json
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Frames the Animated-pack *_Sitting clips take to go from standing to seated.
SIT_SETTLE_FRAMES = 11

# Frames to cross-fade between consecutive animation segments of a character.
NLA_BLEND_FRAMES = 4


class OptimizedSceneGenerator:
    """Efficient JSON-driven Blender scene generator"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self.asset_base_path = self._get_asset_base_path()
        self.blender_path = self._get_blender_path()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate JSON configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required sections
            required_sections = ['scene', 'characters', 'environment', 'camera', 'lighting']
            for section in required_sections:
                if section not in config:
                    raise ValueError(f"Missing required section: {section}")
            
            return config
        except Exception as e:
            raise ValueError(f"Invalid configuration file: {e}")
    
    def _get_asset_base_path(self) -> str:
        """Get asset base path from config or auto-detect"""
        # Check config first
        if 'settings' in self.config and 'asset_base_path' in self.config['settings']:
            return self.config['settings']['asset_base_path']
        
        # Auto-detect from config file location; JSONs saved in output/ (or elsewhere) fall
        # back to the repo's own assets/ folder next to this script.
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        if os.path.isdir(os.path.join(config_dir, "assets")):
            return config_dir
        return os.path.dirname(os.path.abspath(__file__))
    
    def _get_blender_path(self) -> str:
        """Get Blender executable path"""
        # Check config first
        if 'settings' in self.config and 'blender_path' in self.config['settings']:
            return self.config['settings']['blender_path']
        
        # Default paths by platform
        default_paths = {
            'darwin': '/Applications/Blender.app/Contents/MacOS/Blender',
            'linux': 'blender',
            'win32': 'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe'
        }
        
        return default_paths.get(sys.platform, 'blender')
    
    def _sanitize_name(self, name: str) -> str:
        """Convert name to valid Python identifier"""
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        if sanitized and sanitized[0].isdigit():
            sanitized = f"obj_{sanitized}"
        return sanitized or "unnamed_object"
    
    def _generate_header(self) -> str:
        """Generate script header and imports"""
        return f'''
import bpy
import os
import random
import math
import bmesh
import mathutils

# Clear existing scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ── Lower-body-lock helper ───────────────────────────────────────────────────
# Keywords that identify the SPINE chain (upper body side of the split).
# Any bone whose name contains one of these is upper-body, along with all its
# descendants.  Everything else (hips, legs, feet, …) is lower-body.
_UPPER_CHAIN_KW = {{
    "spine", "chest", "breast", "neck", "head",
    "torso", "abdomen",
    "shoulder", "clavicle", "collar",
    "upperarm", "upper_arm", "arm",
    "forearm", "fore_arm", "elbow",
    "hand", "wrist", "palm",
    "finger", "thumb", "index", "middle", "ring", "pinky",
}}

def _classify_bones_by_hierarchy(armature):
    """
    Walk the armature's bone tree and return (upper_set, lower_set).

    Strategy:
      1. Find every bone that looks like a 'spine' / 'chest' anchor
         (name contains a keyword from _UPPER_CHAIN_KW).
      2. Those bones + all their recursive children → upper body.
      3. Every remaining bone → lower body.

    This works regardless of the pack's exact naming convention because we
    search by substring, not exact name.
    """
    bones = armature.data.bones
    upper = set()
    lower = set()

    for bone in bones:
        name_lc = bone.name.lower()
        # Strip namespace prefixes like "mixamorig:" before matching
        name_lc = name_lc.split(":")[-1]
        if any(kw in name_lc for kw in _UPPER_CHAIN_KW):
            upper.add(bone.name)
            for child in bone.children_recursive:
                upper.add(child.name)

    for bone in bones:
        if bone.name not in upper:
            lower.add(bone.name)

    return upper, lower


def _fcurve_bone_name(data_path: str):
    """Extract the bone name from a pose FCurve data_path, or None."""
    if 'pose.bones' not in data_path:
        return None
    try:
        return data_path.split('["')[1].split('"]')[0]
    except IndexError:
        return None


def _action_fcurves(action):
    """All FCurves of an action — Blender 4.x (legacy) and 5.x (slotted actions)."""
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    return [fc for layer in action.layers for strip in layer.strips
            for bag in strip.channelbags for fc in bag.fcurves]


def _build_blended_action(armature, upper_action, lower_action, blended_name: str,
                          lower_loc_scale: float = 1.0):
    """
    Create (or reuse) a merged action:
      - upper body FCurves come from upper_action (cycled, so a short gesture
        loops for the whole segment)
      - lower body FCurves come from lower_action; its location keys are
        multiplied by lower_loc_scale when it was authored on a different rig
    The split is determined by the armature's own bone hierarchy so it works
    with any bone-naming convention.
    """
    existing = bpy.data.actions.get(blended_name)
    if existing:
        return existing

    upper_bones, lower_bones = _classify_bones_by_hierarchy(armature)
    print(f"  🦴 Bone split — upper: {{len(upper_bones)}}, lower: {{len(lower_bones)}}")

    blended = bpy.data.actions.new(name=blended_name)
    blended.use_fake_user = True

    added = set()
    _bag = []  # Blender 5.x channelbag, created on first FCurve

    def _new_fc(data_path, index, group):
        if hasattr(blended, "fcurves"):  # Blender < 5.0
            return blended.fcurves.new(data_path=data_path, index=index, action_group=group)
        # Blender 5.x: fcurve_ensure_for_datablock() refuses unless the action is
        # already assigned to the armature, so build slot/layer/channelbag directly.
        if not _bag:
            slot  = blended.slots.new(id_type='OBJECT', name=armature.name)
            strip = blended.layers.new("Layer").strips.new(type='KEYFRAME')
            _bag.append(strip.channelbag(slot, ensure=True))
        bag = _bag[0]
        fc = bag.fcurves.new(data_path, index=index)
        if group:
            fc.group = bag.groups.get(group) or bag.groups.new(group)
        return fc

    def _copy_fc(src_action, want_lower: bool):
        for fc in _action_fcurves(src_action):
            bone = _fcurve_bone_name(fc.data_path)
            if bone is None:
                # Non-bone channel (root transform etc.) — copy from lower_action
                if not want_lower:
                    continue
            else:
                in_lower = bone in lower_bones
                if want_lower != in_lower:
                    continue
            grp_name = fc.group.name if fc.group else ""
            key = (fc.data_path, fc.array_index)
            if key in added:
                continue  # already added by the other pass — skip
            try:
                new_fc = _new_fc(fc.data_path, fc.array_index, grp_name)
            except RuntimeError as e:
                print(f"  ⚠️  {{blended_name}}: could not copy {{fc.data_path}}[{{fc.array_index}}]: {{e}}")
                continue
            added.add(key)
            k = lower_loc_scale if (want_lower and fc.data_path.endswith(".location")) else 1.0
            for kp in fc.keyframe_points:
                new_kp = new_fc.keyframe_points.insert(kp.co[0], kp.co[1] * k, options={{'FAST'}})
                new_kp.interpolation = kp.interpolation
            if not want_lower:
                new_fc.modifiers.new(type='CYCLES')
            new_fc.update()

    _copy_fc(lower_action, want_lower=True)   # lower body from lower_action (sitting)
    _copy_fc(upper_action, want_lower=False)  # upper body from upper_action (idle/punch)
    return blended


# Packs whose actions a lower_body_lock can borrow when no character in the
# scene carries them (e.g. an Ultimate Modular character sitting via Man_Sitting).
_DONOR_GLB = {{
    "Man_":    "assets/Animated Men Pack-glb/Man.glb",
    "Female_": "assets/Animated Women Pack-glb/Woman.glb",
}}


def _hips_len(armature_data):
    """Rest-pose hip height in the rig's own units (None if the rig has no hips)."""
    bone = armature_data.bones.get("Hips") or next(
        (b for b in armature_data.bones if "hip" in b.name.lower()), None)
    return bone.head_local.length if bone else None


def _resolve_lower_action(name):
    """
    Find a lower_body_lock action by name, importing it from its Animated-pack
    GLB if no character in the scene carries it.
    Returns (action, rest hip height of the rig it was authored on, or None).
    """
    for act in bpy.data.actions:
        if act.name.split("|")[-1].split(".")[0] != name:
            continue
        for o in bpy.data.objects:
            if o.type == "ARMATURE" and o.animation_data and any(
                    s.action == act for t in o.animation_data.nla_tracks for s in t.strips):
                return act, _hips_len(o.data)
        return act, act.get("rig_hips_len")

    prefix = next((p for p in _DONOR_GLB if name.startswith(p)), None)
    path = os.path.join(asset_base_path, _DONOR_GLB[prefix]) if prefix else None
    if not path or not os.path.exists(path):
        return None, None
    before_objs, before_acts = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new_objs = [o for o in bpy.data.objects if o not in before_objs]
    donor = next((o for o in new_objs if o.type == "ARMATURE"), None)
    hips = _hips_len(donor.data) if donor else None
    found = None
    for act in [a for a in bpy.data.actions if a not in before_acts]:
        if found is None and act.name.split("|")[-1].split(".")[0] == name:
            found = act
        else:
            bpy.data.actions.remove(act)
    for o in new_objs:
        bpy.data.objects.remove(o, do_unlink=True)
    if found:
        found.use_fake_user = True
        if hips:
            found["rig_hips_len"] = hips
        print(f"  📥 Borrowed {{name}} from {{_DONOR_GLB[prefix]}}")
    return found, hips
# ────────────────────────────────────────────────────────────────────────────

# Scene configuration
scene_name = "{self.config['scene']['name']}"
duration_seconds = {self.config['scene']['duration_seconds']}
frame_rate = {self.config['scene']['frame_rate']}
render_video = False  # Will be set by command line args

print("🎬 Optimized Scene Generator")
print("=" * 50)
print(f"Scene: {{scene_name}}")
print(f"Duration: {{duration_seconds}} seconds")
print(f"Frame Rate: {{frame_rate}} fps")
print(f"Render Video: {{render_video}}")

# Set scene properties
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = int(round(duration_seconds * frame_rate))
scene.frame_set(1)

# Asset base path
asset_base_path = "{self.asset_base_path}"
character_armatures = {{}}

'''
    
    def _generate_character_code(self, character: Dict[str, Any]) -> str:
        """Generate code for a character — routes to single-action or multi-action path."""
        if 'animation_sequence' in character:
            return self._generate_character_multi_action_code(character)
        return self._generate_character_single_action_code(character)

    def _generate_character_single_action_code(self, character: Dict[str, Any]) -> str:
        """Single action that loops for the full scene duration (original behaviour)."""
        char_name = character['name']
        sanitized_name = self._sanitize_name(char_name)
        asset_path = character['asset_path']
        armature_filter = character.get('armature_filter', 'Armature')
        scale = character.get('scale', [1, 1, 1])
        start_pos = character.get('start_position', [0, 0, 0])
        end_pos = character.get('end_position', [0, 0, 0])
        animation = character.get('animation', {})
        action_filter = animation.get('action_filter', 'Idle')
        interpolation = animation.get('interpolation', 'LINEAR')

        return f'''
# Character: {char_name}  [single action]
print("👤 Importing {char_name}...")
{sanitized_name}_armature = None
asset_path = os.path.join(asset_base_path, "{asset_path}")

if os.path.exists(asset_path):
    bpy.ops.import_scene.gltf(filepath=asset_path)
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE' and '{armature_filter}' in obj.name:
            {sanitized_name}_armature = obj
            break

    if {sanitized_name}_armature:
        _imported_scale = {sanitized_name}_armature.scale.copy()
        {sanitized_name}_armature.scale = (
            _imported_scale[0] * {scale[0]},
            _imported_scale[1] * {scale[1]},
            _imported_scale[2] * {scale[2]}
        )
        {sanitized_name}_armature.name = "{char_name}"
        character_armatures["{char_name}"] = {sanitized_name}_armature

        char_action = None
        for action in bpy.data.actions:
            if '{action_filter}' in action.name:
                char_action = action
                break

        if char_action:
            if not {sanitized_name}_armature.animation_data:
                {sanitized_name}_armature.animation_data_create()
            {sanitized_name}_armature.animation_data.action = char_action

            {sanitized_name}_armature.location = {start_pos}
            {sanitized_name}_armature.keyframe_insert(data_path="location", frame=1)
            {sanitized_name}_armature.location = {end_pos}
            {sanitized_name}_armature.keyframe_insert(data_path="location", frame=scene.frame_end)

            for fcurve in _action_fcurves(char_action):
                if fcurve.data_path == "location":
                    for kp in fcurve.keyframe_points:
                        kp.interpolation = '{interpolation}'

            action_length = char_action.frame_range[1] - char_action.frame_range[0]
            looped_curves = 0
            for fcurve in _action_fcurves(char_action):
                if fcurve.data_path.startswith('pose.bones'):
                    if not fcurve.modifiers:
                        mod = fcurve.modifiers.new(type='CYCLES')
                        mod.mode_before = 'REPEAT'
                        mod.mode_after  = 'REPEAT'
                    looped_curves += 1

            print(f"✅ {char_name}: '{action_filter}' ({{action_length:.0f}} frames) looped over {{scene.frame_end}} frames ({{looped_curves}} bone curves)")
        else:
            print(f"⚠️  No action matching '{action_filter}' for {char_name}")
    else:
        print(f"⚠️  No armature matching '{armature_filter}' for {char_name}")
else:
    print(f"❌ Asset not found: {{asset_path}}")

'''

    def _generate_character_multi_action_code(self, character: Dict[str, Any]) -> str:
        """
        Multiple sequential actions via Blender NLA.

        Each entry in animation_sequence defines:
          action_filter    – substring to match in bpy.data.actions
          start_second     – when this segment begins (in scene seconds)
          end_second       – when this segment ends
          start_position   – character location at start_second
          end_position     – character location at end_second
          start_rotation   – [x,y,z] euler rotation in radians at start_second (optional)
          end_rotation     – [x,y,z] euler rotation in radians at end_second   (optional)
          interpolation    – LINEAR / BEZIER / CONSTANT for transform keyframes

        Bone animations → NLA strips (repeat-based looping within segment).
        Location + rotation keyframes → separate movement action in active-action slot.
        Rotation changes (e.g. character turning around) use BEZIER interpolation
        on the rotation curves so the turn looks smooth.
        """
        char_name       = character['name']
        sanitized_name  = self._sanitize_name(char_name)
        asset_path      = character['asset_path']
        armature_filter = character.get('armature_filter', 'Armature')
        scale           = character.get('scale', [1, 1, 1])
        sequence        = character['animation_sequence']
        frame_rate      = self.config['scene']['frame_rate']

        # Build segment data (convert seconds → 1-based frames)
        segments = []
        prev_end_rot = [0, 0, 0]
        for seg in sequence:
            sf = int(seg['start_second'] * frame_rate) + 1
            ef = int(seg['end_second']   * frame_rate) + 1
            s_rot = seg.get('start_rotation', prev_end_rot)
            e_rot = seg.get('end_rotation',   s_rot)
            prev_end_rot = e_rot
            segments.append({
                'action_filter':   seg['action_filter'],
                'lower_body_lock': seg.get('lower_body_lock'),   # e.g. "Man_Sitting"
                'start_frame':     sf,
                'end_frame':       ef,
                'start_pos':       seg.get('start_position', [0, 0, 0]),
                'end_pos':         seg.get('end_position',   [0, 0, 0]),
                'start_rot':       s_rot,
                'end_rot':         e_rot,
                'interp':          seg.get('interpolation', 'LINEAR'),
            })

        # Collect unique frame → (pos, rot, interp) — later segment wins on collision
        kf_map = {}
        for seg in segments:
            kf_map[seg['start_frame']] = (seg['start_pos'], seg['start_rot'], seg['interp'])
            kf_map[seg['end_frame']]   = (seg['end_pos'],   seg['end_rot'],   seg['interp'])

        # Detect which frames have a rotation change (for BEZIER smoothing)
        rot_change_frames = set()
        prev_rot = None
        for frame in sorted(kf_map.keys()):
            _, rot, _ = kf_map[frame]
            if prev_rot is not None and rot != prev_rot:
                rot_change_frames.add(frame)
            prev_rot = rot

        # ── Generate Blender script lines ────────────────────────────────────
        lines = []
        lines.append(f'\n# Character: {char_name}  [multi-action sequence]')
        lines.append(f'print("👤 Importing {char_name}...")')
        lines.append(f'{sanitized_name}_armature = None')
        lines.append(f'asset_path = os.path.join(asset_base_path, "{asset_path}")')
        lines.append('')
        lines.append('if os.path.exists(asset_path):')
        lines.append('    bpy.ops.import_scene.gltf(filepath=asset_path)')
        lines.append('    for obj in bpy.context.selected_objects:')
        lines.append(f'        if obj.type == "ARMATURE" and "{armature_filter}" in obj.name:')
        lines.append(f'            {sanitized_name}_armature = obj')
        lines.append('            break')
        lines.append('')
        lines.append(f'    if {sanitized_name}_armature:')
        lines.append(f'        _imported_scale = {sanitized_name}_armature.scale.copy()')
        lines.append(f'        {sanitized_name}_armature.scale = (')
        lines.append(f'            _imported_scale[0] * {scale[0]},')
        lines.append(f'            _imported_scale[1] * {scale[1]},')
        lines.append(f'            _imported_scale[2] * {scale[2]}')
        lines.append(f'        )')
        lines.append(f'        {sanitized_name}_armature.name = "{char_name}"')
        lines.append(f'        {sanitized_name}_armature.rotation_mode = "XYZ"')
        lines.append(f'        character_armatures["{char_name}"] = {sanitized_name}_armature')
        lines.append('')
        lines.append(f'        # Capture the import rotation so we only offset the Z (yaw),')
        lines.append(f'        # preserving the GLB coordinate-system correction on X/Y.')
        lines.append(f'        _init_rot_{sanitized_name} = {sanitized_name}_armature.rotation_euler.copy()')
        lines.append('')
        lines.append(f'        if not {sanitized_name}_armature.animation_data:')
        lines.append(f'            {sanitized_name}_armature.animation_data_create()')
        lines.append('')
        lines.append(f'        # --- Location + Rotation keyframes (active action) ---')
        lines.append(f'        _mov_action = bpy.data.actions.new("{char_name}_movement")')
        lines.append(f'        {sanitized_name}_armature.animation_data.action = _mov_action')

        for frame in sorted(kf_map.keys()):
            pos, rot, interp = kf_map[frame]
            # rot values are Z-axis offsets; X and Y stay at the imported values
            z_offset = rot[2]
            lines.append(f'        {sanitized_name}_armature.location = {pos}')
            lines.append(f'        {sanitized_name}_armature.rotation_euler = (')
            lines.append(f'            _init_rot_{sanitized_name}.x,')
            lines.append(f'            _init_rot_{sanitized_name}.y,')
            lines.append(f'            _init_rot_{sanitized_name}.z + {z_offset}')
            lines.append(f'        )')
            lines.append(f'        {sanitized_name}_armature.keyframe_insert(data_path="location", frame={frame})')
            lines.append(f'        {sanitized_name}_armature.keyframe_insert(data_path="rotation_euler", frame={frame})')

        # Set interpolation: BEZIER on rotation curves at turning frames, LINEAR elsewhere
        lines.append(f'        for _fc in _action_fcurves(_mov_action):')
        lines.append(f'            for _kp in _fc.keyframe_points:')
        lines.append(f'                _f = int(_kp.co[0])')
        lines.append(f'                if _fc.data_path == "rotation_euler" and _f in {sorted(rot_change_frames)}:')
        lines.append(f'                    _kp.interpolation = "BEZIER"')
        lines.append(f'                else:')
        lines.append(f'                    _kp.interpolation = "LINEAR"')
        lines.append('')

        # NLA strips for bone animations
        lines.append(f'        # --- NLA strips: one per animation segment ---')
        lines.append(f'        _nla_tracks = {sanitized_name}_armature.animation_data.nla_tracks')

        for i, seg in enumerate(segments):
            af  = seg['action_filter']
            lbl = seg['lower_body_lock']   # None or e.g. "Man_Sitting"
            sf  = seg['start_frame']
            ef  = seg['end_frame']
            lines.append(f'')
            label = f"{af} [lower={lbl}]" if lbl else af
            lines.append(f'        # Segment {i+1}: {label}  (frames {sf}–{ef})')

            # Find upper-body action — match "Name" or "Armature|Name" or "Name.001",
            # but never match blended actions that happen to contain the name as a substring.
            lines.append(f'        _seg{i}_upper = None')
            lines.append(f'        for _a in bpy.data.actions:')
            lines.append(f'            if _a.name.split("|")[-1].split(".")[0] == "{af}":')
            lines.append(f'                _seg{i}_upper = _a')
            lines.append(f'                break')

            if lbl:
                # Find lower-body lock action and build blended action at runtime
                lines.append(f'        _seg{i}_lower, _seg{i}_src_hips = _resolve_lower_action("{lbl}")')
                lines.append(f'        _seg{i}_dst_hips = _hips_len({sanitized_name}_armature.data)')
                lines.append(f'        _seg{i}_loc_scale = (_seg{i}_dst_hips / _seg{i}_src_hips) if (_seg{i}_src_hips and _seg{i}_dst_hips) else 1.0')
                blended_name = f"{char_name}_blended_{i}_{af}_over_{lbl}"
                lines.append(f'        if _seg{i}_upper and _seg{i}_lower:')
                lines.append(f'            _seg{i}_action = _build_blended_action(')
                lines.append(f'                {sanitized_name}_armature, _seg{i}_upper, _seg{i}_lower, "{blended_name}",')
                lines.append(f'                lower_loc_scale=_seg{i}_loc_scale)')
                lines.append(f'            print(f"  🔀 Blended action: upper={af} + lower={lbl}")')
                lines.append(f'        elif _seg{i}_upper:')
                lines.append(f'            _seg{i}_action = _seg{i}_upper')
                lines.append(f'            print("  ⚠️  lower_body_lock \'{lbl}\' not found — using upper only")')
                lines.append(f'        else:')
                lines.append(f'            _seg{i}_action = None')
            else:
                lines.append(f'        _seg{i}_action = _seg{i}_upper')

            lines.append(f'        if _seg{i}_action:')
            lines.append(f'            _track{i} = _nla_tracks.new()')
            lines.append(f'            _track{i}.name = "{af}"')
            lines.append(f'            _strip{i} = _track{i}.strips.new(_seg{i}_action.name, {sf}, _seg{i}_action)')
            # *_Sitting clips open with a sit-down from standing. When the character is
            # already seated (scene start, or previous segment also seated), start from
            # the settled pose instead of standing up and sitting down again.
            already_seated = lbl and (i == 0 or segments[i - 1]['lower_body_lock'])
            if already_seated and 'Sitting' in lbl:
                lines.append(f'            _strip{i}.action_frame_start += {SIT_SETTLE_FRAMES}')
            lines.append(f'            _strip{i}.frame_start   = {sf}')
            lines.append(f'            _strip{i}.frame_end     = {ef}')
            # Cross-fade into the next segment instead of snapping: this strip runs on for
            # the next strip's blend-in, and the next strip fades in on top of it. Strips do
            # not hold past that, so channels one action keys and the next doesn't (e.g.
            # Walk's feet under Idle) don't leak into later segments.
            _blend = lambda a, b: min(NLA_BLEND_FRAMES, max(0, (b - a) // 2))
            ext = _blend(segments[i + 1]['start_frame'], segments[i + 1]['end_frame']) if i + 1 < len(segments) else 0
            lines.append(f'            _strip{i}.extrapolation = "NOTHING"')
            if i > 0:
                lines.append(f'            _strip{i}.blend_in = {_blend(sf, ef)}')
            lines.append(f'            _act{i}_len = _seg{i}_action.frame_range[1] - _seg{i}_action.frame_range[0]')
            lines.append(f'            if _act{i}_len > 0:')
            lines.append(f'                _strip{i}.repeat = max(1.0, ({ef} - {sf} + {ext}) / _act{i}_len)')
            lines.append(f'            print(f"  ✅ {char_name} seg {i+1}: {{{{_seg{i}_action.name}}}} frames {sf}–{ef} (repeat={{{{_strip{i}.repeat:.1f}}}}x)")')
            lines.append(f'        else:')
            lines.append(f'            print("  ⚠️  Action not found: {af}")')

        lines.append(f'')
        lines.append(f'        print("✅ {char_name}: {len(segments)}-segment sequence set up via NLA")')
        lines.append(f'    else:')
        lines.append(f'        print("⚠️  No armature matching \'{armature_filter}\' for {char_name}")')
        lines.append(f'else:')
        lines.append(f'    print(f"❌ Asset not found: {{asset_path}}")')
        lines.append('')

        return '\n'.join(lines)
    
    def _generate_environment_code(self) -> str:
        """Generate environment setup code"""
        env = self.config.get('environment', {})
        code = '''
# Environment setup
print("🌍 Setting up environment...")

'''
        
        # Base surface
        if 'base_surface' in env:
            surface = env['base_surface']
            surface_type = surface.get('type', 'plane')
            size = surface.get('size', 20)
            position = surface.get('position', [0, 0, -1])
            name = surface.get('name', 'Ground')
            material = surface.get('material', {})
            
            if surface_type == 'plane':
                code += f'''
# Base surface
bpy.ops.mesh.primitive_plane_add(size={size}, location={position})
base_surface = bpy.context.active_object
base_surface.name = "{name}"

'''
            
            # Add material
            if material:
                base_color = material.get('base_color', [0.8, 0.8, 0.8, 1.0])
                metallic = material.get('metallic', 0.0)
                roughness = material.get('roughness', 0.5)
                
                code += f'''
# Base surface material
material = bpy.data.materials.new(name="{name}_Material")
material.use_nodes = True
material.node_tree.nodes.clear()
bsdf = material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
output = material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
material.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
bsdf.inputs[0].default_value = {base_color}  # Base Color
bsdf.inputs[1].default_value = {metallic}     # Metallic
bsdf.inputs[2].default_value = {roughness}    # Roughness
base_surface.data.materials.append(material)

'''
        
        # Scattered elements
        for element in env.get('scattered_elements', []):
            code += self._generate_scattered_element_code(element)
        
        return code
    
    def _generate_scattered_element_code(self, element: Dict[str, Any]) -> str:
        """Generate code for scattered environment elements"""
        name = element.get('name', 'Element')
        asset_path = element.get('asset_path', '')
        scale = element.get('scale', [1, 1, 1])
        count = element.get('count', 1)
        random_seed = element.get('random_seed', 42)
        scatter_area = element.get('scatter_area', {})
        
        x_range = scatter_area.get('x_range', [-10, 10])
        y_range = scatter_area.get('y_range', [-10, 10])
        z_position = scatter_area.get('z_position', 0)
        
        return f'''
# Scattered element: {name}
print("🌲 Adding {name}...")
element_path = os.path.join(asset_base_path, "{asset_path}")

if os.path.exists(element_path):
    bpy.ops.import_scene.gltf(filepath=element_path)
    imported_objects = bpy.context.selected_objects.copy()
    
    # Only scale root objects (no parent) to avoid compounding scale through hierarchy
    # Multiply on top of natural import scale (README values are multipliers, not absolutes)
    root_objects = [obj for obj in imported_objects if obj.parent is None]
    for obj in root_objects:
        obj.scale = (
            obj.scale[0] * {scale[0]},
            obj.scale[1] * {scale[1]},
            obj.scale[2] * {scale[2]}
        )
    
    if imported_objects:
        main_obj = root_objects[0] if root_objects else imported_objects[0]
        
        # Set up random scattering
        random.seed({random_seed})
        
        # Position first object
        main_obj.location = (
            random.uniform({x_range[0]}, {x_range[1]}),
            random.uniform({y_range[0]}, {y_range[1]}),
            {z_position}
        )
        main_obj.name = f"{name}_001"
        
        # Create scattered duplicates (count-1 additional copies)
        for i in range(1, {count}):
            copy = main_obj.copy()
            copy.data = main_obj.data.copy()
            copy.name = f"{name}_{{i+1:03d}}"
            
            copy.location = (
                random.uniform({x_range[0]}, {x_range[1]}),
                random.uniform({y_range[0]}, {y_range[1]}),
                {z_position}
            )
            bpy.context.collection.objects.link(copy)
        
        print(f"✅ Added {count} {name} objects")
else:
    print(f"❌ Asset not found: {{element_path}}")

'''
    
    def _generate_props_code(self) -> str:
        """Generate code to import props and parent them to character bones."""
        props = self.config.get('props', [])
        if not props:
            return ''

        code = '''
# Props — parented to character bones
print("🔧 Attaching props...")
'''
        for prop in props:
            name            = prop.get('name', 'Prop')
            asset_path      = prop.get('asset_path', '')
            scale           = prop.get('scale', [1, 1, 1])
            attach_to       = prop.get('attach_to', '')
            bone            = prop.get('bone', 'Palm.R')
            pos_offset      = prop.get('position_offset', [0, 0, 0])
            rot_offset      = prop.get('rotation_offset', [0, 0, 0])
            reveal_at_sec   = prop.get('reveal_at_second', None)
            frame_rate      = self.config.get('scene', {}).get('frame_rate', 24)
            sanitized       = self._sanitize_name(name)

            code += f'''
# Prop: {name}
_prop_{sanitized}_path = os.path.join(asset_base_path, "{asset_path}")
if os.path.exists(_prop_{sanitized}_path):
    bpy.ops.import_scene.gltf(filepath=_prop_{sanitized}_path)
    _prop_{sanitized}_objects = bpy.context.selected_objects.copy()
    _prop_{sanitized}_roots = [o for o in _prop_{sanitized}_objects if o.parent is None]
    if _prop_{sanitized}_roots:
        _prop_{sanitized} = _prop_{sanitized}_roots[0]
        _prop_{sanitized}.name = "{name}"

        # Parent to bone
        _target_armature = character_armatures.get("{attach_to}")
        if _target_armature:
            # Update dependency graph so bone world matrices are current
            bpy.context.view_layer.update()

            _prop_{sanitized}.parent       = _target_armature
            _prop_{sanitized}.parent_type  = 'BONE'
            _prop_{sanitized}.parent_bone  = "{bone}"

            # matrix_parent_inverse must be Identity so that prop.location is
            # interpreted in bone-local space. Calling .identity() on the property
            # modifies a temporary copy and has no effect (common Blender Python trap),
            # so we assign a new Identity matrix directly.
            _prop_{sanitized}.matrix_parent_inverse = mathutils.Matrix.Identity(4)

            # Position / rotation offset in bone-local space
            _prop_{sanitized}.location     = mathutils.Vector({pos_offset})
            _prop_{sanitized}.rotation_euler = mathutils.Euler({rot_offset})

            # Scale: JSON values are world-space metres. Divide by armature world
            # scale so size is correct regardless of GLB import scale (~100 for cm GLBs).
            _arm_ws = _target_armature.matrix_world.to_scale()[0]
            if _arm_ws > 0:
                _prop_{sanitized}.scale = (
                    {scale[0]} / _arm_ws,
                    {scale[1]} / _arm_ws,
                    {scale[2]} / _arm_ws,
                )
            else:
                _prop_{sanitized}.scale = ({scale[0]}, {scale[1]}, {scale[2]})

            print(f"✅ '{name}' attached to {{_target_armature.name}} / {bone} (arm_ws={{_arm_ws:.3f}})")
'''
            # Visibility keyframes: hide prop until reveal_at_second
            if reveal_at_sec is not None:
                reveal_frame = int(reveal_at_sec * frame_rate) + 1
                code += f'''
            # Hide prop until frame {reveal_frame} (reveal_at_second={reveal_at_sec})
            for _po in _prop_{sanitized}_objects:
                _po.hide_viewport = True
                _po.hide_render   = True
                _po.keyframe_insert(data_path="hide_viewport", frame=1)
                _po.keyframe_insert(data_path="hide_render",   frame=1)
                _po.hide_viewport = True
                _po.hide_render   = True
                _po.keyframe_insert(data_path="hide_viewport", frame={reveal_frame - 1})
                _po.keyframe_insert(data_path="hide_render",   frame={reveal_frame - 1})
                _po.hide_viewport = False
                _po.hide_render   = False
                _po.keyframe_insert(data_path="hide_viewport", frame={reveal_frame})
                _po.keyframe_insert(data_path="hide_render",   frame={reveal_frame})
            print(f"  🔒 '{name}' hidden until frame {reveal_frame}")
'''
            code += f'''
        else:
            print(f"⚠️  Character '{attach_to}' not found for prop '{name}'")
    else:
        print(f"⚠️  No root object found in prop '{name}'")
else:
    print(f"❌ Prop asset not found: {{_prop_{sanitized}_path}}")
'''
        return code

    def _generate_camera_code(self) -> str:
        """Generate camera setup code"""
        camera = self.config.get('camera', {})
        position = camera.get('position', [7, -7, 5])
        rotation_deg = camera.get('rotation', [1.1, 0, 0.8])
        # Convert degrees to radians if values seem to be in degrees (> 6.28)
        rotation = [math.radians(r) if abs(r) > 6.28 else r for r in rotation_deg]
        lens_mm = camera.get('lens_mm', 50)
        
        return f'''
# Camera setup
print("📹 Setting up camera...")
bpy.ops.object.camera_add(location={position})
camera = bpy.context.active_object
camera.rotation_euler = {rotation}
camera.data.lens = {lens_mm}
bpy.context.scene.camera = camera

'''
    
    def _generate_lighting_code(self) -> str:
        """Generate lighting setup code"""
        lighting = self.config.get('lighting', [])
        code = '''
# Lighting setup
print("💡 Setting up lighting...")
'''
        
        for i, light in enumerate(lighting):
            light_type = light.get('type', 'SUN')
            position = light.get('position', [5, 5, 10])
            energy = light.get('energy', 3.0)
            
            code += f'''
bpy.ops.object.light_add(type='{light_type}', location={position})
light_{i} = bpy.context.active_object
light_{i}.data.energy = {energy}
'''
        
        return code
    
    def _generate_render_code(self) -> str:
        """Generate rendering setup code"""
        return '''
# Render setup
if render_video:
    print("🎥 Setting up video render...")
    scene.render.resolution_x = 854
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.filepath = output_file.replace('.blend', '.mp4')
    
    bpy.ops.render.render(animation=True)
    print(f"🎬 Video rendered: {scene.render.filepath}")

# Save blend file
bpy.ops.wm.save_as_mainfile(filepath=output_file)
print(f"📁 Saved: {output_file}")
print("✅ Scene generation complete!")
'''
    
    def generate_blender_script(self, output_file: str, render_video: bool = False) -> str:
        """Generate complete Blender Python script"""
        script_parts = [
            self._generate_header(),
            f'output_file = "{output_file}"',
            f'render_video = {render_video}',
        ]
        
        # Add characters
        for character in self.config.get('characters', []):
            script_parts.append(self._generate_character_code(character))

        # Add props (must come after characters so character_armatures is populated)
        script_parts.append(self._generate_props_code())

        # Add environment, camera, lighting, render
        script_parts.extend([
            self._generate_environment_code(),
            self._generate_camera_code(),
            self._generate_lighting_code(),
            self._generate_render_code()
        ])
        
        return '\n'.join(script_parts)
    
    def generate_scene(self, output_file: str = None, render_video: bool = False) -> bool:
        """Generate Blender scene from configuration"""
        if output_file is None:
            scene_name = self.config['scene']['name'].replace(' ', '_').replace('.', '_')
            output_file = f"{scene_name}.blend"
        
        # Ensure absolute path
        if not os.path.isabs(output_file):
            output_file = os.path.abspath(output_file)
        
        print(f"🎬 Generating scene: {self.config['scene']['name']}")
        print(f"📁 Output file: {output_file}")
        
        # Generate script
        script = self.generate_blender_script(output_file, render_video)
        
        # Save script for debugging
        script_file = "temp_optimized_scene_script.py"
        with open(script_file, 'w') as f:
            f.write(script)
        
        debug_script_path = "debug_optimized_script.py"
        with open(debug_script_path, 'w') as f:
            f.write(script)
        print(f"🐛 Debug script saved to: {debug_script_path}")
        
        # Execute in Blender
        try:
            result = subprocess.run([
                self.blender_path,
                "--background",
                "--python-exit-code", "1",
                "--python", script_file
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"\\n✅ Scene generated successfully!")
                print(f"📁 Saved as: {output_file}")
                
                # Clean up temp script
                if os.path.exists(script_file):
                    os.remove(script_file)
                
                return True
            else:
                print(f"\\n❌ Blender execution failed!")
                print(f"Error: {result.stderr[-1500:]}")
                return False
                
        except subprocess.TimeoutExpired:
            print("\\n⏰ Blender execution timed out!")
            return False
        except Exception as e:
            print(f"\\n❌ Error executing Blender: {e}")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Optimized Flexible Scene Generator')
    parser.add_argument('config', help='JSON configuration file')
    parser.add_argument('--output', '-o', help='Output blend file name')
    parser.add_argument('--video', action='store_true', help='Render video')
    parser.add_argument('--no-video', action='store_true', help='Skip video rendering')
    
    args = parser.parse_args()
    
    # Determine video rendering
    render_video = False
    if args.video:
        render_video = True
    elif not args.no_video:
        # Ask user if not specified
        try:
            response = input("🎥 Do you want to render a low-quality 480p video? (y/N): ").strip().lower()
            render_video = response in ['y', 'yes']
        except KeyboardInterrupt:
            print("\\n👋 Cancelled by user")
            return
    
    try:
        # Create generator
        generator = OptimizedSceneGenerator(args.config)
        
        # Generate scene
        success = generator.generate_scene(args.output, render_video)
        
        if success:
            print("\\n🎉 Scene generation completed successfully!")
        else:
            print("\\n💥 Scene generation failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
