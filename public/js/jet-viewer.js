import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const $ = s => document.querySelector(s);
const canvas = $('#viewport'), stage = $('.stage');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#e5e3de');
scene.fog = new THREE.Fog('#e5e3de', 42, 100);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = .98;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
const camera = new THREE.PerspectiveCamera(35, 1, .06, 160);
const target = new THREE.Vector3(0, 2.0, 0);
let theta = 2.56, phi = 1.15, radius = 25;
let jet, metadata, selected = null, mode = 'paint', ready = false;
const nodes = new Map(), originals = new Map(), meshes = [], materials = new Set();
const desired = { gear: 1, canopy: 0, burner: 0, explode: 0, pitch: 0, roll: 0, yaw: 0 };
const current = { ...desired };
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const clay = new THREE.MeshStandardMaterial({ color: '#b5b1a8', roughness: .72, metalness: .03, side: THREE.DoubleSide });
const wire = new THREE.MeshBasicMaterial({ color: '#4f6258', wireframe: true, transparent: true, opacity: .62 });

// A local studio environment: real reflection cards filtered into a PMREM.
// No downloaded HDR or external image service is needed to inspect this model.
const studio = new THREE.Scene();
studio.background = new THREE.Color('#a7b0b3');
for (const [position, scale, color, intensity] of [
  [[-6,8,-3],[7,5,1],0xf8f5e9,4], [[7,5,2],[4,8,1],0xe7f2ff,3],
  [[0,10,5],[7,5,1],0xffffff,5], [[0,3,-10],[8,3,1],0xffeee0,2],
]) {
  const panel = new THREE.Mesh(new THREE.PlaneGeometry(1,1), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.DoubleSide }));
  panel.position.fromArray(position); panel.scale.fromArray(scale); panel.lookAt(0,2,0); studio.add(panel);
}
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(studio, .06).texture;
pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xc9d5df,0xa89983,.75));
const key = new THREE.DirectionalLight(0xfff2df,2.4);
key.position.set(8,15,-8); key.castShadow=true;
key.shadow.mapSize.set(4096,4096);
Object.assign(key.shadow.camera,{left:-12,right:12,top:12,bottom:-12,near:1,far:45});
key.shadow.normalBias=.025; key.shadow.bias=-.00015; key.shadow.radius=4;
key.target.position.set(0,1,0); scene.add(key,key.target);
const fill = new THREE.DirectionalLight(0xd4e6ff,.75); fill.position.set(-10,6,-4); scene.add(fill);
const rim = new THREE.DirectionalLight(0xffffff,1.5); rim.position.set(-3,10,10); scene.add(rim);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(220,220),new THREE.MeshStandardMaterial({color:'#c9c6be',roughness:.96,metalness:0}));
floor.rotation.x=-Math.PI/2; floor.position.y=-.018; floor.receiveShadow=true; scene.add(floor);
const grid = new THREE.GridHelper(40,40,0xa1aaa0,0xb6bcb1); grid.position.y=-.012; grid.visible=false;
grid.material.transparent=true; grid.material.opacity=.38; scene.add(grid);

