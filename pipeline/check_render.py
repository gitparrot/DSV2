"""Blender script: render a rigged skin .blend for a visual check (rest front/side, then a test pose).

    blender -b ds2_export/isaac_engineer_3p.blend -P pipeline/check_render.py -- <out prefix> [--size 2.4] [--center 1.0]

Renders only the meshes in the scene's main collection (the skin), not the host_ref collection. The test pose
rotates the left arm, left forearm, right arm, head, upper spine and left leg of a j_* skeleton (whatever of those
exists), which is how the mod moves the skin in game.
Writes <out>_front.png, <out>_side.png, <out>_posed.png.
"""
import math, sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
size = float(argv[argv.index("--size") + 1]) if "--size" in argv else 2.6
center = Vector((0, 0, float(argv[argv.index("--center") + 1]) if "--center" in argv else 1.05))

sc = bpy.context.scene
skin = [o for o in sc.collection.objects if o.type == "MESH"]
for coll in bpy.data.collections:
    for o in coll.objects:
        o.hide_render = True
for o in skin:
    o.hide_render = False
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 800, 900
world = bpy.data.worlds.new("check")
world.color = (0.35, 0.35, 0.38)
sc.world = world
cam = bpy.data.objects.new("check_cam", bpy.data.cameras.new("check_cam"))
sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.data.ortho_scale = size
sun = bpy.data.objects.new("check_sun", bpy.data.lights.new("check_sun", "SUN"))
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), 0, math.radians(200))
sun.data.energy = 3
sc.camera = cam


def shoot(tag, yaw):
    cam.location = center + Vector((math.sin(yaw) * 5, math.cos(yaw) * 5, 0))
    cam.rotation_euler = (math.radians(90), 0, math.radians(180) - yaw)
    sc.render.filepath = f"{out}_{tag}.png"
    bpy.ops.render.render(write_still=True)


shoot("front", 0)
shoot("side", math.radians(90))
arm = next((o for o in sc.collection.objects if o.type == "ARMATURE"), None)
pose = {"j_leftarm": (0, 0, -60), "j_leftforearm": (0, 0, -70), "j_rightarm": (40, 0, 30),
        "j_head": (25, 0, 30), "j_spine1": (0, 0, 20), "j_leftupleg": (0, 0, -40), "j_leftleg": (0, 0, 60)}
if arm:
    for name, rot in pose.items():
        pb = arm.pose.bones.get(name)
        if pb:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = [math.radians(a) for a in rot]
    bpy.context.view_layer.update()
    shoot("posed", math.radians(30))
