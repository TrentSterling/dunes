"""Original aircraft geometry, grouping and pivot helpers. No Viper source used.

Generic primitives/materials are reused from Glamis' Unlicense common.py.
The airframe surface generation and articulation are authored for Dunes.
"""
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector, Matrix

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE.parent / 'trx_pro'))
from common import mat, box, cylinder, tube, lathe, sphere, apply_transform, join

TAU = 2 * math.pi
GROUPS = {}
ROOT = None
M = {}


def mesh(name, verts, faces, material, smooth=True):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    bm = bmesh.new(); bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data); bm.free()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    if material:
        data.materials.append(material)
    for polygon in data.polygons:
        polygon.use_smooth = smooth
    return obj


def add(obj, group='Fuselage'):
    if isinstance(obj, list):
        for item in obj: add(item, group)
        return obj
    GROUPS.setdefault(group, []).append(obj)
    return obj


def boolean(target, cutter, operation):
    """Exact surface intersection, avoiding stair-step face-centroid cutouts."""
    bpy.context.view_layer.objects.active=target
    modifier=target.modifiers.new('Continuous_'+operation,'BOOLEAN')
    modifier.operation=operation; modifier.solver='EXACT'; modifier.object=cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    for items in GROUPS.values():
        if cutter in items: items.remove(cutter)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return target


def offset_group(name, node, offset):
    vector=Vector(offset)
    for obj in GROUPS.get(name,[]): obj.location+=vector
    # Bake object positions before assemble converts vertices into pivot space.
    for obj in GROUPS.get(name,[]): apply_transform(obj)
    node.location+=vector


def group(name, origin=(0, 0, 0), axis=None, angle=0, explode=(0, 0, 0)):
    node = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(node)
    node.parent = ROOT
    node.location = origin
    node['system'] = name
    node['explode'] = (explode[0], explode[2], -explode[1])
    if axis:
        node['hingeAxis'] = (axis[0], axis[2], -axis[1])
        node['travelDegrees'] = angle
    return node


def assemble(name, node):
    # Join within an articulated subsystem, preserving its independent pivot.
    items = GROUPS.get(name, [])
    if not items: return
    obj = join(items, name + '_Mesh')
    obj.data.transform(Matrix.Translation(-node.location))
    obj.parent = node
    obj.location = (0, 0, 0)
    obj['part'] = name


def curve(name, points, radius=.006, material=None, group_name='Fuselage'):
    return add(tube(name, points, radius, material or M['seam'], sides=6, bend=0, steps=1), group_name)


def between(name, a, b, radius, material, group_name):
    return curve(name, [a, b], radius, material, group_name)


def lerp_rows(rows, x, col):
    rows = sorted(rows)
    if x <= rows[0][0]: return rows[0][col]
    if x >= rows[-1][0]: return rows[-1][col]
    for a,b in zip(rows, rows[1:]):
        if a[0] <= x <= b[0]:
            t = (x-a[0])/(b[0]-a[0])
            return a[col]*(1-t)+b[col]*t


def monotone(rows, x, col):
    """Shape-preserving cubic Hermite interpolation; no station overshoot."""
    rows = sorted(rows)
    if x <= rows[0][0]: return rows[0][col]
    if x >= rows[-1][0]: return rows[-1][col]
    xs=[r[0] for r in rows]; ys=[r[col] for r in rows]
    d=[(ys[i+1]-ys[i])/(xs[i+1]-xs[i]) for i in range(len(xs)-1)]
    slopes=[d[0]]
    for i in range(1,len(xs)-1):
        if d[i-1]*d[i] <= 0: slopes.append(0)
        else:
            hp=xs[i]-xs[i-1]; hn=xs[i+1]-xs[i]
            w1=2*hn+hp; w2=hn+2*hp
            slopes.append((w1+w2)/(w1/d[i-1]+w2/d[i]))
    slopes.append(d[-1])
    for i in range(len(xs)-1):
        if xs[i] <= x <= xs[i+1]:
            h=xs[i+1]-xs[i]; t=(x-xs[i])/h
            return ((2*t**3-3*t*t+1)*ys[i]+(t**3-2*t*t+t)*h*slopes[i]
                    +(-2*t**3+3*t*t)*ys[i+1]+(t**3-t*t)*h*slopes[i+1])


