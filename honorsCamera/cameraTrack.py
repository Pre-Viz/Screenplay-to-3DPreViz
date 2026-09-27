import bpy
import mathutils
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import FloatProperty, EnumProperty, PointerProperty
from math import radians, sin, cos

bl_info = {
    "name": "Camera Track (Follow)",
    "author": "User",
    "version": (1, 2),
    "blender": (4, 0, 0),
    "location": "3D Viewport > Sidebar > Camera Tab",
    "description": (
        "Parent the camera to a character/object so it follows all movement. "
        "Uses Method 3: place camera in position, parent with Keep Transformation, "
        "add Track To so it always faces the subject."
    ),
    "category": "Animation",
}

DEFAULT_TARGET_HEIGHT = 4.1


# --- PROPERTY GROUP ---
class CameraTrackProperties(PropertyGroup):

    target_type: EnumProperty(
        name="Target Mode",
        items=[
            ('CHARACTER', "Character (Eyes)", "Face character eyes at 4.1m"),
            ('OBJECT',    "Object (Center)",  "Face object origin at 0m"),
        ],
        default='CHARACTER',
    )

    depth: FloatProperty(
        name="Depth",
        description="Distance behind/in front of the subject",
        default=5.0,
        min=0.1, max=200.0, step=10, precision=2,
    )

    height: FloatProperty(
        name="Height Offset",
        description=(
            "Camera height relative to the look-at point.\n"
            "  0 = same level as eyes/center\n"
            " +ve = above (high angle)\n"
            " -ve = below (low angle)"
        ),
        default=0.0,
        min=-20.0, max=20.0, step=10, precision=2,
    )

    lateral: FloatProperty(
        name="Lateral Offset",
        description="Side offset (+ = camera to the right of subject, - = left)",
        default=0.0,
        min=-50.0, max=50.0, step=10, precision=2,
    )

    angle: FloatProperty(
        name="Angle (°)",
        description=(
            "Horizontal angle around the subject.\n"
            "  0° = in front (direction character faces)\n"
            " 90° = right side   180° = behind   270° = left side"
        ),
        default=0.0,
        min=-360.0, max=360.0, step=10, precision=1,
    )


# --- OPERATOR ---
class CAMERA_OT_track(Operator):
    bl_idname     = "camera.track_follow"
    bl_label      = "Attach Camera to Subject"
    bl_options    = {'REGISTER', 'UNDO'}
    bl_description = (
        "Place the camera at the configured offset, then parent it to the subject "
        "so it follows every movement automatically (Method 3)"
    )

    def execute(self, context):
        subject = context.view_layer.objects.active
        camera  = context.scene.camera
        props   = context.scene.camera_track

        if not subject:
            self.report({'ERROR'}, "Select the subject object first.")
            return {'CANCELLED'}
        if not camera:
            self.report({'ERROR'}, "No scene camera set.")
            return {'CANCELLED'}
        if camera == subject:
            self.report({'ERROR'}, "The active object is the camera itself — select the subject instead.")
            return {'CANCELLED'}

        target_height = DEFAULT_TARGET_HEIGHT if props.target_type == 'CHARACTER' else 0.0

        # -------------------------------------------------------------- #
        # 1. Create / update the look-at empty
        #    (parented to subject, sits at eye / object-center height)
        # -------------------------------------------------------------- #
        look_name = f"{subject.name}_Track_LookAt"
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

        context.view_layer.update()

        # -------------------------------------------------------------- #
        # 2. Calculate camera world position relative to subject
        #
        #    We use the subject's matrix_world ROTATION (not world axes)
        #    so the camera is placed relative to whichever direction the
        #    character is actually facing on their path.
        #
        #    Horizontal placement (XY) is in the subject's local space:
        #      angle=0   → directly in front (local +Y = forward)
        #      angle=90  → right side
        #      angle=180 → directly behind
        #      angle=270 → left side
        #
        #    Height is added in pure world Z AFTER the XY transform,
        #    keeping it fully independent — changing height never
        #    changes the horizontal depth or framing.
        # -------------------------------------------------------------- #
        angle_rad = radians(props.angle)

        # Polar placement in subject's local horizontal plane:
        # depth = radius, angle = rotation from "in front"
        cam_local_x = props.depth * sin(angle_rad) + props.lateral * cos(angle_rad)
        cam_local_y = props.depth * cos(angle_rad) - props.lateral * sin(angle_rad)

        # Strip scale from the subject's matrix so camera distance
        # isn't multiplied by the character's scale (e.g. 2.5×)
        subj_pos = subject.matrix_world.translation
        subj_rot = subject.matrix_world.to_3x3().normalized()

        # Rotate local XY offset into world space using subject's orientation
        local_horiz = mathutils.Vector((cam_local_x, cam_local_y, 0.0))
        world_horiz = subj_rot @ local_horiz

        # World Z: subject feet + look-at height + independent height offset
        cam_world_x = subj_pos.x + world_horiz.x
        cam_world_y = subj_pos.y + world_horiz.y
        cam_world_z = subj_pos.z + target_height + props.height

        # -------------------------------------------------------------- #
        # 3. Clean up camera — remove previous track state
        # -------------------------------------------------------------- #
        for c in list(camera.constraints):
            camera.constraints.remove(c)

        if camera.animation_data:
            camera.animation_data_clear()

        # Detach from any existing parent before repositioning
        camera.parent = None
        camera.matrix_parent_inverse.identity()

        # -------------------------------------------------------------- #
        # 4. Place camera at calculated world position
        # -------------------------------------------------------------- #
        camera.location       = (cam_world_x, cam_world_y, cam_world_z)
        camera.rotation_euler = (0.0, 0.0, 0.0)

        # -------------------------------------------------------------- #
        # 5. Add Track To constraint so camera always faces the subject
        # -------------------------------------------------------------- #
        track = camera.constraints.new(type='TRACK_TO')
        track.target     = look_at
        track.track_axis = 'TRACK_NEGATIVE_Z'
        track.up_axis    = 'UP_Y'

        # -------------------------------------------------------------- #
        # 6. Parent camera to subject — Keep Transformation
        #    (Method 3: Ctrl+P → Keep Transformation)
        #
        #    Correct Python equivalent:
        #      a) Force a depsgraph update so matrix_world is fully evaluated
        #         (this is critical when the subject uses Follow Path / NLA)
        #      b) Store the camera's evaluated world matrix
        #      c) Set the parent
        #      d) Re-assign matrix_world — Blender recalculates matrix_local
        #         and matrix_parent_inverse automatically so the camera stays
        #         at the exact world position we placed it, while inheriting
        #         ALL future movement from the subject's path/animation.
        # -------------------------------------------------------------- #
        context.view_layer.update()
        world_matrix_before = camera.matrix_world.copy()

        camera.parent = subject

        # Force another update so Blender knows the new parent relationship
        context.view_layer.update()

        # Re-apply world matrix — this is the "Keep Transformation" step.
        # Works correctly whether the subject is driven by keyframes,
        # a Follow Path constraint, NLA strips, or any combination.
        camera.matrix_world = world_matrix_before

        context.view_layer.update()

        self.report(
            {'INFO'},
            f"Camera attached to '{subject.name}' — "
            f"depth={props.depth}m  height={props.height:+.1f}m  "
            f"lateral={props.lateral:+.1f}m  angle={props.angle}°"
        )
        return {'FINISHED'}


