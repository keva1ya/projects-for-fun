# Author: Kevalya
bl_info = {
    "name": "Snow Generator",
    "author": "Kevalya",
    "description": "Generate snow mesh",
    "version": (1, 0),
    "blender": (4, 3, 0),
    "location": "View 3D > Properties Panel",
    "category": "Object",
}


# Libraries
import math
import os
import random
import time

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Vector


# Panel
class REAL_PT_snow(Panel):
    bl_space_type = "VIEW_3D"
    bl_context = "objectmode"
    bl_region_type = "UI"
    bl_label = "Snow"
    bl_category = "Snow Generator"

    def draw(self, context):
        scn = context.scene
        settings = scn.snow
        layout = self.layout

        # Main settings
        col = layout.column(align=True)
        col.prop(settings, "coverage", slider=True)
        col.prop(settings, "height")
        col.prop(settings, "vertices")

        # Geometry settings
        box = layout.box()
        box.label(text="Geometry Settings")
        col = box.column(align=True)
        col.prop(settings, "resolution")
        col.prop(settings, "particle_scale")
        col.prop(settings, "decimate_ratio")

        # Material settings
        box = layout.box()
        box.label(text="Material Settings")
        col = box.column(align=True)
        col.prop(settings, "subsurface_weight")
        col.prop(settings, "roughness")
        col.prop(settings, "displacement_strength")

        # Buttons
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("snow.create", text="Add Snow", icon="FREEZE")

        # Add reset settings button
        row = layout.row(align=True)
        row.operator("snow.reset_settings", text="Reset Settings", icon="LOOP_BACK")


class SNOW_OT_Create(Operator):
    bl_idname = "snow.create"
    bl_label = "Create Snow"
    bl_description = "Create snow"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context) -> bool:
        return bool(context.selected_objects)

    def execute(self, context):
        coverage = context.scene.snow.coverage
        height = context.scene.snow.height
        vertices = context.scene.snow.vertices
        resolution = context.scene.snow.resolution
        particle_scale = context.scene.snow.particle_scale
        decimate_ratio = context.scene.snow.decimate_ratio
        subsurface_weight = context.scene.snow.subsurface_weight
        roughness = context.scene.snow.roughness
        displacement_strength = context.scene.snow.displacement_strength

        # Get a list of selected objects, except non-mesh objects
        input_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        snow_list = []
        # Start UI progress bar
        length = len(input_objects)
        context.window_manager.progress_begin(0, 10)
        timer = 0
        for obj in input_objects:
            # Timer
            context.window_manager.progress_update(timer)
            # Duplicate mesh
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            context.view_layer.objects.active = obj
            object_eval = obj.evaluated_get(context.view_layer.depsgraph)
            mesh_eval = bpy.data.meshes.new_from_object(object_eval)
            snow_object = bpy.data.objects.new("Snow", mesh_eval)
            snow_object.matrix_world = obj.matrix_world
            context.collection.objects.link(snow_object)
            bpy.ops.object.select_all(action="DESELECT")
            context.view_layer.objects.active = snow_object
            snow_object.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            bm_orig = bmesh.from_edit_mesh(snow_object.data)
            bm_copy = bm_orig.copy()
            bm_copy.transform(obj.matrix_world)
            bm_copy.normal_update()
            remove_unwanted_faces(vertices, bm_copy, snow_object)
            ballobj = setup_metaball_snow(context, height, snow_object)
            context.view_layer.objects.active = snow_object
            surface_area = calculate_surface_area(snow_object)
            snow = generate_snow_particles(
                context, surface_area, height, coverage, snow_object, ballobj
            )
            apply_snow_modifiers(snow, decimate_ratio)
            # Place inside collection
            context.view_layer.active_layer_collection = (
                context.view_layer.layer_collection
            )
            if "Snow" not in context.scene.collection.children:
                coll = bpy.data.collections.new("Snow")
                context.scene.collection.children.link(coll)
            else:
                coll = bpy.data.collections["Snow"]
            coll.objects.link(snow)
            context.view_layer.layer_collection.collection.objects.unlink(snow)
            create_snow_material(snow)
            # Parent with object
            snow.parent = obj
            snow.matrix_parent_inverse = obj.matrix_world.inverted()
            # Add snow to list
            snow_list.append(snow)
            # Update progress bar
            timer += 0.1 / length
        # Select created snow meshes
        for s in snow_list:
            s.select_set(True)
        # End progress bar
        context.window_manager.progress_end()

        return {"FINISHED"}


