"""Dress the staged CC0 Quaternius base, retaining its humanoid skin and rig."""
import bpy,bmesh,json,math,argparse,sys,shutil
from pathlib import Path
from mathutils import Vector

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--source',default=str(root/'blender/rider/source/Superhero_Male_FullBody.gltf'));p.add_argument('--output',default=str(root/'assets/driver/rider.glb'))
args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
source=Path(args.source);stage=root/'artifacts/rider-source';stage.mkdir(parents=True,exist_ok=True)
# Strip unused image references in a staged copy; the kit has two missing eye/
# eyebrow normal-map filenames. The outfit uses our own opaque materials.
g=json.loads(source.read_text());g.pop('images',None);g.pop('textures',None)
for m in g['materials']:m.clear();m.update({'pbrMetallicRoughness':{'baseColorFactor':[.7,.3,.08,1],'metallicFactor':0,'roughnessFactor':.8}})
for buffer in g['buffers']:
 src=source.parent/buffer['uri'];dst=stage/src.name
 if src.resolve()!=dst.resolve():shutil.copy2(src,dst)
 buffer['uri']=dst.name
clean=stage/'rider-input.gltf';clean.write_text(json.dumps(g))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(clean))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');body=bpy.data.objects['SuperHero_Male']
for o in list(bpy.data.objects):
 if o.type=='MESH' and o!=body:bpy.data.objects.remove(o,do_unlink=True)

def material(name,color,rough=.7,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 s=m.node_tree.nodes.get('Principled BSDF');s.inputs['Base Color'].default_value=(*color,1);s.inputs['Roughness'].default_value=rough;s.inputs['Metallic'].default_value=metal
 return m
orange=material('Dunes fire suit',(.95,.075,.008));dark=material('Boots gloves and panels',(.025,.032,.034));ivory=material('Helmet shell and suit stripes',(.88,.84,.69),.3);visor=material('Opaque smoked visor',(.012,.026,.038),.16,.35)
body.data.materials.clear()
for m in [orange,dark,ivory]:body.data.materials.append(m)
bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.z>1.585],context='VERTS');bm.to_mesh(body.data);bm.free()
for face in body.data.polygons:
 center=sum((body.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
 face.material_index=1 if center.z<.22 or abs(center.x)>.71 else 0
 face.use_smooth=True

parts=[]
def bind(obj,name,mat):
 obj.name=name;obj.data.materials.clear();obj.data.materials.append(mat)
 bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);obj.select_set(False)
 vg=obj.vertex_groups.new(name='Head');vg.add(list(range(len(obj.data.vertices))),1,'REPLACE')
 mod=obj.modifiers.new('Rider rig','ARMATURE');mod.object=arm;parts.append(obj)
 for poly in obj.data.polygons:poly.use_smooth=True
 return obj
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,location=(0,-.008,1.70));shell=bpy.context.object;shell.scale=(.119,.143,.151);bind(shell,'Full face helmet',ivory)

def band(name,lat0,lat1,yaw0,yaw1,radius,mat):
 vs=[];fs=[];rows=6;cols=36
 for j in range(rows+1):
  lat=lat0+(lat1-lat0)*j/rows
  for i in range(cols+1):
   yaw=yaw0+(yaw1-yaw0)*i/cols;vs.append((.119*radius*math.cos(lat)*math.sin(yaw),-.008-.143*radius*math.cos(lat)*math.cos(yaw),1.70+.151*radius*math.sin(lat)))
 for j in range(rows):
  for i in range(cols):
   a=j*(cols+1)+i;fs.append((a,a+1,a+cols+2,a+cols+1))
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update();ob=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(ob);bind(ob,name,mat)
band('Visor seal',-.35,.37,-1.24,1.24,1.014,dark)
band('Visor',-.28,.30,-1.17,1.17,1.023,visor)
band('Helmet orange band',.45,.57,-math.pi,math.pi,1.014,orange)
band('Chin vent',-.68,-.52,-.45,.45,1.017,dark)
# Join the dressed mesh into one skin, retaining distinct opaque materials.
bpy.ops.object.select_all(action='DESELECT');body.select_set(True)
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=body;bpy.ops.object.join();body.name='Dunes_Rider'
for a in bpy.data.actions:bpy.data.actions.remove(a)
arm.animation_data_clear();arm['source']='Quaternius Universal Base Characters, CC0';arm['helmet_center']=[0,1.70,.008]
out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);body.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(stage/'dunes-rider.blend'))
bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',use_selection=True,export_animations=False,export_yup=True,export_extras=True)
print('RIDER_EXPORT',json.dumps({'file':str(out),'vertices':len(body.data.vertices),'triangles':sum(len(p.vertices)-2 for p in body.data.polygons),'bones':len(arm.data.bones),'bytes':out.stat().st_size}))
