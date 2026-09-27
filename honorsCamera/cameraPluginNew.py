import bpy
import mathutils
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import FloatProperty, EnumProperty, PointerProperty
from math import radians, sin, cos

# --- ADDON METADATA ---
bl_info = {
    "name": "Cinematic Camera Tools",
    "author": "User",
    "version": (5, 0),
    "blender": (4, 0, 0),
    "location": "3D Viewport > Sidebar > Camera Tab",
    "description": "Push In, Push Out, Orbit (curve path), and Track (follow) camera movements.",
    "category": "Animation",
}

# --- SHARED CONSTANTS ---
DEFAULT_CLOSE         = 2.0
DEFAULT_WIDE          = 10.0
ANIMATION_DURATION    = 90
DEFAULT_TARGET_HEIGHT = 4.1   # character eyes


# ======================================================================
# PROPERTY GROUP
# ======================================================================
class CameraToolsProperties(PropertyGroup):

    # ------------------------------------------------------------------
    # Shared: target mode
    # ------------------------------------------------------------------
    target_type: EnumProperty(
        name="Target Mode",
        description="Choose the camera focus point",
        items=[
            ('CHARACTER', "Character (Eyes)", "Focus on character eyes at 4.1m"),
            ('OBJECT',    "Object (Center)",  "Focus on object origin at 0m"),
        ],
        default='CHARACTER',
    )

    # ------------------------------------------------------------------
    # Push In
    # ------------------------------------------------------------------
    push_in_start: FloatProperty(
        name="Start Distance",
        description="Starting distance from target (wide shot)",
        default=DEFAULT_WIDE, min=0.1, max=100.0, step=1, precision=2,
    )
    push_in_end: FloatProperty(
        name="End Distance",
        description="Ending distance from target (close shot)",
        default=DEFAULT_CLOSE, min=0.1, max=100.0, step=1, precision=2,
    )
    push_in_duration: FloatProperty(
        name="Duration (Frames)",
        default=ANIMATION_DURATION, min=1, max=1000, step=1, precision=0,
    )
    push_in_angle: FloatProperty(
        name="Angle (Deg)",
        description="0 = behind character, 90 = right side",
        default=0.0, min=-360.0, max=360.0, step=10, precision=1,
    )

    # ------------------------------------------------------------------
    # Push Out
    # ------------------------------------------------------------------
    push_out_start: FloatProperty(
        name="Start Distance",
        description="Starting distance from target (close shot)",
        default=DEFAULT_CLOSE, min=0.1, max=100.0, step=1, precision=2,
    )
    push_out_end: FloatProperty(
        name="End Distance",
        description="Ending distance from target (wide shot)",
        default=DEFAULT_WIDE, min=0.1, max=100.0, step=1, precision=2,
    )
    push_out_duration: FloatProperty(
        name="Duration (Frames)",
        default=ANIMATION_DURATION, min=1, max=1000, step=1, precision=0,
    )
    push_out_angle: FloatProperty(
        name="Angle (Deg)",
        description="0 = behind character, 90 = right side",
        default=0.0, min=-360.0, max=360.0, step=10, precision=1,
    )

    # ------------------------------------------------------------------
    # Orbit  (from cameraOrbit.py v1.2)
    # ------------------------------------------------------------------
    orbit_radius: FloatProperty(
        name="Radius",
        description="Distance from target to camera",
        default=5.0, min=0.1, max=200.0, step=10, precision=2,
    )
    orbit_start_angle: FloatProperty(
        name="Start Angle (°)",
        description="0°=behind  90°=right  180°=front  270°=left",
        default=0.0, min=-360.0, max=360.0, step=10, precision=1,
    )
    orbit_end_angle: FloatProperty(
        name="End Angle (°)",
        description="Ending position on the circle",
        default=360.0, min=-360.0, max=360.0, step=10, precision=1,
    )
    orbit_duration: FloatProperty(
        name="Duration (Frames)",
        default=ANIMATION_DURATION, min=1, max=2000, step=1, precision=0,
    )
    orbit_camera_height: FloatProperty(
        name="Height Offset",
        description=(
            "Vertical offset of the orbit circle relative to the look-at point.\n"
            "  0 = level orbit\n"
            " +ve = above (high angle, looking down)\n"
            " -ve = below (low angle, looking up)"
        ),
        default=0.0, min=-50.0, max=50.0, step=10, precision=2,
    )

    # ------------------------------------------------------------------
    # Track / Follow  (from cameraTrack.py v1.2)
    # ------------------------------------------------------------------
    track_depth: FloatProperty(
        name="Depth",
        description="Distance in front of / behind the subject",
        default=5.0, min=0.1, max=200.0, step=10, precision=2,
    )
    track_height: FloatProperty(
        name="Height Offset",
        description=(
            "Camera height relative to the look-at point.\n"
            "  0 = same level   +ve = above   -ve = below"
        ),
        default=0.0, min=-20.0, max=20.0, step=10, precision=2,
    )
    track_lateral: FloatProperty(
        name="Lateral Offset",
        description="Side offset (+ = right of subject, - = left)",
        default=0.0, min=-50.0, max=50.0, step=10, precision=2,
    )
    track_angle: FloatProperty(
        name="Angle (°)",
        description=(
            "0° = in front (direction character faces)\n"
            "90° = right side   180° = behind   270° = left side"
        ),
        default=0.0, min=-360.0, max=360.0, step=10, precision=1,
    )