const rad = THREE.MathUtils.degToRad, deltaQ = new THREE.Quaternion();
function setHinge(node, degrees) {
  const r = node.userData.rest;
  node.quaternion.copy(r.quaternion);
  if (r.axis) node.quaternion.multiply(deltaQ.setFromAxisAngle(r.axis,rad(degrees)));
}
function pose(dt=1, immediate=false) {
  const t = immediate || reducedMotion ? 1 : 1-Math.exp(-dt*9);
  for (const k of Object.keys(current)) current[k] += (desired[k]-current[k])*t;
  const retraction=1-current.gear;
  for (const [name,node] of nodes) {
    const r=node.userData.rest;
    node.position.copy(r.position).addScaledVector(r.explode,current.explode);
    let angle=0;
    if (name.startsWith('GearDoor')) {
      // Rest geometry is deployed/open. Close the doors after the legs are stowed.
      const close=THREE.MathUtils.smoothstep(retraction,.74,1);
      angle=r.travel*close;
    } else if (name.startsWith('Gear')) angle=r.travel*THREE.MathUtils.smoothstep(retraction,.06,.85);
    else if (name==='Canopy') angle=r.travel*current.canopy;
    else if (name.startsWith('Flaperon')) angle=24*current.roll*(name.endsWith('_L')?1:-1)-5*current.pitch;
    else if (name.startsWith('Stabilator')) angle=20*current.pitch;
    else if (name==='Rudder') angle=25*current.yaw;
    else if (name.startsWith('NozzlePetal')) angle=r.travel*current.burner;
    setHinge(node,angle);
  }
  for (const m of materials) {
    if (m.name==='Flameholder glow') { m.emissive.set('#d43b0b'); m.emissiveIntensity=.1+current.burner*1.6; }
    if (m.name==='Nozzle liner') { m.emissive.set('#6a1a07'); m.emissiveIntensity=current.burner*.6; }
  }
  jet?.updateMatrixWorld(true);
}

function updateCamera() {
  camera.position.set(radius*Math.sin(phi)*Math.sin(theta),radius*Math.cos(phi),radius*Math.sin(phi)*Math.cos(theta)).add(target);
  camera.lookAt(target);
}
function cameraFrom(position,aim) {
  target.fromArray(aim); const offset=new THREE.Vector3(...position).sub(target);
  radius=offset.length(); phi=Math.acos(offset.y/radius); theta=Math.atan2(offset.x,offset.z);
  updateCamera();
}
const views={
  hero:[[10.5,8,-16.2],[0,1.6,0]], side:[[23,5,0],[0,2.1,0]],
  top:[[0,27,.01],[0,0,0]], front:[[0,4.4,-25],[0,2.05,0]],
  rear:[[11,7,20],[0,2.1,1]], cockpit:[[0,3.20,-3.20],[0,2.97,-5.6]],
};
function setView(name) {
  const def=views[name]; if(!def) return;
  const pos=new THREE.Vector3(...def[0]),aim=new THREE.Vector3(...def[1]);
  if(name==='cockpit'&&metadata?.pilotEyeGltf) {
    pos.fromArray(metadata.pilotEyeGltf).add(new THREE.Vector3(0,.12,.14));
    aim.copy(pos).add(new THREE.Vector3(0,-.23,-2.4));
  }
  if(name!=='cockpit') {
    const fit=Math.max(1,1.02/camera.aspect);
    pos.sub(aim).multiplyScalar(fit).add(aim);
  }
  camera.fov=name==='cockpit'?67:35; camera.updateProjectionMatrix();
  cameraFrom(pos.toArray(),aim.toArray());
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
}
function resize() {
  const {width,height}=stage.getBoundingClientRect();
  renderer.setSize(width,height,false); camera.aspect=width/height; camera.updateProjectionMatrix();
}
new ResizeObserver(()=>{resize(); if(ready) setView($('.views .active')?.dataset.view||'hero');}).observe(stage);
resize(); setView('hero');

