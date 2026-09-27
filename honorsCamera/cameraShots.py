import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, FloatProperty
from math import radians, sin, cos

# --- 1. ADDON METADATA ---
bl_info = {
    "name": "Cinematic Framing Tools",
    "author": "User",
    "version": (1, 4), # Rule of Thirds offset now scales with shot distance
    "blender": (4, 0, 0),
    "location": "3D Viewport > Sidebar > Camera Tab",
    "description": "Instantly set up standard cinematic shot types (CU, MS, WA) and composition (Rule of Thirds).",
    "category": "Animation",
}

# --- CONFIGURATION CONSTANTS ---
# Target Height: Eyes at 3.75m
TARGET_HEIGHT = 4.1
# This represents the height *above* the protagonist's origin (Z=0)
CAMERA_Z_OFFSET = TARGET_HEIGHT

# Composition Offset Factor (multiplied by distance for Rule of Thirds)
COMPOSITION_OFFSET_FACTOR = 0.25 

# Camera Distances and Height Offsets (relative to TARGET_HEIGHT)
SHOT_SETTINGS = {
    'ECU': {'dist': 0.5, 'height_offset': 0},
    'CU':  {'dist': 1.5, 'height_offset': 0},
    'MCU': {'dist': 2.5, 'height_offset': 0},
    'MS':  {'dist': 4.0, 'height_offset': 0},
    'WA':  {'dist': 8.0, 'height_offset': 0},
    'OVR': {'dist': 0.1, 'height_offset': 8.0}, # Directly overhead, 8m up
    'LOW': {'dist': 2.0, 'height_offset': -1.5},   # 1.5m below eye level
}

# --- UTILITY FUNCTIONS ---

def get_composition_offset(composition_type, distance):
    """Returns the X offset based on the selected composition type and camera distance."""
    offset = COMPOSITION_OFFSET_FACTOR * distance
    if composition_type == 'LEFT':
        return -offset
    elif composition_type == 'RIGHT':
        return offset
    return 0.0

def setup_target_and_constraint(protagonist, camera):
    """Creates the 3.75m target object and constrains the camera to it."""
    context = bpy.context
    
    target_name = f"{protagonist.name}_{TARGET_HEIGHT}m_Target_FRAME"
    target_object = bpy.data.objects.get(target_name)
    
    # Create target if it doesn't exist
    if target_object is None:
        bpy.ops.object.empty_add(type='SPHERE', align='WORLD', location=(0, 0, 0))
        target_object = context.active_object
        target_object.name = target_name
        target_object.empty_display_size = 0.1
        target_object.hide_select = True
        target_object.hide_viewport = True
        
    # Parent and position the target
    target_object.parent = protagonist
    target_object.location = (0, 0, CAMERA_Z_OFFSET) # Local Z position

    # Setup Camera Constraint (Make the camera always look at the target)
    for constraint in camera.constraints:
        camera.constraints.remove(constraint)

    track_to = camera.constraints.new(type='TRACK_TO')
    track_to.target = target_object
    track_to.track_axis = 'TRACK_NEGATIVE_Z'
    track_to.up_axis = 'UP_Y'
    
    return target_object


def position_camera(protagonist, camera, distance, angle_offset, x_offset, height_offset):
    """Sets the camera's location instantly, letting the Track To constraint handle rotation."""
    
    protagonist_loc = protagonist.location # Get protagonist's world location
    
    angle_rad = radians(angle_offset)
    
    # 1. Calculate RELATIVE Position (from protagonist center)
    
    # Base Position (Distance from center)
    base_x_rel = distance * sin(angle_rad)
    base_y_rel = -distance * cos(angle_rad) 
    
    # Apply Composition Offset (X-offset is applied tangential to the circle)
    offset_x_dir = cos(angle_rad) 
    offset_y_dir = sin(angle_rad) 
    
    final_x_relative = base_x_rel + (x_offset * offset_x_dir)
    final_y_relative = base_y_rel + (x_offset * offset_y_dir)
    
    # 2. Convert to WORLD Position
    final_x_world = final_x_relative + protagonist_loc.x
    final_y_world = final_y_relative + protagonist_loc.y
    final_z_world = (CAMERA_Z_OFFSET + height_offset) + protagonist_loc.z
    
    # Set Location
    camera.location = (final_x_world, final_y_world, final_z_world)
    camera.parent = None 
    
    # Clear any existing animation data
    if camera.animation_data:
        camera.animation_data_clear()