# ======================================================================
# SHARED HELPER: create / update look-at empty parented to subject
# ======================================================================
def _get_or_create_look_at(subject, look_name, target_height, context):
    look_at = bpy.data.objects.get(look_name)
    if look_at is None:
        bpy.ops.object.empty_add(type='SPHERE', location=(0, 0, 0))
        look_at = context.active_object
        look_at.name = look_name
        look_at.empty_display_size = 0.15
        look_at.hide_select   = True
        look_at.hide_viewport = True
    if look_at.parent != subject:
        look_at.parent = subject
        look_at.matrix_parent_inverse.identity()
    look_at.location = (0.0, 0.0, target_height)
    return look_at


# ======================================================================
# LOGIC: Push In / Push Out  (unchanged working version)
# ======================================================================
def linear_shot_logic(protagonist, camera, start_depth, end_depth,
                      start_lateral, end_lateral, duration, angle_offset):
    """Linear camera movement (Push In / Push Out) with Track To constraint."""

    context     = bpy.context
    props       = context.scene.camera_tools
    target_h    = DEFAULT_TARGET_HEIGHT if props.target_type == 'CHARACTER' else 0.0

    # Target empty
    look_at = _get_or_create_look_at(
        protagonist, f"{protagonist.name}_Target", target_h, context
    )

    # Camera constraints
    for c in list(camera.constraints):
        camera.constraints.remove(c)
    if camera.animation_data:
        camera.animation_data_clear()
    camera.parent = None
    camera.matrix_parent_inverse.identity()
    camera.rotation_euler = (0, 0, 0)

    track_to = camera.constraints.new(type='TRACK_TO')
    track_to.target     = look_at
    track_to.track_axis = 'TRACK_NEGATIVE_Z'
    track_to.up_axis    = 'UP_Y'

    context.scene.frame_end = duration
    context.view_layer.update()

    angle_rad = radians(angle_offset)
    p_loc     = protagonist.matrix_world.translation

    start_x = (start_lateral * cos(angle_rad) - (-start_depth) * sin(angle_rad)) + p_loc.x
    start_y = (start_lateral * sin(angle_rad) + (-start_depth) * cos(angle_rad)) + p_loc.y
    end_x   = (end_lateral   * cos(angle_rad) - (-end_depth)   * sin(angle_rad)) + p_loc.x
    end_y   = (end_lateral   * sin(angle_rad) + (-end_depth)   * cos(angle_rad)) + p_loc.y
    cam_z   = p_loc.z + target_h

    camera.parent = None
    camera.matrix_parent_inverse.identity()

    camera.location = (start_x, start_y, cam_z)
    camera.keyframe_insert(data_path="location", frame=1)
    camera.location = (end_x, end_y, cam_z)
    camera.keyframe_insert(data_path="location", frame=duration)

    if camera.animation_data and camera.animation_data.action:
        for fcu in camera.animation_data.action.fcurves:
            if fcu.data_path.startswith("location"):
                for kp in fcu.keyframe_points:
                    kp.interpolation = 'BEZIER'

    context.scene.frame_current = 1
    return protagonist.name