function setMaterial(next) {
  mode=next;
  for(const mesh of meshes) mesh.material=next==='paint'?originals.get(mesh):next==='clay'?clay:wire;
  document.querySelectorAll('[data-material]').forEach(b=>b.classList.toggle('active',b.dataset.material===next));
}
function labelValues() {
  $('#gear-value').value=desired.gear>.99?'DEPLOYED':desired.gear<.01?'STOWED':`${Math.round(desired.gear*100)}%`;
  $('#canopy-value').value=desired.canopy<.01?'CLOSED':desired.canopy>.99?'OPEN':`${Math.round(desired.canopy*100)}%`;
  $('#burner-value').value=desired.burner<.01?'IDLE':`${Math.round(desired.burner*100)}%`;
  $('#explode-value').value=`${Math.round(desired.explode*100)}%`;
  for(const [key,max] of [['pitch',20],['roll',24],['yaw',25]]) $(`#${key}-value`).value=`${Math.round(desired[key]*max)}°`;
}
function set(values, immediate=false) {
  for(const [key,value] of Object.entries(values)) {
    if(!(key in desired)) continue;
    const min=['pitch','roll','yaw'].includes(key)?-1:0;
    desired[key]=THREE.MathUtils.clamp(Number(value),min,1);
    $(`#${key}`).value=desired[key];
  }
  labelValues(); if(immediate) pose(1,true);
}
for(const key of Object.keys(desired)) $(`#${key}`).addEventListener('input',e=>set({[key]:e.target.value}));
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
document.querySelectorAll('[data-material]').forEach(b=>b.addEventListener('click',()=>setMaterial(b.dataset.material)));
$('#grid').addEventListener('change',e=>grid.visible=e.target.checked);
$('#reset').addEventListener('click',()=>{
  set({gear:1,canopy:0,burner:0,explode:0,pitch:0,roll:0,yaw:0}); setMaterial('paint'); setView('hero');
  $('#rotate').checked=false; $('#grid').checked=false; grid.visible=false; select(null);
});
$('#fullscreen').addEventListener('click',async()=>{
  try { if(document.fullscreenElement) await document.exitFullscreen(); else await $('#app').requestFullscreen(); }
  catch { $('#part-name').textContent='Fullscreen is unavailable in this browser.'; }
});

// Mouse, pen and touch orbit controls with two-finger zoom/pan; no global input capture.
const pointers=new Map(); let start=null, moved=0;
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('pointerdown',e=>{
  canvas.setPointerCapture(e.pointerId); pointers.set(e.pointerId,[e.clientX,e.clientY]);
  start={x:e.clientX,y:e.clientY,button:e.button}; moved=0;
});
canvas.addEventListener('pointermove',e=>{
  if(!pointers.has(e.pointerId)) return;
  const prev=pointers.get(e.pointerId),dx=e.clientX-prev[0],dy=e.clientY-prev[1];
  moved+=Math.abs(dx)+Math.abs(dy);
  if(pointers.size===2) {
    const other=[...pointers.entries()].find(([id])=>id!==e.pointerId)[1];
    const before=Math.hypot(prev[0]-other[0],prev[1]-other[1]);
    const after=Math.hypot(e.clientX-other[0],e.clientY-other[1]);
    if(after>1) radius=THREE.MathUtils.clamp(radius*before/after,.45,70);
  } else if(start?.button===2||e.shiftKey) {
    const right=new THREE.Vector3().setFromMatrixColumn(camera.matrix,0);
    const up=new THREE.Vector3().setFromMatrixColumn(camera.matrix,1);
    target.addScaledVector(right,-dx*radius*.001).addScaledVector(up,dy*radius*.001);
  } else {
    theta-=dx*.006; phi=THREE.MathUtils.clamp(phi-dy*.005,.02,Math.PI-.03);
  }
  pointers.set(e.pointerId,[e.clientX,e.clientY]); updateCamera();
});
canvas.addEventListener('pointerup',e=>{
  if(moved<6&&start?.button===0) pick(e.clientX,e.clientY);
  pointers.delete(e.pointerId); start=null;
});
canvas.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);start=null;});
canvas.addEventListener('wheel',e=>{e.preventDefault();radius=THREE.MathUtils.clamp(radius*Math.exp(e.deltaY*.001),.45,70);updateCamera();},{passive:false});
canvas.addEventListener('keydown',e=>{
  if(e.key==='Home'){setView('hero');e.preventDefault();}
  if(e.key==='+'||e.key==='='){radius*=.9;updateCamera();e.preventDefault();}
  if(e.key==='-'){radius*=1.1;updateCamera();e.preventDefault();}
  if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
    theta+=(e.key==='ArrowLeft'?.08:e.key==='ArrowRight'?-.08:0);
    phi=THREE.MathUtils.clamp(phi+(e.key==='ArrowUp'?-.05:e.key==='ArrowDown'?.05:0),.02,Math.PI-.03);
    updateCamera();e.preventDefault();
  }
});
const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
let selectionBox;
function select(node) {
  selected=node;
  if(selectionBox){scene.remove(selectionBox);selectionBox.geometry.dispose();selectionBox.material.dispose();selectionBox=null;}
  if(node) {
    selectionBox=new THREE.BoxHelper(node,0xc7562c); selectionBox.material.transparent=true; selectionBox.material.opacity=.6;
    scene.add(selectionBox);
    $('#part-name').textContent=`SELECTED / ${node.name.replaceAll('_',' ').toUpperCase()}`;
  } else $('#part-name').textContent='DRAG TO ORBIT · SCROLL TO ZOOM · CLICK A PART';
}
function pick(x,y) {
  if(!jet) return;
  const r=canvas.getBoundingClientRect();pointer.set((x-r.left)/r.width*2-1,-(y-r.top)/r.height*2+1);
  raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObject(jet,true).find(h=>h.object.isMesh);
  let node=hit?.object;
  while(node&&!node.userData.rest) node=node.parent;
  select(node||null);
}