# --- 2. OPERATOR CLASS ---

class CAMERA_OT_set_framing_shot(Operator):
    bl_idname = "camera.set_framing_shot" 
    bl_label = "SET CAMERA SHOT"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        protagonist = context.view_layer.objects.active
        camera = context.scene.camera
        props = context.window_manager.camera_frame_props

        if not protagonist or not camera:
            self.report({'ERROR'}, "Select Protagonist and ensure a Scene Camera is set.")
            return {'CANCELLED'}

        # 1. Get Settings from UI properties
        settings = SHOT_SETTINGS[props.shot_type]
        distance = settings['dist']
        height_offset = settings['height_offset']
        
        x_offset = get_composition_offset(props.composition, distance)

        # 2. Setup Target and Constraint
        setup_target_and_constraint(protagonist, camera)

        # 3. Position Camera Instantly
        position_camera(protagonist, camera, distance, props.angle_offset, x_offset, height_offset)

        self.report({'INFO'}, f"{props.shot_type} set at {props.composition} composition.")
        return {'FINISHED'}


# --- 3. UI PANEL CLASS (Where the buttons live) ---
class VIEW3D_PT_framing_tools(bpy.types.Panel):
    bl_label = "Cinematic Framing Tools"
    bl_idname = "VIEW3D_PT_FRAMING_TOOLS"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Camera' 

    def draw(self, context):
        layout = self.layout
        
        protagonist = context.view_layer.objects.active
        if not protagonist:
            layout.label(text="Select a Protagonist (Mesh/Armature)", icon='INFO')
            return

        layout.label(text=f"Target: {protagonist.name}'s {TARGET_HEIGHT}m Level", icon='DOT')
        
        box = layout.box()
        
        # Shot Type Selection
        box.label(text="Shot Framing:")
        box.prop(context.window_manager.camera_frame_props, "shot_type", text="")
        
        # Composition Selection
        box.label(text="Composition:")
        box.prop(context.window_manager.camera_frame_props, "composition", text="")
        
        # Angle Slider
        box.label(text="Starting Angle:")
        box.prop(context.window_manager.camera_frame_props, "angle_offset", text="")
        
        # Execution Button
        layout.separator()
        layout.operator(CAMERA_OT_set_framing_shot.bl_idname)
        

# --- 4. REGISTRATION FUNCTIONS ---

# Create a Pointer Property Group to store the settings selected in the UI
class FrameProperties(bpy.types.PropertyGroup):
    shot_type: EnumProperty(
        name="Shot Type",
        items=[
            ('ECU', "Extreme Close Up (ECU)", "Focus on detail, e.g., eyes."),
            ('CU', "Close Up (CU)", "Head and shoulders."),
            ('MCU', "Medium Close Up (MCU)", "Waist up."),
            ('MS', "Medium Shot (MS)", "Knees up, full body context."),
            ('WA', "Wide Angle (WA)", "Full environment context."),
            ('LOW', "Low Angle", "Camera positioned low, looking up."),
            ('OVR', "Overhead Shot", "Camera positioned above, looking down."),
        ],
        default='MS',
    )
    composition: EnumProperty(
        name="Composition",
        items=[
            ('CENTER', "Center", "Protagonist centered in the frame."),
            ('LEFT', "Left Third", "Protagonist aligned with the left vertical Rule of Thirds line."),
            ('RIGHT', "Right Third", "Protagonist aligned with the right vertical Rule of Thirds line."),
        ],
        default='CENTER',
    )
    angle_offset: FloatProperty(
        name="Angle (Deg)",
        default=0.0,
        min=-360.0,
        max=360.0,
        step=50,
    )


classes = (
    CAMERA_OT_set_framing_shot,
    VIEW3D_PT_framing_tools,
    FrameProperties, # Register property group
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls) 
    
    # Register the property group to the window manager
    bpy.types.WindowManager.camera_frame_props = bpy.props.PointerProperty(type=FrameProperties)


def unregister():
    # Unregister the property group from the window manager
    del bpy.types.WindowManager.camera_frame_props
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 

if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register() 