# ======================================================================
# LOGIC: Orbit  (from cameraOrbit.py v1.2 — exact copy)
# ======================================================================
def orbit_logic(subject, camera, radius, start_angle, end_angle,
                duration, camera_height, target_height, context):
    """
    Orbit camera around subject using a circular curve path (Method 2).
    Exact logic from cameraOrbit.py v1.2.
    """
    # 1. Look-at empty
    look_at = _get_or_create_look_at(
        subject, f"{subject.name}_Orbit_LookAt", target_height, context
    )
    context.view_layer.update()
    look_world = look_at.matrix_world.translation.copy()

    # 2. Remove old curve + data + purge orphans
    path_name = f"{subject.name}_Orbit_Path"
    old_path  = bpy.data.objects.get(path_name)
    if old_path is not None:
        old_curve_data = old_path.data
        bpy.data.objects.remove(old_path, do_unlink=True)
        if old_curve_data and old_curve_data.users == 0:
            bpy.data.curves.remove(old_curve_data)
    bpy.ops.outliner.orphans_purge(do_recursive=True)

    # 3. Build circle at look-world + height offset
    orbit_center = look_world.copy()
    orbit_center.z += camera_height

    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=orbit_center)
    path_obj = context.active_object
    path_obj.name = path_name
    path_obj.data.use_path      = True
    path_obj.data.path_duration = int(duration)
    path_obj.hide_select   = True
    path_obj.hide_viewport = True
    path_obj.hide_render   = True

    # 4. Clean up camera
    for c in list(camera.constraints):
        camera.constraints.remove(c)
    if camera.animation_data:
        camera.animation_data_clear()
    camera.parent = None
    camera.matrix_parent_inverse.identity()
    camera.location       = (0.0, 0.0, 0.0)
    camera.rotation_euler = (0.0, 0.0, 0.0)

    # 5. Follow Path constraint
    follow = camera.constraints.new(type='FOLLOW_PATH')
    follow.target             = path_obj
    follow.use_fixed_location = True
    follow.use_curve_follow   = False
    follow.forward_axis       = 'FORWARD_Y'
    follow.up_axis            = 'UP_Z'

    start_offset = start_angle / 360.0
    end_offset   = end_angle   / 360.0

    context.scene.frame_end     = int(duration)
    context.scene.frame_current = 1

    kf_path = f'constraints["{follow.name}"].offset_factor'
    follow.offset_factor = start_offset
    camera.keyframe_insert(data_path=kf_path, frame=1)
    follow.offset_factor = end_offset
    camera.keyframe_insert(data_path=kf_path, frame=int(duration))

    # 6. Track To
    track = camera.constraints.new(type='TRACK_TO')
    track.target     = look_at
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis    = 'UP_Y'

    # 7. Linear interpolation
    if camera.animation_data and camera.animation_data.action:
        for fcu in camera.animation_data.action.fcurves:
            for kp in fcu.keyframe_points:
                kp.interpolation = 'LINEAR'

    context.scene.frame_current = 1
    return subject.name


# ======================================================================
# LOGIC: Track / Follow  (from cameraTrack.py v1.2 — exact copy)
# ======================================================================
def track_attach_logic(subject, camera, depth, height, lateral,
                       angle, target_height, context):
    """
    Parent camera to subject with Keep Transformation (Method 3).
    Exact logic from cameraTrack.py v1.2.
    """
    # 1. Look-at empty
    look_at = _get_or_create_look_at(
        subject, f"{subject.name}_Track_LookAt", target_height, context
    )
    context.view_layer.update()

    # 2. Camera world position — relative to subject's facing direction
    angle_rad   = radians(angle)
    cam_local_x = depth * sin(angle_rad) + lateral * cos(angle_rad)
    cam_local_y = depth * cos(angle_rad) - lateral * sin(angle_rad)

    subj_pos  = subject.matrix_world.translation
    subj_rot  = subject.matrix_world.to_3x3().normalized()
    world_horiz = subj_rot @ mathutils.Vector((cam_local_x, cam_local_y, 0.0))

    cam_world_x = subj_pos.x + world_horiz.x
    cam_world_y = subj_pos.y + world_horiz.y
    cam_world_z = subj_pos.z + target_height + height

    # 3. Clean up camera
    for c in list(camera.constraints):
        camera.constraints.remove(c)
    if camera.animation_data:
        camera.animation_data_clear()
    camera.parent = None
    camera.matrix_parent_inverse.identity()

    # 4. Place camera
    camera.location       = (cam_world_x, cam_world_y, cam_world_z)
    camera.rotation_euler = (0.0, 0.0, 0.0)

    # 5. Track To
    track = camera.constraints.new(type='TRACK_TO')
    track.target     = look_at
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis    = 'UP_Y'

    # 6. Parent with Keep Transformation
    context.view_layer.update()
    world_matrix_before = camera.matrix_world.copy()
    camera.parent = subject
    context.view_layer.update()
    camera.matrix_world = world_matrix_before
    context.view_layer.update()

    return subject.name


