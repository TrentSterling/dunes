"""Fixed-view inspection of the actual saved Kestrel Blender model."""
import argparse
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

args=argparse.ArgumentParser()
args.add_argument('--blend',required=True); args.add_argument('--output',required=True)
args.add_argument('--views',default='hero,side,top,rear')
opt=args.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.open_mainfile(filepath=opt.blend)
out=Path(opt.output); out.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=40
scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=1600; scene.render.resolution_y=1050; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.world=bpy.data.worlds.new('Studio world')
scene.world.color=(.18,.18,.18); scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.35,.39,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.015))
floor=bpy.context.object; floor.name='Studio_floor'
m=bpy.data.materials.new('Studio_warmgray'); m.diffuse_color=(.30,.28,.25,1); m.use_nodes=True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.30,.28,.25,1)
m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.72; floor.data.materials.append(m)
for name,loc,energy,size,color in [('Key',(4,6,14),2400,9,(1,.91,.78)),('Fill',(-10,3,8),1800,8,(.78,.88,1)),('Rim',(3,-10,12),3000,7,(1,1,1))]:
    data=bpy.data.lights.new(name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); scene.collection.objects.link(obj); obj.location=loc
    obj.rotation_euler=(Vector((0,0,2))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Inspection_camera'); camera=bpy.data.objects.new('Inspection_camera',data)
scene.collection.objects.link(camera); scene.camera=camera; data.lens=48
views={'hero':((13,20,10),(0,.3,2.0),False),'side':((23,0,4),(0,0,2.2),True),
       'top':((0,0,30),(0,0,0),True),'rear':((11,-19,8),(0,-1,2),False),
       'cockpit':((2.4,5.5,5),(0,3.5,2.6),False)}
for name in opt.views.split(','):
    pos,target,ortho=views[name]; camera.location=pos
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO' if ortho else 'PERSP'; data.ortho_scale=18 if name=='side' else 25.5
    data.lens=48 if name!='cockpit' else 52
    scene.render.filepath=str(out/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    print('[kestrel] rendered',name,flush=True)
