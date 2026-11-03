"""Kestrel subsystem builders. All aircraft shapes and details authored for Dunes."""
import math
from mathutils import Vector
import geometry as g
import jet_spec as S


def body_surface(y,a,offset=0):
    rx=g.monotone(S.STATIONS,y,1); top=g.monotone(S.STATIONS,y,2)
    bottom=g.monotone(S.STATIONS,y,3); z=g.monotone(S.STATIONS,y,4)
    c=math.cos(a)
    return ((rx+offset)*math.sin(a),y,z+((top if c>=0 else bottom)+offset)*c)


def paint_faces(obj,material,predicate):
    """Paint the existing skin instead of layering a second coincident surface."""
    index=len(obj.data.materials); obj.data.materials.append(material)
    for face in obj.data.polygons:
        p=sum((obj.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
        if predicate(p): face.material_index=index


def conform_fuselage_text(obj,side):
    g.apply_transform(obj)
    for v in obj.data.vertices:
        x,y,z=v.co; rx=g.monotone(S.STATIONS,y,1); cz=g.monotone(S.STATIONS,y,4)
        rz=g.monotone(S.STATIONS,y,2 if z>=cz else 3)
        v.co.x=side*(rx*math.sqrt(max(.05,1-((z-cz)/rz)**2))+.008)


def conform_wing_text(obj,rows,side):
    g.apply_transform(obj)
    for v in obj.data.vertices:
        x,y,z=v.co; span=abs(x)
        lead=g.lerp_rows(rows,span,1); trail=g.lerp_rows(rows,span,2)
        u=max(0,min(1,(lead-y)/(lead-trail)))
        v.co.z=g.wing_point(rows,span,u,side,True,.008)[2]


def build_fuselage():
    rows=[]
    for i in range(183):
        y=7.6-(7.6+6.87)*i/182
        rows.append((y,*[g.monotone(S.STATIONS,y,c) for c in range(1,5)]))
    # A material boundary at the radome station, rather than a seam hidden by paint.
    nose=[r for r in rows if r[0]>=5.5]
    body=[nose[-1]]+[r for r in rows if r[0]<5.5]
    g.shell('Radome',nose,72,g.M['nose'])
    skin=g.shell('Airframe_skin',body,72,g.M['body'])
    # The outer inlet is welded into the belly. Boolean intersections produce
    # continuous edges; deleting whole quads produced the visible sawtooth seam.
    intake=g.shell('Intake_union',S.INTAKE_OUTER,96,g.M['under'],'_Cutters')
    g.boolean(skin,intake,'UNION')
    duct=[(y,w-.052,t-.052,b-.052,z) for y,w,t,b,z in S.INTAKE]
    duct=[(duct[0][0]+.12,*duct[0][1:])]+duct
    g.boolean(skin,g.shell('Intake_bore',duct,96,g.M['duct'],'_Cutters'),'DIFFERENCE')
    cockpit=[]
    for i in range(65):
        y=2.10+3.04*i/64; w=g.monotone(S.CANOPY,y,1)
        cockpit.append((y+S.COCKPIT_OFFSET[1],w,2,.40,
                        g.monotone(S.CANOPY_BASE,y,1)+S.COCKPIT_OFFSET[2]))
    g.boolean(skin,g.shell('Cockpit_aperture',cockpit,64,g.M['cockpit'],'_Cutters'),'DIFFERENCE')
    # Recessed dorsal hatches and deliberately broken fuselage panel rings.
    for y in [5.48,-1.4,-3.3,-4.9,-6.4]:
        g.curve('Circumferential_panel', [body_surface(y,.85+4.58*i/88,.003) for i in range(89)],.0025)
    for side in [-1,1]:
        for a in [.95,1.65,2.30]:
            g.curve('Longitudinal_seam',[body_surface(1.0-7.3*i/55,side*a,.004) for i in range(56)],.0025)
        # Six separated service fasteners at each of the engine service panels.
        for y in [-1.42,-3.32,-4.92]:
            for a in [.94,1.18,1.42,1.66,1.90,2.14]:
                p=body_surface(y+.045,side*a,.014)
                g.add(g.sphere('Flush_fastener',.010,p,g.M['steel'],segs=8,rings=4))
        # Curved shoulder skins, tangent toward the body and flattened at the
        # swept edge. They replace the visibly detached triangular flat plate.
        plan=[(-3.5,1.12,2.13),(-2.7,1.53,2.13),(-.15,1.57,2.15),
              (1.2,1.16,2.22),(2.7,.76,2.37),(3.9,.47,2.43)]
        verts=[]; faces=[]; ny=72; nx=16
        for lower in [False,True]:
            for j in range(ny+1):
                y=-3.5+7.4*j/ny
                rx=g.monotone(S.STATIONS,y,1)
                outside=g.monotone(plan,y,1); edge_z=g.monotone(plan,y,2)
                inside=min(rx*.58,outside*.84)
                center=g.monotone(S.STATIONS,y,4); rt=g.monotone(S.STATIONS,y,2)
                body_z=center+rt*math.sqrt(1-(inside/rx)**2)-.035
                for k in range(nx+1):
                    u=k/nx; x=inside+(outside-inside)*u
                    z=edge_z+(body_z-edge_z)*(1-u)**2
                    if lower: z-=.025+.06*math.sin(math.pi*u)
                    verts.append((side*x,y,z))
        layer=(ny+1)*(nx+1)
        for off in [0,layer]:
            for j in range(ny):
                for k in range(nx):
                    a=off+j*(nx+1)+k; faces.append((a,a+1,a+nx+2,a+nx+1))
        boundary=list(range(nx+1))+[j*(nx+1)+nx for j in range(1,ny+1)]
        boundary+=list(range(ny*(nx+1)+nx-1,ny*(nx+1)-1,-1))
        boundary+=[j*(nx+1) for j in range(ny-1,0,-1)]
        for a,b in zip(boundary,boundary[1:]+boundary[:1]): faces.append((a,b,b+layer,a+layer))
        g.add(g.mesh('Blended_wing_shoulder',verts,faces,g.M['body']))
        # Raked canopy sill joins to the actual fuselage section at each station.
        rim=[]
        for i in range(46):
            y=2.16+2.92*i/45; w=g.monotone(S.CANOPY,y,1)
            rim.append((side*w,y+S.COCKPIT_OFFSET[1],g.monotone(S.CANOPY_BASE,y,1)+S.COCKPIT_OFFSET[2]-.01))
        g.curve('Canopy_sill',rim,.018,g.M['edge'])
        for a,b in zip(rim,rim[1:]):
            feet=[]
            for x,y,z in [b,a]:
                rx=g.monotone(S.STATIONS,y,1); angle=math.asin(min(.98,abs(x)/rx))
                feet.append(body_surface(y,side*angle,.003))
            g.plate('Sill_fillet',[a,b,*feet],.012,g.M['body'])
        # Small dorsal identification panels. Text is real geometry and exports without font files.
        conform_fuselage_text(g.label('DUNES', (side*.625,-3.8,2.42),.16,g.M['white'],right=(0,side,0),up=(0,0,1)),side)
        conform_fuselage_text(g.label('KF-01', (side*.58,4.67,2.39),.11,g.M['white'],right=(0,side,0),up=(0,0,1)),side)
        for y in [4.95,4.70,4.45]:
            g.between('AOA_vane',(side*.55,y,2.38),(side*.69,y-.045,2.38),.009,g.M['steel'],'Fuselage')
        # Dorsal cooling vents, aligned to the skin rather than floating in a box.
        for j in range(8):
            y=-2.0-j*.095
            g.curve('Engine_vent',[body_surface(y,side*(.41+k*.006),.009) for k in range(36)],.012,g.M['dark'])
    g.plate('Dorsal_antenna',[(0,-1.2,2.81),(0,-1.38,3.04),(0,-1.62,2.96),(0,-1.60,2.80)],.025,g.M['edge'])
    g.between('Pitot_probe',(0,7.58,1.98),(0,7.85,1.98),.009,g.M['steel'],'Sensors')


def build_intake():
    # The exterior belongs to the welded fuselage. This subsystem contains the
    # separate dark lining, lip, splitter and recessed compressor.
    outer=S.INTAKE
    n=64; verts=[]
    for inner in (True,):
        for y,rx,rt,rb,z in outer:
            for k in range(n):
                a=g.TAU*k/n; s=.054
                verts.append(((rx-s)*math.sin(a),y,z+((rt-s if math.cos(a)>=0 else rb-s)*math.cos(a))))
    length=len(outer); layer=length*n; faces=[]
    for off in (0,):
        for j in range(length-1):
            for k in range(n): faces.append((off+j*n+k,off+j*n+(k+1)%n,off+(j+1)*n+(k+1)%n,off+(j+1)*n+k))
    obj=g.mesh('Intake_lining',verts,faces,g.M['duct'])
    g.add(obj,'Intake')
    dy=S.INTAKE_OFFSET_Y
    lip=[(.525*math.sin(g.TAU*k/80),4.36+dy,1.79+(.165 if math.cos(g.TAU*k/80)>=0 else .335)*math.cos(g.TAU*k/80)) for k in range(81)]
    g.curve('Rolled_intake_lip',lip,.026,g.M['steel'],'Intake')
    fan=g.cylinder('Intake_depth',.53,.035,(0,.50+dy,1.85),(90,0,0),g.M['dark'],segments=64)
    fan.scale.y=.68
    g.add(fan,'Intake')
    for j in range(22):
        a=g.TAU*j/22
        pts=[]
        for r,da in [(.12,0),(.49,.14),(.50,.25),(.14,.28)]:
            pts.append((r*math.sin(a+da),.54+dy,1.85+.68*r*math.cos(a+da)))
        g.plate('Compressor_blade',pts,.006,g.M['titanium'],'Intake',axis=(0,1,0))
    g.add(g.sphere('Compressor_hub',.13,(0,.57+dy,1.85),g.M['steel'],scale=(1,.6,1)),'Intake')
    # Boundary-layer splitter above the inlet mouth.
    g.plate('Intake_splitter',[(-.47,4.37+dy,2.01),(.47,4.37+dy,2.01),(.58,3.40+dy,2.10),(-.58,3.40+dy,2.10)],.027,g.M['edge'],'Intake')


def build_wings(nodes):
    for side,tag in [(-1,'L'),(1,'R')]:
        main='Wing_'+tag
        nodes[main]=g.group(main,explode=(side*2.2,0,.1))
        skin=g.wing('Wing_fixed',S.WING,side,.62,4.78,0,.725,main)
        paint_faces(skin,g.M['orange'],lambda p:abs(p.x)>4.48)
        g.wing('Wing_root_aft',S.WING,side,.62,1.33,.725,1,main)
        flap='Flaperon_'+tag
        p0=Vector(g.wing_point(S.WING,1.35,.735,side,True)); p1=Vector(g.wing_point(S.WING,4.78,.735,side,True))
        nodes[flap]=g.group(flap,tuple(p0),tuple((p1-p0).normalized()),-24,explode=(side*2.2,-.8,.15))
        g.wing('Flaperon',S.WING,side,1.35,4.78,.738,1,flap)
        # Separately colored narrow leading strip, orange outer panel, and physical seams.
        for x in [1.65,2.65,3.6,4.40]:
            g.curve('Wing_panel_seam',[g.wing_point(S.WING,x,.09+.60*k/28,side,True,.007) for k in range(29)],.0038,g.M['seam'],main)
        for u in [.10,.70]:
            g.curve('Wing_span_seam',[g.wing_point(S.WING,.85+3.88*k/55,u,side,True,.006) for k in range(56)],.0035,g.M['seam'],main)
        # Small flush white and dark-orange recognition bars laid on the actual upper surface.
        for start,material in [(4.27,g.M['white']),(4.35,g.M['edge'])]:
            pts=[g.wing_point(S.WING,x,u,side,True,.012) for x,u in [(start,.09),(start+.04,.09),(start+.04,.67),(start,.67)]]
            g.plate('Recognition_stripe',pts,.003,material,main)
        p=g.wing_point(S.WING,2.5,.39,side,True,.014)
        conform_wing_text(g.label('DUNES',p,.29,g.M['white'],right=(side,0,0),up=(0,side,0),group_name=main),S.WING,side)
        for x in [1.0,1.18,1.36]:
            p=g.wing_point(S.WING,x,.56,side,True,.012)
            conform_wing_text(g.label('NO STEP',p,.047,g.M['ink'],group_name=main),S.WING,side)
        tail='Stabilator_'+tag
        origin=(side*.62,-5.55,2.04)
        nodes[tail]=g.group(tail,origin,(1,0,0),20,explode=(side*1.7,-1,.2))
        g.wing('Stabilator',S.TAIL,side,.55,2.80,0,1,tail)
        for x in [1.05,1.8,2.55]:
            g.curve('Tail_seam',[g.wing_point(S.TAIL,x,.08+.82*k/30,side,True,.006) for k in range(31)],.0035,g.M['seam'],tail)
        # Wingtip instrumentation pods with separate rails and navigation lights.
        pod='TipPod_'+tag
        nodes[pod]=g.group(pod,explode=(side*2.8,0,0))
        x=side*4.80
        g.add(g.box('Tip_rail',(.13,1.45,.12),(x,-2.2,2.20),material=g.M['edge'],bevel=.025),pod)
        sections=[(-.83,.004,.004,.004,2.25),(-1.02,.06,.06,.06,2.25),(-1.28,.092,.092,.092,2.25),
                  (-2.73,.092,.092,.092,2.25),(-3.0,.067,.067,.067,2.25),(-3.10,.01,.01,.01,2.25)]
        obj=g.shell('Instrumentation_pod',sections,32,g.M['under'],pod)
        for v in obj.data.vertices: v.co.x+=x
        g.ring('Pod_band',(x,-1.55,2.25),.094,.012,g.M['orange'],pod)
        g.add(g.sphere('Navigation_light',.046,(x,-2.87,2.32),g.M['red'] if side<0 else g.M['green'],scale=(1,1.5,.7)),pod)


def build_fin(nodes):
    rows=[(2.60,-3.10,-6.75,0,.085),(3.0,-3.8,-6.72,0,.075),
          (4.4,-4.85,-6.58,0,.06),(4.8,-5.15,-6.50,0,.045)]
    nodes['Fin']=g.group('Fin',explode=(0,-.3,1.9))
    skin=g.wing('Vertical_fin',rows,1,2.60,4.80,0,.745,'Fin',vertical=True)
    paint_faces(skin,g.M['orange'],lambda p:p.z>4.54)
    nodes['Rudder']=g.group('Rudder',(0,-6.27,2.70),(0,-.08,.997),25,explode=(0,-1.1,2.0))
    g.wing('Rudder',rows,1,2.72,4.80,.76,1,'Rudder',vertical=True)
    for side in [-1,1]:
        x=side*.082
        labels=[g.label('01',(x,-5.53,3.48),.53,g.M['white'],right=(0,side,0),up=(0,0,1),group_name='Fin'),
                g.label('KESTREL',(side*.057,-5.55,4.16),.112,g.M['white'],right=(0,side,0),up=(0,0,1),group_name='Fin')]
        for label in labels:
            g.apply_transform(label)
            for v in label.data.vertices:
                x,y,z=v.co; lead=g.lerp_rows(rows,z,1); trailing=g.lerp_rows(rows,z,2)
                chord=lead-trailing; u=max(0,min(1,(lead-y)/chord))
                thickness=g.airfoil(u,g.lerp_rows(rows,z,4))*chord
                v.co.x=.006*chord*math.sin(math.pi*u)+side*(thickness+.006)
        for z in [3.03,4.44]:
            g.curve('Fin_panel',[(side*.05,-5.0,z),(side*.06,-6.38,z)],.004,g.M['seam'],'Fin')
        # Twin ventral stabilizing fins, canted slightly outwards.
        g.plate('Ventral_fin',[(side*.49,-4.53,1.70),(side*.62,-5.60,1.62),
                             (side*.88,-6.42,.98),(side*.88,-5.56,.90)],.045,g.M['panels'])


def build_cockpit(nodes):
    nodes['Cockpit']=g.group('Cockpit',explode=(0,0,1.25))
    c='Cockpit'
    g.add(g.box('Cockpit_tub',(.80,2.18,.12),(0,3.56,2.33),material=g.M['dark'],bevel=.05),c)
    for side in [-1,1]:
        g.add(g.box('Side_console',(.19,1.78,.28),(side*.32,3.55,2.49),material=g.M['cockpit'],bevel=.038),c)
        for j in range(11):
            y=2.87+j*.12
            g.add(g.box('Console_panel',(.14,.103,.016),(side*.32,y,2.64),material=g.M['edge'],bevel=.006),c)
            for k in [-1,1]:
                g.add(g.cylinder('Toggle_base',.015,.018,(side*.32+k*.032,y,2.66),material=g.M['steel'],segments=8),c)
                g.between('Toggle',(side*.32+k*.032,y,2.67),(side*.32+k*.032,y+.012,2.71),.006,g.M['white'],c)
    g.add(g.box('Seat_shell',(.47,.49,.64),(0,2.84,2.69),rot=(12,0,0),material=g.M['edge'],bevel=.07,segments=4),c)
    g.add(g.box('Seat_cushion',(.40,.53,.12),(0,3.02,2.49),material=g.M['seat'],bevel=.045,segments=4),c)
    g.add(g.box('Seat_back',(.39,.11,.57),(0,2.95,2.77),rot=(12,0,0),material=g.M['seat'],bevel=.04,segments=4),c)
    g.add(g.box('Head_rest',(.26,.20,.24),(0,2.78,3.10),rot=(12,0,0),material=g.M['seat'],bevel=.065,segments=4),c)
    for side in [-1,1]:
        g.curve('Seat_harness',[(side*.13,2.91,3.00),(side*.15,3.025,2.77),(side*.12,3.19,2.55)],.022,g.M['harness'],c)
        for y in [2.85,3.02,3.19]:
            g.curve('Seat_stitch',[(side*.18,y,2.56),(side*.06,y,2.56)],.003,g.M['seam'],c)
        g.between('Ejection_rail',(side*.22,2.64,2.39),(side*.22,2.65,3.17),.022,g.M['steel'],c)
    g.curve('Ejection_handle',[(-.09,3.25,2.55),(-.10,3.36,2.57),(0,3.39,2.57),(.10,3.36,2.57),(.09,3.25,2.55)],.014,g.M['yellow'],c)
    # Instrument fascia is angled back toward the pilot, with modeled bevels and button rows.
    g.add(g.box('Instrument_panel',(.80,.15,.43),(0,4.19,2.67),rot=(12,0,0),material=g.M['cockpit'],bevel=.035),c)
    g.add(g.box('Glareshield',(.74,.39,.075),(0,4.19,2.92),material=g.M['dark'],bevel=.045),c)
    for side in [-1,1]:
        x=side*.24
        g.add(g.box('MFD_frame',(.26,.034,.24),(x,4.09,2.70),material=g.M['edge'],bevel=.014),c)
        g.add(g.box('MFD_glass',(.215,.009,.187),(x,4.065,2.70),material=g.M['screen'],bevel=.006),c)
        for j in range(5):
            for s in [-1,1]:
                g.add(g.box('MFD_key',(.020,.016,.014),(x-.10+j*.05,4.048,2.70+s*.108),material=g.M['white'],bevel=.003),c)
        # Luminous vector symbology on the actual MFD plane.
        for j in range(4):
            z=2.64+j*.035
            g.curve('MFD_readout',[(x-.073,4.057,z),(x+.073*(1-j*.12),4.057,z)],.0022,g.M['phosphor'],c)
        g.label('NAV' if side<0 else 'ENG',(x,4.05,2.75),.033,g.M['phosphor'],right=(1,0,0),up=(0,0,1),group_name=c)
    for z in [2.55,2.65,2.75]:
        g.add(g.cylinder('Standby_dial',.049,.025,(0,4.07,z),(90,0,0),g.M['steel'],segments=24),c)
        g.add(g.cylinder('Dial_face',.041,.029,(0,4.06,z),(90,0,0),g.M['dark'],segments=24),c)
        g.between('Dial_needle',(0,4.04,z),(.023,4.04,z+.013),.0025,g.M['white'],c)
    g.add(g.box('HUD_base',(.18,.24,.055),(0,4.26,2.98),material=g.M['edge'],bevel=.02),c)
    for side in [-1,1]:
        g.between('HUD_support',(side*.10,4.25,2.97),(side*.10,4.40,3.05),.012,g.M['edge'],c)
    g.plate('HUD_combiner',[(-.14,4.40,2.99),(.14,4.40,2.99),(.13,4.48,3.10),(-.13,4.48,3.10)],.006,g.M['hudglass'],c,axis=(0,1,0))
    g.between('Sidestick',(.31,3.61,2.64),(.31,3.61,2.81),.025,g.M['dark'],c)
    g.add(g.sphere('Stick_grip',.038,(.31,3.61,2.83),g.M['dark'],scale=(1,1,1.6)),c)
    g.between('Throttle',(-.31,3.45,2.65),(-.31,3.47,2.74),.024,g.M['steel'],c)
    g.add(g.box('Throttle_grip',(.11,.06,.04),(-.31,3.47,2.77),material=g.M['dark'],bevel=.015),c)
    # Canopy is a longitudinal surface, not a stretched sphere.
    nodes['Canopy']=g.group('Canopy',S.CANOPY_HINGE,(1,0,0),57,explode=(0,0,2.3))
    verts=[]; faces=[]; ny=64; na=40
    for j in range(ny+1):
        y=2.10+3.04*j/ny; w=g.monotone(S.CANOPY,y,1); h=g.monotone(S.CANOPY,y,2)
        for k in range(na+1):
            a=math.pi*k/na
            verts.append((w*math.cos(a),y,g.monotone(S.CANOPY_BASE,y,1)+h*math.sin(a)))
    for j in range(ny):
        for k in range(na):
            a=j*(na+1)+k; faces.append((a,a+1,a+na+2,a+na+1))
    g.add(g.mesh('Canopy_glass',verts,faces,g.M['glass']),'Canopy')
    for side in [-1,1]:
        g.curve('Canopy_rail',[(side*g.monotone(S.CANOPY,2.1+3.04*j/64,1),2.1+3.04*j/64,g.monotone(S.CANOPY_BASE,2.1+3.04*j/64,1)+.004) for j in range(65)],.016,g.M['edge'],'Canopy')
    for y in [2.24,4.96]:
        w=g.monotone(S.CANOPY,y,1); h=g.monotone(S.CANOPY,y,2)
        g.curve('Canopy_bow',[(w*math.cos(math.pi*j/40),y,g.monotone(S.CANOPY_BASE,y,1)+h*math.sin(math.pi*j/40)) for j in range(41)],.015,g.M['edge'],'Canopy')
    for side in [-1,1]:
        g.between('Canopy_lift_actuator',(side*.35,2.37,2.54),(side*.35,2.42,2.76),.018,g.M['steel'],'Canopy')


def wheel(center,radius,width,name,group):
    x,y,z=center
    # A closed revolved tire profile, with rounded shoulders and real rim opening.
    profile=[(radius*.50,-width*.44),(radius*.73,-width*.53),(radius*.91,-width*.45),
             (radius*.99,-width*.29),(radius,0),(radius*.99,width*.29),
             (radius*.91,width*.45),(radius*.73,width*.53),(radius*.50,width*.44),
             (radius*.50,-width*.44)]
    g.add(g.lathe(name+'_tire',profile,g.M['rubber'],64,loc=center,rot=(0,90,0)),group)
    for side in [-1,1]:
        face=x+side*width*.44
        g.add(g.cylinder('Wheel_hub',radius*.53,.035,(face,y,z),(0,90,0),g.M['gear'],segments=32),group)
        g.add(g.cylinder('Hub_cap',radius*.19,.043,(face+side*.025,y,z),(0,90,0),g.M['steel'],segments=24),group)
        for j in range(8):
            a=g.TAU*j/8
            g.add(g.cylinder('Hub_recess',radius*.071,.039,(face+side*.021,y+radius*.35*math.sin(a),z+radius*.35*math.cos(a)),(0,90,0),g.M['dark'],segments=12),group)
    for t in [-.22,0,.22]:
        g.ring('Tread_groove',(x+width*t,y,z),radius+.001,.003,g.M['seam'],group,axis='X')


def build_gear(nodes):
    for side,tag in [(-1,'L'),(1,'R')]:
        name='GearMain_'+tag; pivot=(side*.58,-.65,1.65)
        # A compound forward/inboard fold places the wheel inside the fuselage bay.
        # Solve the hinge from the deployed leg vector and the intended stowed vector.
        deployed=Vector((side*.96,-.28,-1.26))
        stowed=Vector((-side*.38,1.50,.30))
        axis=deployed.cross(stowed).normalized()
        nodes[name]=g.group(name,pivot,tuple(axis),math.degrees(deployed.angle(stowed)),explode=(side*.7,0,-.3))
        knee=(side*1.14,-.83,.92); hub=(side*1.54,-.93,.39)
        g.between('Main_upper_strut',pivot,knee,.075,g.M['gear'],name)
        g.between('Oleo_chrome',knee,(side*1.43,-.91,.47),.044,g.M['steel'],name)
        g.between('Main_axle',(side*1.38,-.93,.39),(side*1.69,-.93,.39),.054,g.M['steel'],name)
        g.between('Drag_brace',(side*.60,.0,1.48),(side*1.05,-.82,.94),.034,g.M['gear'],name)
        g.between('Torque_link',(side*1.12,-.78,.85),(side*1.31,-.69,.66),.025,g.M['gear'],name)
        g.between('Torque_link',(side*1.31,-.69,.66),(side*1.40,-.85,.50),.025,g.M['gear'],name)
        g.curve('Brake_hose',[pivot,(side*.98,-.72,1.02),(side*1.21,-.77,.78),(side*1.40,-.90,.41)],.011,g.M['rubber'],name)
        wheel(hub,.39,.22,'MainWheel_'+tag,name)
        door='GearDoorMain_'+tag
        nodes[door]=g.group(door,(side*.67,-.65,1.49),(0,1,0),side*102,explode=(side*.8,0,-.2))
        # Shown open at rest; the viewer closes the doors after the legs retract.
        g.add(g.box('Main_gear_door',(.045,1.11,.59),(side*.82,-.68,1.10),rot=(0,-side*12,0),material=g.M['under'],bevel=.035),door)
        for y in [-1.04,-.38]:
            g.between('Door_rib',(side*.79,y,.86),(side*.87,y,1.33),.015,g.M['gear'],door)
    name='GearNose'; pivot=(0,3.46,1.61)
    # Compound fold into the shoulder bay beside the duct, behind the cockpit.
    deployed=Vector((0,.42,-1.33)); stowed=Vector((.52,-1.10,.68))
    axis=deployed.cross(stowed).normalized()
    nodes[name]=g.group(name,pivot,tuple(axis),math.degrees(deployed.angle(stowed)),explode=(0,1,-.2))
    g.between('Nose_upper_strut',pivot,(0,3.68,.77),.057,g.M['gear'],name)
    g.between('Nose_oleo',(0,3.68,.83),(0,3.81,.38),.035,g.M['steel'],name)
    for side in [-1,1]:
        g.between('Nose_fork',(side*.14,3.78,.52),(side*.14,3.88,.28),.030,g.M['gear'],name)
    g.between('Nose_drag_brace',(0,2.94,1.48),(0,3.59,.94),.028,g.M['gear'],name)
    wheel((0,3.88,.28),.28,.17,'NoseWheel',name)
    g.add(g.box('Landing_lamp',(.16,.07,.12),(0,3.73,.92),material=g.M['gear'],bevel=.02),name)
    g.add(g.sphere('Lamp_lens',.058,(0,3.78,.92),g.M['white'],scale=(1,.25,.7)),name)
    nodes['GearDoorNose']=g.group('GearDoorNose',(0,3.5,1.48),(1,0,0),102,explode=(0,1,-.4))
    g.add(g.box('Nose_door',(.39,.055,.72),(0,3.31,1.02),rot=(-12,0,0),material=g.M['under'],bevel=.025),'GearDoorNose')
    g.label('01',(0,3.273,1.06),.17,g.M['ink'],right=(-1,0,0),up=(0,0,1),group_name='GearDoorNose')


def build_engine(nodes):
    name='Engine'; nodes[name]=g.group(name,explode=(0,-2,0))
    z=S.ENGINE_Z
    for y,r,thick,mat in [(-6.55,.57,.027,g.M['steel']),(-6.79,.575,.038,g.M['titanium']),(-6.88,.57,.017,g.M['dark'])]:
        g.ring('Nozzle_collar',(0,y,z),r,thick,mat,name)
    # Deep nozzle liner stays open at the lip. The recessed turbine prevents a flat black disc.
    verts=[]; faces=[]; n=80
    for y,r in [(-7.50,.43),(-7.22,.47),(-6.65,.50),(-6.15,.46)]:
        for j in range(n):
            a=g.TAU*j/n; verts.append((r*math.sin(a),y,z+r*math.cos(a)))
    for k in range(3):
        for j in range(n): faces.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
    g.add(g.mesh('Nozzle_liner',verts,faces,g.M['liner']),name)
    g.add(g.cylinder('Turbine_depth',.45,.02,(0,-6.12,z),(90,0,0),g.M['dark'],segments=64),name)
    for r in [.13,.30,.40]: g.ring('Flameholder',(0,-6.30,z),r,.015,g.M['burner'],name)
    for j in range(18):
        a=g.TAU*j/18
        g.between('Liner_rib',(.46*math.sin(a),-6.20,z+.46*math.cos(a)),(.435*math.sin(a),-7.46,z+.435*math.cos(a)),.007,g.M['titanium'],name)
    for j in range(16):
        a=g.TAU*j/16; petal='NozzlePetal_%02d'%j
        origin=(.56*math.sin(a),-6.85,z+.56*math.cos(a))
        axis=(math.cos(a),0,-math.sin(a))
        nodes[petal]=g.group(petal,origin,axis,8,explode=(0,-2,0))
        verts=[]
        for y,r in [(-6.86,.57),(-7.09,.55),(-7.40,.46),(-7.58,.435)]:
            for k in range(7):
                angle=a+(.5-k/6)*g.TAU/16*.94
                verts.append((r*math.sin(angle),y,z+r*math.cos(angle)))
        faces=[]
        for iy in range(3):
            for ix in range(6):
                q=iy*7+ix; faces.append((q,q+1,q+8,q+7))
        g.add(g.mesh('Exhaust_petal',verts,faces,g.M['titanium'] if j%3 else g.M['steel']),petal)
        for da in [-.12,.12]:
            g.curve('Petal_stiffener',[(r*math.sin(a+da),y,z+r*math.cos(a+da)) for y,r in [(-6.91,.575),(-7.09,.56),(-7.40,.47),(-7.55,.445)]],.007,g.M['dark'],petal)
        g.add(g.sphere('Petal_hinge',.022,origin,g.M['steel'],segs=12,rings=6),petal)
