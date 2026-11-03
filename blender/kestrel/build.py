"""Build Kestrel 01 from original parametric aircraft parts, then export GLB."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import geometry as g
import jet_spec as S
import parts


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=1
    g.M.update({
        'body':g.mat('Airframe ceramic gray',S.PALETTE['airframe'],metal=.15,rough=.48,clearcoat=.10,clearcoat_rough=.32),
        'under':g.mat('Underside light gray',S.PALETTE['underside'],metal=.2,rough=.44),
        'nose':g.mat('Radome graphite',S.PALETTE['nose'],metal=.08,rough=.53),
        'panels':g.mat('Service panels',S.PALETTE['panels'],metal=.27,rough=.41),
        'edge':g.mat('Edge charcoal',S.PALETTE['edge'],metal=.35,rough=.35),
        'orange':g.mat('Dunes vermilion',S.PALETTE['orange'],metal=.15,rough=.32,clearcoat=.25),
        'white':g.mat('Ceramic white',S.PALETTE['white'],metal=.08,rough=.37),
        'seam':g.mat('Recessed seam','#46545b',metal=.1,rough=.65),
        'ink':g.mat('Stencil ink',S.PALETTE['ink'],rough=.65),
        'steel':g.mat('Machined steel','#a7b3b9',metal=.86,rough=.27),
        'titanium':g.mat('Heat treated titanium','#686775',metal=.88,rough=.39),
        'rubber':g.mat('Tire rubber',S.PALETTE['rubber'],rough=.79),
        'dark':g.mat('Light absorbing recess','#10191c',rough=.88),
        'duct':g.mat('Intake interior','#26312f',metal=.1,rough=.72,double_sided=True),
        'gear':g.mat('Landing gear enamel','#c5cecc',metal=.38,rough=.30),
        'cockpit':g.mat('Cockpit coated metal','#293438',metal=.15,rough=.63),
        'seat':g.mat('Seat woven olive','#535c49',rough=.92),
        'harness':g.mat('Harness webbing','#a89977',rough=.84),
        'yellow':g.mat('Rescue yellow','#e3b632',rough=.52),
        'glass':g.mat('Canopy coated glass','#9aaea9',rough=.065,metal=.08,transmission=.62,alpha=.46,ior=1.46,double_sided=True),
        'hudglass':g.mat('HUD combiner','#6fb09c',rough=.1,transmission=.6,alpha=.32,double_sided=True),
        'screen':g.mat('MFD black glass','#102925',rough=.18,emit='#0b2922',emit_strength=.3),
        'phosphor':g.mat('Display phosphor','#9bbd9e',rough=.4,emit='#7fc8a1',emit_strength=.65),
        'red':g.mat('Port navigation red','#ff2214',rough=.15,emit='#ff1306',emit_strength=1.1),
        'green':g.mat('Starboard navigation green','#22f596',rough=.15,emit='#08cc72',emit_strength=1.1),
        'liner':g.mat('Nozzle liner','#302e2d',metal=.58,rough=.65,double_sided=True),
        'burner':g.mat('Flameholder glow','#66210a',metal=.35,rough=.5,emit='#b82d07',emit_strength=.15),
    })
    g.ROOT=bpy.data.objects.new('Kestrel_01',None)
    bpy.context.scene.collection.objects.link(g.ROOT)
    g.ROOT['author']='Trent / Dunes'; g.ROOT['units']='meters'; g.ROOT['design']='Original single-engine fighter'
    nodes={
        'Fuselage':g.group('Fuselage'),
        'Intake':g.group('Intake',explode=(0,1.0,-.7)),
        'Sensors':g.group('Sensors',explode=(0,1.5,0)),
    }
    for fn in [parts.build_fuselage,parts.build_intake]:
        fn(); print('[kestrel]',fn.__name__,flush=True)
    for fn in [parts.build_wings,parts.build_fin,parts.build_cockpit,parts.build_gear,parts.build_engine]:
        fn(nodes); print('[kestrel]',fn.__name__,flush=True)
    shell=bpy.data.objects['Airframe_skin']
    bm=bmesh.new(); bm.from_mesh(shell.data)
    topology={'boundaryEdges':sum(e.is_boundary for e in bm.edges),
              'nonManifoldEdges':sum(not e.is_manifold for e in bm.edges)}
    bm.free()
    if topology['nonManifoldEdges']:
        raise RuntimeError('Airframe shell has open or non-manifold intersections: '+str(topology))
    for name,node in nodes.items():
        if name in ['Canopy','Cockpit']: g.offset_group(name,node,S.COCKPIT_OFFSET)
        elif name.startswith(('Wing_','Flaperon_','TipPod_')): g.offset_group(name,node,S.WING_OFFSET)
        elif name in ['GearNose','GearDoorNose']: g.offset_group(name,node,(0,S.INTAKE_OFFSET_Y,0))
    for name,node in nodes.items(): g.assemble(name,node)
    eye=bpy.data.objects.new('PilotEye',None); bpy.context.scene.collection.objects.link(eye)
    eye.parent=g.ROOT; eye.location=Vector(S.DRIVER_EYE)+Vector(S.COCKPIT_OFFSET)
    bpy.context.view_layer.update()
    meshes=[o for o in bpy.data.objects if o.type=='MESH']
    points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    triangles=0
    for obj in meshes:
        obj.data.calc_loop_triangles(); triangles+=len(obj.data.loop_triangles)
    # Seed the editable Blender viewport with an exterior view and material shading.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active; space.shading.type='MATERIAL'
                space.region_3d.view_distance=21
                space.region_3d.view_location=(0,0,2)
                space.region_3d.view_rotation=Vector((12,18,10)).to_track_quat('Z','Y')
    bpy.ops.file.pack_all()
    blend=output/'kestrel.blend'; glb=output/'kestrel.glb'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',export_yup=True,
        export_apply=True,export_cameras=False,export_lights=False,export_animations=False,
        export_extras=True,export_materials='EXPORT',export_image_format='AUTO')
    report={'name':S.NAME,'version':'0.2.1','units':'meters','triangles':triangles,
        'airframeShellTopology':topology,
        'meshGroups':len(meshes),'materials':len(bpy.data.materials),'nodes':len(bpy.data.objects),
        'boundsBlender':{'min':list(low),'max':list(high)},
        'dimensions':{'length':high.y-low.y,'span':high.x-low.x,'height':high.z-low.z},
        'pilotEyeGltf':[eye.location.x,eye.location.z,-eye.location.y],
        'articulated':[n for n in nodes if 'hingeAxis' in nodes[n]],
        'glbBytes':glb.stat().st_size,'glbSha256':hashlib.sha256(glb.read_bytes()).hexdigest(),
        'sourceSha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))},
        'source':'Original Dunes aircraft geometry, Glamis generic modeling primitives (Unlicense)',
        'reference':'https://viperoneone.com/notes/jets/ (explanatory guidance only; no code or assets copied)'}
    (output/'kestrel.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
