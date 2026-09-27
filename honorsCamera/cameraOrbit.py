import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import FloatProperty, EnumProperty, PointerProperty

bl_info = {
    "name": "Camera Orbit",
    "author": "User",
    "version": (1, 2),
    "blender": (4, 0, 0),
    "location": "3D Viewport > Sidebar > Camera Tab",
    "description": "Orbit a camera around any object using a circular curve path (Method 2).",
    "category": "Animation",
}

DEFAULT_TARGET_HEIGHT = 4.1


# --- PROPERTY GROUP ---
class CameraOrbitProperties(PropertyGroup):

    target_type: EnumProperty(
        name="Target Mode",
        items=[
            ('CHARACTER', "Character (Eyes)", "Focus on character eyes at 4.1m"),
            ('OBJECT',    "Object (Center)",  "Focus on object origin at 0m"),
        ],
        default='CHARACTER',
    )

    radius: FloatProperty(
        name="Radius",
        description="Distance from target to camera",
        default=5.0,
        min=0.1, max=200.0, step=10, precision=2,
    )

    start_angle: FloatProperty(
        name="Start Angle (°)",
        description="Starting position on the circle (0° = behind, 90° = right, 180° = front, 270° = left)",
        default=0.0,
        min=-360.0, max=360.0, step=10, precision=1,
    )

    end_angle: FloatProperty(
        name="End Angle (°)",
        description="Ending position on the circle",
        default=360.0,
        min=-360.0, max=360.0, step=10, precision=1,
    )

    duration: FloatProperty(
        name="Duration (Frames)",
        description="How many frames the orbit takes",
        default=90,
        min=1, max=2000, step=1, precision=0,
    )

    camera_height: FloatProperty(
        name="Camera Height Offset",
        description=(
            "Vertical offset of the orbit circle relative to the look-at point.\n"
            "  0 = level orbit (same height as eyes/center)\n"
            " +ve = orbit above the target (high angle, looking down)\n"
            " -ve = orbit below the target (low angle, looking up)"
        ),
        default=0.0,
        min=-50.0, max=50.0, step=10, precision=2,
    )