def shell(name, sections, n=64, material=None, group_name='Fuselage', cut=None):
    # sections are (y, rx, top radius, bottom radius, z), matching spec stations.
    verts=[]
    for y,rx,rt,rb,z in sections:
        for k in range(n):
            a=TAU*k/n
            verts.append((rx*math.sin(a),y,z+(rt if math.cos(a)>=0 else rb)*math.cos(a)))
    faces=[]
    for j in range(len(sections)-1):
        for k in range(n):
            face=(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k)
            p=sum((Vector(verts[v]) for v in face),Vector())/4
            if not cut or not cut(p): faces.append(face)
    faces.extend([tuple(reversed(range(n))),tuple((len(sections)-1)*n+k for k in range(n))])
    return add(mesh(name,verts,faces,material or M['body']),group_name)


def airfoil(u,t):
    return 5*t*(.2969*math.sqrt(max(0,u))-.1260*u-.3516*u*u+.2843*u**3-.1036*u**4)


def wing_point(rows,x,u,side=1,upper=True,offset=0):
    lead=lerp_rows(rows,x,1); trail=lerp_rows(rows,x,2)
    chord=lead-trail; z=lerp_rows(rows,x,3)
    thickness=airfoil(u,lerp_rows(rows,x,4))*chord
    camber=.006*chord*math.sin(math.pi*u)
    return (side*x,lead-u*chord,z+camber+(thickness if upper else -thickness)+offset)


def wing(name,rows,side,x0,x1,u0=0,u1=1,group_name='Wings',material=None,vertical=False):
    ns=max(4,round((x1-x0)*10)); nc=36
    verts=[]
    for upper in (True,False):
        for j in range(ns+1):
            x=x0+(x1-x0)*j/ns
            for k in range(nc+1):
                u=u0+(u1-u0)*(.5-.5*math.cos(math.pi*k/nc))
                p=wing_point(rows,x,u,side,upper)
                if vertical: p=(p[2],p[1],abs(p[0]))
                verts.append(p)
    layer=(ns+1)*(nc+1)
    faces=[]
    for off in (0,layer):
        for j in range(ns):
            for k in range(nc):
                a=off+j*(nc+1)+k
                faces.append((a,a+1,a+nc+2,a+nc+1))
    boundary=list(range(nc+1))+[j*(nc+1)+nc for j in range(1,ns+1)]
    boundary+=list(range(ns*(nc+1)+nc-1,ns*(nc+1)-1,-1))
    boundary += [j*(nc+1) for j in range(ns-1,0,-1)]
    for a,b in zip(boundary,boundary[1:]+boundary[:1]): faces.append((a,b,b+layer,a+layer))
    return add(mesh(name,verts,faces,material or M['body']),group_name)


def plate(name,points,thickness,material,group_name='Fuselage',axis=(0,0,1)):
    a=Vector(axis)*thickness/2
    verts=[tuple(Vector(p)+a) for p in points]+[tuple(Vector(p)-a) for p in points]
    n=len(points)
    faces=[tuple(range(n)),tuple(range(n,2*n))]
    for i in range(n): faces.append((i,(i+1)%n,(i+1)%n+n,i+n))
    return add(mesh(name,verts,faces,material,False),group_name)


def label(text,loc,size,material,right=(1,0,0),up=(0,1,0),group_name='Fuselage'):
    data=bpy.data.curves.new(text,'FONT'); data.body=text; data.size=size
    data.align_x='CENTER'; data.extrude=.0007; data.resolution_u=3
    font=Path('C:/Windows/Fonts/bahnschrift.ttf')
    if font.exists():
        try: data.font=bpy.data.fonts.load(str(font),check_existing=True)
        except RuntimeError: pass
    obj=bpy.data.objects.new('Marking_'+text,data)
    bpy.context.scene.collection.objects.link(obj)
    r=Vector(right).normalized(); u=Vector(up).normalized(); n=r.cross(u)
    obj.matrix_world=Matrix((r,u,n)).transposed().to_4x4()
    obj.location=loc
    data.materials.append(material)
    bpy.context.view_layer.objects.active=obj; obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj.select_set(False)
    return add(obj,group_name)


def ring(name,center,radius,tube_radius,material,group_name='Fuselage',axis='Y',n=64):
    c=Vector(center)
    pts=[]
    for i in range(n+1):
        a=TAU*i/n
        v=(radius*math.sin(a),0,radius*math.cos(a)) if axis=='Y' else (0,radius*math.sin(a),radius*math.cos(a))
        pts.append(c+Vector(v))
    return curve(name,pts,tube_radius,material,group_name)