def track_detach_logic(camera, context):
    """Remove parent + constraints, camera stays in place."""
    context.view_layer.update()
    world_mat     = camera.matrix_world.copy()
    camera.parent = None
    camera.matrix_world = world_mat
    for c in list(camera.constraints):
        camera.constraints.remove(c)


# ======================================================================
# OPERATORS
# ======================================================================

# --- Push In ---
class CAMERA_OT_push_in(Operator):
    bl_idname   = "camera.push_in_shot"
    bl_label    = "Execute Push In"
    bl_options  = {'REGISTER', 'UNDO'}

    def execute(self, context):
        subject = context.view_layer.objects.active
        camera  = context.scene.camera
        props   = context.scene.camera_tools
        if not subject or not camera:
            self.report({'ERROR'}, "Select subject and ensure a scene camera is set.")
            return {'CANCELLED'}
        name = linear_shot_logic(
            subject, camera,
            props.push_in_start, props.push_in_end,
            0.0, 0.0,
            int(props.push_in_duration), props.push_in_angle,
        )
        self.report({'INFO'}, f"Push In on '{name}' — angle {props.push_in_angle}°")
        return {'FINISHED'}


# --- Push Out ---
class CAMERA_OT_push_out(Operator):
    bl_idname   = "camera.push_out_shot"
    bl_label    = "Execute Push Out"
    bl_options  = {'REGISTER', 'UNDO'}

    def execute(self, context):
        subject = context.view_layer.objects.active
        camera  = context.scene.camera
        props   = context.scene.camera_tools
        if not subject or not camera:
            self.report({'ERROR'}, "Select subject and ensure a scene camera is set.")
            return {'CANCELLED'}
        name = linear_shot_logic(
            subject, camera,
            props.push_out_start, props.push_out_end,
            0.0, 0.0,
            int(props.push_out_duration), props.push_out_angle,
        )
        self.report({'INFO'}, f"Push Out on '{name}' — angle {props.push_out_angle}°")
        return {'FINISHED'}


# --- Orbit ---
class CAMERA_OT_orbit(Operator):
    bl_idname   = "camera.orbit_shot"
    bl_label    = "Execute Orbit"
    bl_options  = {'REGISTER', 'UNDO'}

    def execute(self, context):
        subject = context.view_layer.objects.active
        camera  = context.scene.camera
        props   = context.scene.camera_tools
        if not subject or not camera:
            self.report({'ERROR'}, "Select subject and ensure a scene camera is set.")
            return {'CANCELLED'}
        if camera == subject:
            self.report({'ERROR'}, "Active object is the camera — select the subject instead.")
            return {'CANCELLED'}
        target_h = DEFAULT_TARGET_HEIGHT if props.target_type == 'CHARACTER' else 0.0
        name = orbit_logic(
            subject, camera,
            props.orbit_radius,
            props.orbit_start_angle, props.orbit_end_angle,
            props.orbit_duration,
            props.orbit_camera_height,
            target_h, context,
        )
        self.report(
            {'INFO'},
            f"Orbit on '{name}'  {props.orbit_start_angle}°→{props.orbit_end_angle}°  "
            f"r={props.orbit_radius}m  h={props.orbit_camera_height:+.1f}m"
        )
        return {'FINISHED'}


# --- Track Attach ---
class CAMERA_OT_track_attach(Operator):
    bl_idname   = "camera.track_attach"
    bl_label    = "Attach Camera to Subject"
    bl_options  = {'REGISTER', 'UNDO'}

    def execute(self, context):
        subject = context.view_layer.objects.active
        camera  = context.scene.camera
        props   = context.scene.camera_tools
        if not subject or not camera:
            self.report({'ERROR'}, "Select subject and ensure a scene camera is set.")
            return {'CANCELLED'}
        if camera == subject:
            self.report({'ERROR'}, "Active object is the camera — select the subject instead.")
            return {'CANCELLED'}
        target_h = DEFAULT_TARGET_HEIGHT if props.target_type == 'CHARACTER' else 0.0
        name = track_attach_logic(
            subject, camera,
            props.track_depth, props.track_height,
            props.track_lateral, props.track_angle,
            target_h, context,
        )
        self.report(
            {'INFO'},
            f"Camera attached to '{name}'  "
            f"depth={props.track_depth}m  h={props.track_height:+.1f}m  "
            f"lat={props.track_lateral:+.1f}m  angle={props.track_angle}°"
        )
        return {'FINISHED'}