def apply_snow_modifiers(snow, decimate_ratio):
    bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
    # Decimate the mesh to get rid of some visual artifacts
    snow.modifiers.new("Decimate", "DECIMATE")
    snow.modifiers["Decimate"].ratio = decimate_ratio
    snow.modifiers.new("Subdiv", "SUBSURF")
    snow.modifiers["Subdiv"].render_levels = 1
    snow.modifiers["Subdiv"].quality = 1


def generate_snow_particles(
    context,
    surface_area: float,
    height: float,
    coverage: float,
    snow_object: bpy.types.Object,
    ballobj: bpy.types.Object,
):
    # Approximate the number of particles to be emitted
    number = int(surface_area * 50 * (height**-2) * ((coverage / 100) ** 2))
    bpy.ops.object.particle_system_add()
    particles = snow_object.particle_systems[0]
    psettings = particles.settings
    psettings.type = "HAIR"
    psettings.render_type = "OBJECT"
    # Generate random number for seed
    random_seed = random.randint(0, 1000)
    particles.seed = random_seed
    # Set particles object
    psettings.particle_size = height
    psettings.instance_object = ballobj
    psettings.count = number
    # Convert particles to mesh
    bpy.ops.object.select_all(action="DESELECT")
    context.view_layer.objects.active = ballobj
    ballobj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    snow = bpy.context.active_object
    particle_scale = context.scene.snow.particle_scale
    snow.scale = [particle_scale, particle_scale, particle_scale]
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
    bpy.ops.object.select_all(action="DESELECT")
    snow_object.select_set(True)
    bpy.ops.object.delete()
    snow.select_set(True)
    return snow


def setup_metaball_snow(
    context, height: float, snow_object: bpy.types.Object
) -> bpy.types.Object:
    ball_name = "SnowBall"
    ball = bpy.data.metaballs.new(ball_name)
    ballobj = bpy.data.objects.new(ball_name, ball)
    bpy.context.scene.collection.objects.link(ballobj)
    # Use resolution from settings instead of a fixed formula
    resolution = context.scene.snow.resolution
    # Apply resolution to the metaball
    ball.resolution = resolution
    ball.threshold = 1.3
    element = ball.elements.new()
    element.radius = 1.5
    element.stiffness = 0.75
    ballobj.scale = [0.09, 0.09, 0.09]
    return ballobj


def remove_unwanted_faces(vertices, bm_copy, snow_object: bpy.types.Object):
    # Find upper faces
    if vertices:
        selected_faces = set(face.index for face in bm_copy.faces if face.select)
    # Based on a certain angle, find all faces not pointing up
    down_faces = set(
        face.index
        for face in bm_copy.faces
        if Vector((0, 0, -1.0)).angle(face.normal, 4.0) < (math.pi / 2.0 + 0.5)
    )
    bm_copy.free()
    bpy.ops.mesh.select_all(action="DESELECT")
    # Select upper faces
    mesh = bmesh.from_edit_mesh(snow_object.data)
    for face in mesh.faces:
        if vertices:
            if face.index not in selected_faces:
                face.select = True
        if face.index in down_faces:
            face.select = True
    # Delete unnecessary faces
    faces_select = [face for face in mesh.faces if face.select]
    bmesh.ops.delete(mesh, geom=faces_select, context="FACES_KEEP_BOUNDARY")
    mesh.free()
    bpy.ops.object.mode_set(mode="OBJECT")


def calculate_surface_area(obj: bpy.types.Object) -> float:
    bm_obj = bmesh.new()
    bm_obj.from_mesh(obj.data)
    bm_obj.transform(obj.matrix_world)
    area = sum(face.calc_area() for face in bm_obj.faces)
    bm_obj.free
    return area