# --- OPERATOR ---
class CAMERA_OT_orbit(Operator):
    bl_idname = "camera.orbit_shot"
    bl_label = "Execute Orbit"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Create a circular orbit path around the selected object and animate the camera along it"

    def execute(self, context):
        target_obj = context.view_layer.objects.active
        camera    = context.scene.camera
        props     = context.scene.camera_orbit

        if not target_obj:
            self.report({'ERROR'}, "Select the object to orbit around.")
            return {'CANCELLED'}
        if not camera:
            self.report({'ERROR'}, "No scene camera set. Set one in Scene Properties.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------ #
        # 1. Create / update the look-at empty (the point the camera faces)
        # ------------------------------------------------------------------ #
        target_height = DEFAULT_TARGET_HEIGHT if props.target_type == 'CHARACTER' else 0.0
        look_name = f"{target_obj.name}_Orbit_LookAt"
        look_at = bpy.data.objects.get(look_name)

        if look_at is None:
            bpy.ops.object.empty_add(type='SPHERE', location=(0, 0, 0))
            look_at = context.active_object
            look_at.name = look_name
            look_at.empty_display_size = 0.15
            look_at.hide_select = True
            look_at.hide_viewport = True

        if look_at.parent != target_obj:
            look_at.parent = target_obj
            look_at.matrix_parent_inverse.identity()

        look_at.location = (0.0, 0.0, target_height)

        # Force a depsgraph update so matrix_world is current
        context.view_layer.update()
        look_world = look_at.matrix_world.translation.copy()

        # ------------------------------------------------------------------ #
        # 2. Remove any old orbit curve and build a fresh circle
        #    (Always rebuild so radius / position stay correct)
        # ------------------------------------------------------------------ #
        path_name = f"{target_obj.name}_Orbit_Path"

        # Remove the old object AND its underlying curve data block so Blender
        # can't accidentally reuse or re-link the stale data on the next run.
        old_path = bpy.data.objects.get(path_name)
        if old_path is not None:
            old_curve_data = old_path.data  # grab reference before removing object
            bpy.data.objects.remove(old_path, do_unlink=True)
            # Now remove the orphaned curve data block itself
            if old_curve_data and old_curve_data.users == 0:
                bpy.data.curves.remove(old_curve_data)

        # Purge any other zero-user data left behind from previous runs
        bpy.ops.outliner.orphans_purge(do_recursive=True)

        # Add a Bezier Circle at the look-at world position, raised by camera_height
        orbit_center = look_world.copy()
        orbit_center.z += props.camera_height

        bpy.ops.curve.primitive_bezier_circle_add(
            radius=props.radius,
            location=orbit_center,
        )
        path_obj = context.active_object
        path_obj.name = path_name

        # Make it a proper animation path
        path_obj.data.use_path        = True
        path_obj.data.path_duration   = int(props.duration)

        # Hide it – it's infrastructure, not art
        path_obj.hide_select   = True
        path_obj.hide_viewport = True
        path_obj.hide_render   = True

        # ------------------------------------------------------------------ #
        # 3. Prepare the camera (clear previous orbit state)
        # ------------------------------------------------------------------ #
        # Remove all constraints
        for c in list(camera.constraints):
            camera.constraints.remove(c)

        # Clear all animation data (location, rotation, old constraint keys)
        if camera.animation_data:
            camera.animation_data_clear()

        # Detach from any parent
        camera.parent = None
        camera.matrix_parent_inverse.identity()

        # Camera's own location must be (0,0,0) so Follow Path places it
        # exactly on the curve without any extra offset
        camera.location      = (0.0, 0.0, 0.0)
        camera.rotation_euler = (0.0, 0.0, 0.0)

        # ------------------------------------------------------------------ #
        # 4. Follow Path constraint  →  rides the circle
        # ------------------------------------------------------------------ #
        follow = camera.constraints.new(type='FOLLOW_PATH')
        follow.target             = path_obj
        follow.use_fixed_location = True   # lets us drive position with offset_factor
        follow.use_curve_follow   = False  # rotation handled by Track To below

        # Map degree angles → 0..1 offset_factor
        start_offset = props.start_angle / 360.0
        end_offset   = props.end_angle   / 360.0

        context.scene.frame_end     = int(props.duration)
        context.scene.frame_current = 1

        # Keyframe through the camera object using the full data-path
        # (direct constraint.keyframe_insert is unreliable in script context)
        kf_path = f'constraints["{follow.name}"].offset_factor'

        follow.offset_factor = start_offset
        camera.keyframe_insert(data_path=kf_path, frame=1)

        follow.offset_factor = end_offset
        camera.keyframe_insert(data_path=kf_path, frame=int(props.duration))

        # ------------------------------------------------------------------ #
        # 5. Track To constraint  →  always faces look-at empty
        # ------------------------------------------------------------------ #
        track = camera.constraints.new(type='TRACK_TO')
        track.target     = look_at
        track.track_axis = 'TRACK_NEGATIVE_Z'
        track.up_axis    = 'UP_Y'

        # ------------------------------------------------------------------ #
        # 6. Set interpolation to Linear (constant orbit speed)
        # ------------------------------------------------------------------ #
        if camera.animation_data and camera.animation_data.action:
            for fcu in camera.animation_data.action.fcurves:
                for kp in fcu.keyframe_points:
                    kp.interpolation = 'LINEAR'

        # Return playhead to frame 1
        context.scene.frame_current = 1

        self.report(
            {'INFO'},
            f"Orbit created around '{target_obj.name}'  "
            f"{props.start_angle}°→{props.end_angle}°  "
            f"radius={props.radius}m  height={props.camera_height:+.1f}m  "
            f"frames={int(props.duration)}"
        )
        return {'FINISHED'}


# --- UI PANEL ---
class VIEW3D_PT_camera_orbit(Panel):
    bl_label      = "Camera Orbit"
    bl_idname     = "VIEW3D_PT_CAMERA_ORBIT"
    bl_space_type = 'VIEW_3D'
    bl_region_type= 'UI'
    bl_category   = 'Camera'

    def draw(self, context):
        layout = self.layout
        props  = context.scene.camera_orbit

        target_obj = context.view_layer.objects.active
        camera     = context.scene.camera

        # Status indicators
        row = layout.row()
        row.label(
            text=f"Subject: {target_obj.name}" if target_obj else "No object selected",
            icon='OBJECT_DATA' if target_obj else 'ERROR',
        )
        row = layout.row()
        row.label(
            text=f"Camera: {camera.name}" if camera else "No scene camera!",
            icon='CAMERA_DATA' if camera else 'ERROR',
        )

        layout.separator()

        # Target Mode
        box = layout.box()
        box.label(text="Focus Point:", icon='PIVOT_CURSOR')
        box.prop(props, "target_type", expand=True)

        # Orbit Parameters
        box = layout.box()
        box.label(text="Orbit Parameters:", icon='FORCE_MAGNETIC')
        col = box.column(align=True)
        col.prop(props, "radius",         text="Radius (m)")
        col.prop(props, "camera_height",  text="Height Offset (m)")
        col.prop(props, "start_angle",    text="Start Angle")
        col.prop(props, "end_angle",      text="End Angle")
        col.prop(props, "duration",       text="Frames")

        layout.separator()
        layout.operator(
            CAMERA_OT_orbit.bl_idname,
            text="Execute Orbit",
            icon='PLAY',
        )


# --- REGISTRATION ---
classes = (
    CameraOrbitProperties,
    CAMERA_OT_orbit,
    VIEW3D_PT_camera_orbit,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.camera_orbit = PointerProperty(type=CameraOrbitProperties)

def unregister():
    del bpy.types.Scene.camera_orbit
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()