# --- Track Detach ---
class CAMERA_OT_track_detach(Operator):
    bl_idname   = "camera.track_detach"
    bl_label    = "Detach Camera"
    bl_options  = {'REGISTER', 'UNDO'}

    def execute(self, context):
        camera = context.scene.camera
        if not camera:
            self.report({'ERROR'}, "No scene camera set.")
            return {'CANCELLED'}
        track_detach_logic(camera, context)
        self.report({'INFO'}, "Camera detached.")
        return {'FINISHED'}


# ======================================================================
# UI PANEL
# ======================================================================
class VIEW3D_PT_camera_tools(Panel):
    bl_label       = "Cinematic Camera Tools"
    bl_idname      = "VIEW3D_PT_CAMERA_TOOLS"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Camera'

    def draw(self, context):
        layout  = self.layout
        props   = context.scene.camera_tools
        subject = context.view_layer.objects.active
        camera  = context.scene.camera

        # Status
        row = layout.row()
        row.label(
            text=f"Subject: {subject.name}" if subject else "No object selected",
            icon='OBJECT_DATA' if subject else 'ERROR',
        )
        row = layout.row()
        row.label(
            text=f"Camera: {camera.name}" if camera else "No scene camera!",
            icon='CAMERA_DATA' if camera else 'ERROR',
        )
        layout.separator()

        # Target Mode (shared)
        layout.label(text="Focus Point:", icon='PIVOT_CURSOR')
        layout.prop(props, "target_type", expand=True)
        layout.separator()

        # ---- Push In ----
        box = layout.box()
        box.label(text="Push In (Wide → Close):", icon='TRIA_RIGHT')
        col = box.column(align=True)
        col.prop(props, "push_in_start",    text="Start Dist")
        col.prop(props, "push_in_end",      text="End Dist")
        col.prop(props, "push_in_duration", text="Frames")
        col.prop(props, "push_in_angle",    text="Angle")
        col.operator(CAMERA_OT_push_in.bl_idname, icon='PLAY')

        # ---- Push Out ----
        box = layout.box()
        box.label(text="Push Out (Close → Wide):", icon='TRIA_LEFT')
        col = box.column(align=True)
        col.prop(props, "push_out_start",    text="Start Dist")
        col.prop(props, "push_out_end",      text="End Dist")
        col.prop(props, "push_out_duration", text="Frames")
        col.prop(props, "push_out_angle",    text="Angle")
        col.operator(CAMERA_OT_push_out.bl_idname, icon='PLAY')

        # ---- Orbit ----
        box = layout.box()
        box.label(text="Orbit (Circular Path):", icon='FORCE_MAGNETIC')
        col = box.column(align=True)
        col.prop(props, "orbit_radius",        text="Radius (m)")
        col.prop(props, "orbit_camera_height", text="Height Offset (m)")
        col.prop(props, "orbit_start_angle",   text="Start Angle")
        col.prop(props, "orbit_end_angle",     text="End Angle")
        col.prop(props, "orbit_duration",      text="Frames")
        col.operator(CAMERA_OT_orbit.bl_idname, icon='PLAY')

        # ---- Track / Follow ----
        box = layout.box()
        box.label(text="Track (Follow Subject):", icon='TRACKING')

        # Show animation source
        if subject:
            path_info = None
            for c in subject.constraints:
                if c.type == 'FOLLOW_PATH' and c.target:
                    path_info = c.target.name
                    break
            if camera and camera.parent:
                box.label(text=f"Following: {camera.parent.name}", icon='LINKED')
            if path_info:
                box.label(text=f"Path: '{path_info}'", icon='CURVE_DATA')
            elif subject.animation_data and subject.animation_data.action:
                box.label(text=f"Action: '{subject.animation_data.action.name}'", icon='ACTION')
            else:
                box.label(text="No animation detected yet.", icon='QUESTION')

        col = box.column(align=True)
        col.prop(props, "track_depth",   text="Depth (m)")
        col.prop(props, "track_height",  text="Height Offset (m)")
        col.prop(props, "track_lateral", text="Lateral (m)")
        col.prop(props, "track_angle",   text="Angle (°)")
        row = box.row(align=True)
        row.operator(CAMERA_OT_track_attach.bl_idname, icon='LINKED')
        row.operator(CAMERA_OT_track_detach.bl_idname, icon='UNLINKED')


# ======================================================================
# REGISTRATION
# ======================================================================
classes = (
    CameraToolsProperties,
    CAMERA_OT_push_in,
    CAMERA_OT_push_out,
    CAMERA_OT_orbit,
    CAMERA_OT_track_attach,
    CAMERA_OT_track_detach,
    VIEW3D_PT_camera_tools,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.camera_tools = PointerProperty(type=CameraToolsProperties)

def unregister():
    del bpy.types.Scene.camera_tools
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()