def create_snow_material(obj: bpy.types.Object):
    mat_name = "Snow"
    # If material doesn't exist, create it
    if mat_name in bpy.data.materials:
        bpy.data.materials[mat_name].name = mat_name + ".001"
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    # Delete all nodes
    for node in nodes:
        nodes.remove(node)
    # Add nodes
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    vec_math = nodes.new("ShaderNodeVectorMath")
    com_xyz = nodes.new("ShaderNodeCombineXYZ")
    dis = nodes.new("ShaderNodeDisplacement")
    mul1 = nodes.new("ShaderNodeMath")
    add1 = nodes.new("ShaderNodeMath")
    add2 = nodes.new("ShaderNodeMath")
    mul2 = nodes.new("ShaderNodeMath")
    mul3 = nodes.new("ShaderNodeMath")
    ramp1 = nodes.new("ShaderNodeValToRGB")
    ramp2 = nodes.new("ShaderNodeValToRGB")
    ramp3 = nodes.new("ShaderNodeValToRGB")
    vor = nodes.new("ShaderNodeTexVoronoi")
    noise1 = nodes.new("ShaderNodeTexNoise")
    noise2 = nodes.new("ShaderNodeTexNoise")
    noise3 = nodes.new("ShaderNodeTexNoise")
    mapping = nodes.new("ShaderNodeMapping")
    coord = nodes.new("ShaderNodeTexCoord")

    # Node locations remain the same...
    output.location = (100, 0)
    principled.location = (-200, 500)
    vec_math.location = (-400, 400)
    com_xyz.location = (-600, 400)
    dis.location = (-200, -100)
    mul1.location = (-400, -100)
    add1.location = (-600, -100)
    add2.location = (-800, -100)
    mul2.location = (-1000, -100)
    mul3.location = (-1000, -300)
    ramp1.location = (-500, 150)
    ramp2.location = (-1300, -300)
    ramp3.location = (-1000, -500)
    vor.location = (-1500, 200)
    noise1.location = (-1500, 0)
    noise2.location = (-1500, -200)
    noise3.location = (-1500, -400)
    mapping.location = (-1700, 0)
    coord.location = (-1900, 0)

    # Updated node parameters for Blender 4.0+ compatibility
    principled.distribution = "MULTI_GGX"
    principled.subsurface_method = "RANDOM_WALK"

    # Base Color
    principled.inputs["Base Color"].default_value = (0.904, 0.904, 0.904, 1)

    # Subsurface
    subsurface_weight = bpy.context.scene.snow.subsurface_weight
    if "Subsurface" in principled.inputs:
        principled.inputs["Subsurface"].default_value = subsurface_weight
    elif "Subsurface Weight" in principled.inputs:
        principled.inputs["Subsurface Weight"].default_value = subsurface_weight

    # Subsurface Color
    if "Subsurface Color" in principled.inputs:
        principled.inputs["Subsurface Color"].default_value = (0.36, 0.46, 0.6, 1.0)

    # Subsurface Radius
    if "Subsurface Radius" in principled.inputs:
        principled.inputs["Subsurface Radius"].default_value = (0.904, 0.904, 0.904)

    # Specular
    if "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.224
    elif "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 0.224

    # Roughness
    roughness = bpy.context.scene.snow.roughness
    principled.inputs["Roughness"].default_value = roughness

    # Clearcoat
    if "Clearcoat" in principled.inputs:
        principled.inputs["Clearcoat"].default_value = 0.1

    # Rest of the node setup remains the same...
    vec_math.operation = "MULTIPLY"
    vec_math.inputs[1].default_value = (0.5, 0.5, 0.5)
    com_xyz.inputs[0].default_value = 0.36
    com_xyz.inputs[1].default_value = 0.46
    com_xyz.inputs[2].default_value = 0.6
    dis.inputs[1].default_value = 0.1
    dis.inputs[2].default_value = 0.3
    mul1.operation = "MULTIPLY"
    mul1.inputs[1].default_value = 0.1
    mul2.operation = "MULTIPLY"
    mul2.inputs[1].default_value = 0.6
    mul3.operation = "MULTIPLY"
    mul3.inputs[1].default_value = 0.4
    ramp1.color_ramp.elements[0].position = 0.525
    ramp1.color_ramp.elements[1].position = 0.58
    ramp2.color_ramp.elements[0].position = 0.069
    ramp2.color_ramp.elements[1].position = 0.757
    ramp3.color_ramp.elements[0].position = 0.069
    ramp3.color_ramp.elements[1].position = 0.757
    vor.feature = "N_SPHERE_RADIUS"
    vor.inputs[2].default_value = 30
    noise1.inputs[2].default_value = 12
    noise2.inputs[2].default_value = 2
    noise2.inputs[3].default_value = 4
    noise3.inputs[2].default_value = 1
    noise3.inputs[3].default_value = 4
    mapping.inputs[3].default_value = (12, 12, 12)

    # Node links remain the same...
    link = mat.node_tree.links
    link.new(principled.outputs[0], output.inputs[0])
    link.new(vec_math.outputs[0], principled.inputs[2])
    link.new(com_xyz.outputs[0], vec_math.inputs[0])
    link.new(dis.outputs[0], output.inputs[2])
    link.new(mul1.outputs[0], dis.inputs[0])
    link.new(add1.outputs[0], mul1.inputs[0])
    link.new(add2.outputs[0], add1.inputs[0])
    link.new(mul2.outputs[0], add2.inputs[0])
    link.new(mul3.outputs[0], add2.inputs[1])
    link.new(ramp1.outputs[0], principled.inputs[12])
    link.new(ramp2.outputs[0], mul3.inputs[0])
    link.new(ramp3.outputs[0], add1.inputs[1])
    link.new(vor.outputs[4], ramp1.inputs[0])
    link.new(noise1.outputs[0], mul2.inputs[0])
    link.new(noise2.outputs[0], ramp2.inputs[0])
    link.new(noise3.outputs[0], ramp3.inputs[0])
    link.new(mapping.outputs[0], vor.inputs[0])
    link.new(mapping.outputs[0], noise1.inputs[0])
    link.new(mapping.outputs[0], noise2.inputs[0])
    link.new(mapping.outputs[0], noise3.inputs[0])
    link.new(coord.outputs[3], mapping.inputs[0])

    # Set displacement and add material
    mat.displacement_method = "DISPLACEMENT"
    obj.data.materials.append(mat)

    # Displacement
    displacement_strength = bpy.context.scene.snow.displacement_strength
    dis.inputs[1].default_value = displacement_strength