class CAMERA_OT_track_detach(Operator):
    bl_idname     = "camera.track_detach"
    bl_label      = "Detach Camera"
    bl_options    = {'REGISTER', 'UNDO'}
    bl_description = "Remove the parent relationship and constraints, leaving the camera free"

    def execute(self, context):
        camera = context.scene.camera
        if not camera:
            self.report({'ERROR'}, "No scene camera set.")
            return {'CANCELLED'}

        # Store world position so camera doesn't jump
        context.view_layer.update()
        world_mat = camera.matrix_world.copy()

        camera.parent = None
        camera.matrix_world = world_mat

        for c in list(camera.constraints):
            camera.constraints.remove(c)

        self.report({'INFO'}, "Camera detached and constraints removed.")
        return {'FINISHED'}


# --- UI PANEL ---
class VIEW3D_PT_camera_track(Panel):
    bl_label       = "Camera Track (Follow)"
    bl_idname      = "VIEW3D_PT_CAMERA_TRACK"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Camera'

    def draw(self, context):
        layout  = self.layout
        props   = context.scene.camera_track
        subject = context.view_layer.objects.active
        camera  = context.scene.camera

        # Status row
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

        if camera and camera.parent:
            layout.label(
                text=f"Following: {camera.parent.name}",
                icon='LINKED',
            )

        layout.separator()

        # Show what path/animation is driving the subject
        if subject:
            path_info = None
            for c in subject.constraints:
                if c.type == 'FOLLOW_PATH' and c.target:
                    path_info = c.target.name
                    break

            info_box = layout.box()
            info_box.label(text="Subject Animation Source:", icon='ANIM')
            if path_info:
                info_box.label(text=f"Follow Path: '{path_info}'", icon='CURVE_DATA')
                info_box.label(text="Camera will ride this path too.", icon='INFO')
            elif subject.animation_data and subject.animation_data.action:
                info_box.label(text=f"Action: '{subject.animation_data.action.name}'", icon='ACTION')
                info_box.label(text="Camera will follow keyframed motion.", icon='INFO')
            else:
                info_box.label(text="No animation detected yet.", icon='QUESTION')
                info_box.label(text="Camera tracks future motion once attached.", icon='INFO')

        # Focus point
        box = layout.box()
        box.label(text="Focus Point:", icon='PIVOT_CURSOR')
        box.prop(props, "target_type", expand=True)

        # Camera placement
        box = layout.box()
        box.label(text="Camera Placement:", icon='CAMERA_DATA')
        col = box.column(align=True)
        col.prop(props, "depth",   text="Depth (m)")
        col.prop(props, "height",  text="Height Offset (m)")
        col.prop(props, "lateral", text="Lateral Offset (m)")
        col.prop(props, "angle",   text="Angle (°)")

        layout.separator()

        layout.operator(
            CAMERA_OT_track.bl_idname,
            text="Attach Camera to Subject",
            icon='LINKED',
        )
        layout.operator(
            CAMERA_OT_track_detach.bl_idname,
            text="Detach Camera",
            icon='UNLINKED',
        )


# --- REGISTRATION ---
classes = (
    CameraTrackProperties,
    CAMERA_OT_track,
    CAMERA_OT_track_detach,
    VIEW3D_PT_camera_track,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.camera_track = PointerProperty(type=CameraTrackProperties)

def unregister():
    del bpy.types.Scene.camera_track
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()