try {
  const [gltf,meta]=await Promise.all([
    new GLTFLoader().loadAsync('./assets/kestrel/kestrel.glb',e=>{
      if(e.total) $('#load-detail').textContent=`Loading airframe · ${Math.round(e.loaded/e.total*100)}%`;
    }),fetch('./assets/kestrel/kestrel.json').then(r=>{if(!r.ok)throw new Error('Model specification unavailable');return r.json();}),
  ]);
  jet=gltf.scene; metadata=meta; scene.add(jet);
  jet.traverse(o=>{
    if(o.userData.system) {
      o.userData.rest={position:o.position.clone(),quaternion:o.quaternion.clone(),
        axis:o.userData.hingeAxis?new THREE.Vector3(...o.userData.hingeAxis).normalize():null,
        travel:o.userData.travelDegrees||0,explode:new THREE.Vector3(...(o.userData.explode||[0,0,0]))};
      nodes.set(o.name,o);
    }
    if(o.isMesh) {
      o.castShadow=true;o.receiveShadow=true;meshes.push(o);originals.set(o,o.material);
      for(const m of Array.isArray(o.material)?o.material:[o.material]) {
        materials.add(m); m.envMapIntensity=.60;
        if(m.name==='Canopy coated glass'||m.name==='HUD combiner') {
          m.transparent=true;m.opacity=m.name==='HUD combiner'?.28:.46;
          m.depthWrite=false;m.transmission=.25;m.side=THREE.DoubleSide;o.castShadow=false;
        }
      }
    }
  });
  for(const key of ['length','span','height']) $(`#${key}`).textContent=meta.dimensions[key].toFixed(2);
  $('#status').textContent=`${(meta.triangles/1000).toFixed(1)}K TRIANGLES · ${(meta.glbBytes/1048576).toFixed(1)} MB`;
  ready=true;setView('hero');pose(1,true);$('#loading').classList.add('done');
  window.__jetViewer={ready:true,renderer,scene,camera,jet,nodes,metadata,desired,current,set,setView,setMaterial,
    get mode(){return mode;},get selected(){return selected?.name||null;},get frames(){return frames;}};
} catch(error) {
  console.error(error);$('#loading b').textContent='The model could not load';
  $('#load-detail').textContent=error.message;$('.loader').style.display='none';$('#status').textContent='LOAD FAILED';
}
let last=performance.now(),frames=0;
function animate(now) {
  const dt=Math.min((now-last)/1000,.05);last=now;
  if(ready) {
    pose(dt);
    if($('#rotate').checked&&!pointers.size){theta+=dt*.12;updateCamera();}
    selectionBox?.update();
  }
  renderer.render(scene,camera);frames++;requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