# Add a new operator to reset settings
class SNOW_OT_ResetSettings(Operator):
    bl_idname = "snow.reset_settings"
    bl_label = "Reset Settings"
    bl_description = "Reset all snow settings to default values"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.snow

        # Reset all settings to default values
        settings.coverage = 100
        settings.height = 0.3
        settings.vertices = False
        settings.resolution = 0.7
        settings.particle_scale = 0.09
        settings.decimate_ratio = 0.5
        settings.subsurface_weight = 1.0
        settings.roughness = 0.1
        settings.displacement_strength = 0.1

        return {"FINISHED"}


# Properties
class SnowSettings(PropertyGroup):
    coverage: IntProperty(
        name="Coverage",
        description="Percentage of the object to be covered with snow",
        default=100,
        min=0,
        max=100,
        subtype="PERCENTAGE",
    )

    height: FloatProperty(
        name="Height",
        description="Height of the snow",
        default=0.3,
        step=1,
        precision=2,
        min=0.1,
        max=1,
    )

    vertices: BoolProperty(
        name="Selected Faces",
        description="Add snow only on selected faces",
        default=False,
    )

    # New settings for snow customization
    resolution: FloatProperty(
        name="Resolution",
        description="Metaball resolution (affects snow detail)",
        default=0.7,
        min=0.1,
        max=2.0,
    )

    particle_scale: FloatProperty(
        name="Particle Scale",
        description="Scale of snow particles",
        default=0.09,
        min=0.01,
        max=0.5,
        precision=3,
    )

    decimate_ratio: FloatProperty(
        name="Decimate Ratio",
        description="Ratio for mesh decimation (lower values = less vertices)",
        default=0.5,
        min=0.1,
        max=1.0,
    )

    subsurface_weight: FloatProperty(
        name="Subsurface Weight",
        description="Strength of subsurface scattering effect",
        default=1.0,
        min=0.0,
        max=1.0,
    )

    roughness: FloatProperty(
        name="Roughness",
        description="Surface roughness of snow",
        default=0.1,
        min=0.0,
        max=1.0,
    )

    displacement_strength: FloatProperty(
        name="Displacement",
        description="Strength of surface displacement",
        default=0.1,
        min=0.0,
        max=1.0,
    )


#############################################################################################
classes = (
    REAL_PT_snow,
    SNOW_OT_Create,
    SNOW_OT_ResetSettings,  # Include new class
    SnowSettings,
)

register, unregister = bpy.utils.register_classes_factory(classes)


# Register
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snow = PointerProperty(type=SnowSettings)


# Unregister
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.snow


if __name__ == "__main__":
    (register(),)
