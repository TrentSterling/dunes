import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { SuspensionRig } from './suspension-rig.js?v=20261103-r2';

const $ = s => document.querySelector(s), names = ['FL', 'FR', 'RL', 'RR'];
const canvas = $('#viewport'), stage = $('.stage');
const scene = new THREE.Scene(); scene.background = new THREE.Color('#d6d8d1');
scene.fog = new THREE.Fog('#d6d8d1',12,40);
const renderer = new THREE.WebGLRenderer({canvas, antialias:true, preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08; renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
const camera = new THREE.PerspectiveCamera(36, 1, .025, 100);
const target = new THREE.Vector3(0,.78,0);
let radius=8.5, theta=-2.48, phi=1.23, ready=false, frames=0, rig, model;
let display='full', view='hero', running=!matchMedia('(prefers-reduced-motion: reduce)').matches;
let phase=0, pulseAge=-1, accumulator=0, steering=0, elapsed=0;
const position=Object.fromEntries(names.map(n=>[n,0])), velocity={...position}, manual={...position};
const state={pattern:'cross', amplitude:.12, speed:.3, frequency:2, damping:.65};
const originals = new Map(), staticMeshes=[], wheelNodes=[], pads=[], rods=[], dots=[];
const stand = new THREE.Group(); scene.add(stand);
const pivotGroup = new THREE.Group(); pivotGroup.visible=false; scene.add(pivotGroup);
const studio = new THREE.Scene(); studio.background = new THREE.Color('#8a9287');
for (const [p,s,intensity] of [[[-4,5,-3],[3,5,1],4], [[4,4,0],[3,6,1],3], [[0,6,3],[5,4,1],5]]) {
  const card=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({color:new THREE.Color('white').multiplyScalar(intensity),side:THREE.DoubleSide}));
  card.position.fromArray(p);card.scale.fromArray(s);card.lookAt(0,.6,0);studio.add(card);
}
const pmrem=new THREE.PMREMGenerator(renderer); scene.environment=pmrem.fromScene(studio,.04).texture;pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xf0f4ed,0x777d69,1.6));
const light=new THREE.DirectionalLight(0xfff5e8,3);light.position.set(-3.5,7,-5);light.castShadow=true;
light.shadow.mapSize.set(2048,2048);Object.assign(light.shadow.camera,{left:-4,right:4,top:4,bottom:-4,near:.5,far:20});light.shadow.normalBias=.012;light.shadow.bias=-.0001;scene.add(light);
const fill=new THREE.DirectionalLight(0xd9e6f2,1.6);fill.position.set(4,3,2);scene.add(fill);
const floor=new THREE.Mesh(new THREE.PlaneGeometry(100,100),new THREE.MeshStandardMaterial({color:'#c3c8bb',roughness:.9}));floor.rotation.x=-Math.PI/2;floor.position.y=-.46;floor.receiveShadow=true;scene.add(floor);
const grid=new THREE.GridHelper(12,24,0x9ba38f,0xb3bba6);grid.position.y=-.455;grid.material.transparent=true;grid.material.opacity=.3;scene.add(grid);
const padMat=new THREE.MeshStandardMaterial({color:'#3c4736',metalness:.65,roughness:.38});
const pistonMat=new THREE.MeshStandardMaterial({color:'#aab2a5',metalness:.85,roughness:.24});
const orangeMat=new THREE.MeshStandardMaterial({color:'#c95518',roughness:.55});

function cameraUpdate(){camera.position.set(radius*Math.sin(phi)*Math.sin(theta),radius*Math.cos(phi),radius*Math.sin(phi)*Math.cos(theta)).add(target);camera.lookAt(target);}
const views={hero:[[-5.5,3.2,-7],[0,.70,0]],front:[[0,1.55,-7],[0,.67,-.35]],rear:[[-3,2.4,6],[0,.72,.6]],side:[[-7.5,1.8,0],[0,.74,0]],under:[[-3,-1.8,-4.3],[0,.65,-.15]],detail:[[-2.4,1.25,-3.8],[-.3,.66,-1.44]]};
function setView(name){
  if(!views[name])return;view=name;
  const [p,t]=views[name];target.fromArray(t);const offset=new THREE.Vector3(...p).sub(target);
  const fit=Math.max(1,1.1/camera.aspect);offset.multiplyScalar(fit);
  radius=offset.length();theta=Math.atan2(offset.x,offset.z);phi=Math.acos(offset.y/radius);cameraUpdate();
  floor.visible=name!=='under';grid.visible=name!=='under';stand.visible=name!=='under';
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
}
function resize(){const {width,height}=stage.getBoundingClientRect();renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();setView(view);}
new ResizeObserver(resize).observe(stage);resize();
function setDisplay(mode){
  display=mode;
  for(const mesh of staticMeshes){mesh.visible=mode!=='rig';mesh.material=mode==='ghost'?mesh.userData.ghost:originals.get(mesh);mesh.castShadow=mode==='full';}
  document.querySelectorAll('[data-display]').forEach(b=>b.classList.toggle('active',b.dataset.display===mode));
}
function updateUI(){
  $('#play').textContent=running?'Pause cycle':'Run cycle';$('#status').textContent=running?'CYCLING':'PAUSED';
  for(const [id,format] of [['amplitude',v=>`${Math.round(v*1000)} mm`],['speed',v=>`${v.toFixed(2)} Hz`],['frequency',v=>`${v.toFixed(1)} Hz`],['damping',v=>v.toFixed(2)]]) $(`#${id}-value`).value=format(state[id]);
  $('#steer-value').value=`${Math.round(THREE.MathUtils.radToDeg(steering))}°`;
}
function syncManual(){for(const n of names){manual[n]=position[n];$('#'+n).value=Math.round(position[n]*1000);$(`#${n}-value`).value=`${Math.round(position[n]*1000)} mm`;}}
function pause(){running=false;pulseAge=-1;syncManual();for(const n of names)velocity[n]=0;updateUI();}
function pose(){
  if(!rig)return;rig.pose(position,steering);
  for(let i=0;i<4;i++){
    const c=rig.corners[names[i]], p=pads[i];
    const axleY=Math.abs(new THREE.Vector3(1,0,0).applyQuaternion(c.rotation).y);
    const support=c.spec.radius*Math.sqrt(1-axleY*axleY)+c.spec.width*.5*axleY;
    const height=c.hub.y-support;
    p.top.position.set(c.hub.x,height-.017,c.hub.z);
    p.shaft.position.set(c.hub.x,(height-.07-.41)/2,c.hub.z);p.shaft.scale.y=Math.max(.02,height-.07+.41);
    p.base.position.x=c.hub.x;p.base.position.z=c.hub.z;
    $(`#travel-${c.name}`).innerHTML=`${Math.round(c.travel*1000)} <small>mm</small>`;
    $(`#camber-${c.name}`).textContent=`${c.camber.toFixed(1)}° camber`;
    $(`#bar-${c.name}`).style.left=`${THREE.MathUtils.clamp((c.travel+.33)/.63*100,0,98)}%`;
    if(running||pulseAge>=0){$('#'+c.name).value=Math.round(position[c.name]*1000);$(`#${c.name}-value`).value=`${Math.round(position[c.name]*1000)} mm`;}
  }
  const lines=[...rig.segments,...Object.values(rig.shocks).map(s=>({a:s.a,b:s.end}))];
  if(pivotGroup.visible)lines.forEach((s,i)=>{
    const d=s.b.clone().sub(s.a);rods[i].position.copy(s.a).add(s.b).multiplyScalar(.5);rods[i].quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.clone().normalize());rods[i].scale.set(1,d.length(),1);dots[i*2].position.copy(s.a);dots[i*2+1].position.copy(s.b);
  });
  const err=rig.diagnostics.maxRigidLengthError*1000;
  $('#rig-status').textContent=`Rigid link closure ${err.toFixed(3)} mm · 4 uprights · 8 dampers`;
}
function simulationStep(dt){
  phase+=dt*state.speed*Math.PI*2;if(pulseAge>=0)pulseAge+=dt;
  const signs=state.pattern==='cross'?[1,-1,-1,1]:state.pattern==='front'?[1,1,0,0]:state.pattern==='rear'?[0,0,1,1]:[1,1,1,1];
  names.forEach((n,i)=>{
    let demand=manual[n];
    if(pulseAge>=0)demand=pulseAge<.36?Math.sin(pulseAge/.36*Math.PI)*state.amplitude*(i<2?1:0):0;
    else if(running&&state.pattern!=='manual')demand=state.amplitude*Math.sin(phase+(state.pattern==='ripple'?i*1.3:0))*signs[i];
    const w=state.frequency*Math.PI*2;
    velocity[n]+=(w*w*(demand-position[n])-2*state.damping*w*velocity[n])*dt;
    position[n]+=velocity[n]*dt;
    const limited=THREE.MathUtils.clamp(position[n],n[0]==='F'?-.33:-.15,.3);if(limited!==position[n])velocity[n]=0;position[n]=limited;
  });
  if(pulseAge>6){pulseAge=-1;pause();}
}

$('#play').addEventListener('click',()=>{if(running){pause();}else{if(state.pattern==='manual'){state.pattern='cross';$('#pattern').value='cross';}pulseAge=-1;running=true;phase=0;updateUI();}});
$('#pulse').addEventListener('click',()=>{running=false;pulseAge=0;for(const n of names)manual[n]=0;updateUI();$('#status').textContent='BUMP TEST';});
$('#pattern').addEventListener('change',e=>{state.pattern=e.target.value;pulseAge=-1;if(state.pattern==='manual')pause();else{running=true;phase=0;updateUI();}});
for(const id of ['amplitude','speed','frequency','damping'])$('#'+id).addEventListener('input',e=>{state[id]=Number(e.target.value)/(id==='amplitude'?1000:1);updateUI();});
for(const n of names)$('#'+n).addEventListener('input',e=>{const value=Number(e.target.value)/1000;pause();state.pattern='manual';$('#pattern').value='manual';manual[n]=position[n]=value;velocity[n]=0;syncManual();pose();});
$('#steer').addEventListener('input',e=>{steering=THREE.MathUtils.degToRad(Number(e.target.value));updateUI();pose();});
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
document.querySelectorAll('[data-display]').forEach(b=>b.addEventListener('click',()=>setDisplay(b.dataset.display)));
$('#joints').addEventListener('change',e=>{pivotGroup.visible=e.target.checked;pose();});
$('#wheels').addEventListener('change',e=>wheelNodes.forEach(n=>n.visible=e.target.checked));
function reset(){pause();state.pattern='manual';$('#pattern').value='manual';steering=0;$('#steer').value=0;for(const n of names)position[n]=velocity[n]=manual[n]=0;syncManual();setDisplay('full');$('#joints').checked=false;pivotGroup.visible=false;$('#wheels').checked=true;wheelNodes.forEach(n=>n.visible=true);$('#turntable').checked=false;setView('hero');updateUI();pose();}
$('#reset').addEventListener('click',reset);
$('#fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('#app').requestFullscreen();}catch{$('#rig-status').textContent='Fullscreen unavailable in this browser';}});

const pointers=new Map();let mouseButton=0;
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);mouseButton=e.button;});
canvas.addEventListener('pointermove',e=>{
  if(!pointers.has(e.pointerId))return;
  const previous=pointers.get(e.pointerId),dx=e.clientX-previous[0],dy=e.clientY-previous[1];
  if(pointers.size===2){const other=[...pointers.entries()].find(([id])=>id!==e.pointerId)[1];const before=Math.hypot(previous[0]-other[0],previous[1]-other[1]),after=Math.hypot(e.clientX-other[0],e.clientY-other[1]);if(after>1)radius=THREE.MathUtils.clamp(radius*before/after,.35,20);}
  else if(mouseButton===2||e.shiftKey){target.addScaledVector(new THREE.Vector3().setFromMatrixColumn(camera.matrix,0),-dx*radius*.001);target.addScaledVector(new THREE.Vector3().setFromMatrixColumn(camera.matrix,1),dy*radius*.001);}
  else{theta-=dx*.006;phi=THREE.MathUtils.clamp(phi-dy*.005,.03,Math.PI-.03);}
  pointers.set(e.pointerId,[e.clientX,e.clientY]);cameraUpdate();
});
for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,e=>pointers.delete(e.pointerId));
canvas.addEventListener('wheel',e=>{e.preventDefault();radius=THREE.MathUtils.clamp(radius*Math.exp(e.deltaY*.001),.35,20);cameraUpdate();},{passive:false});
canvas.addEventListener('keydown',e=>{if(e.key==='Home'){setView('hero');e.preventDefault();}if(e.code==='Space'){ $('#play').click();e.preventDefault();}});

try{
  const loader=new GLTFLoader(),json=async file=>{const r=await fetch(file);if(!r.ok)throw new Error(`Cannot load ${file}`);return r.json();};
  const [car,physics,shocks,parts]=await Promise.all([
    loader.loadAsync('./assets/suspension/sandcar.glb',e=>{if(e.total)$('#load-detail').textContent=`Loading the rebuilt sandrail · ${Math.round(e.loaded/e.total*100)}%`;}),
    json('./assets/suspension/sandcar.physics.json'),loader.loadAsync('./assets/suspension/shocks.glb'),json('./assets/suspension/shocks.json')]);
  // GLTFLoader's material primitives can collide with authored node names:
  // a primitive of Shock_FL can itself be called Shock_FL_2. Preserve the real
  // node names and rename primitive collisions before any rig lookup.
  const authoredNodes=new Map();
  car.scene.traverse(o=>{
    if(car.parser.associations.get(o)?.nodes===undefined)return;
    if(authoredNodes.has(o.name))throw new Error(`Duplicate authored assembly: ${o.name}`);
    authoredNodes.set(o.name,o);
  });
  car.scene.traverse(o=>{if(authoredNodes.has(o.name)&&authoredNodes.get(o.name)!==o)o.name+='_primitive';});
  model=car.scene;scene.add(model);rig=new SuspensionRig(model,physics,shocks.scene,parts,authoredNodes);
  model.traverse(mesh=>{if(!mesh.isMesh)return;mesh.castShadow=true;mesh.receiveShadow=true;originals.set(mesh,mesh.material);
    for(const m of Array.isArray(mesh.material)?mesh.material:[mesh.material]){m.envMapIntensity=.55;if(m.name==='Livery'||m.name==='Livery top')m.roughness=Math.max(m.roughness,.27);}
  });
  for(const name of ['Chassis','SteeringWheel','LightBar'])model.getObjectByName(name)?.traverse(mesh=>{if(!mesh.isMesh)return;staticMeshes.push(mesh);mesh.userData.ghost=new THREE.MeshStandardMaterial({color:'#819379',transparent:true,opacity:.10,depthWrite:false,roughness:.8});});
  for(const n of names){wheelNodes.push(model.getObjectByName('Wheel_'+n));const top=new THREE.Mesh(new THREE.CylinderGeometry(.34,.34,.034,48),padMat),shaft=new THREE.Mesh(new THREE.CylinderGeometry(.048,.048,1,16),pistonMat),base=new THREE.Mesh(new THREE.CylinderGeometry(.17,.20,.06,24),orangeMat);base.position.y=-.415;top.receiveShadow=true;top.castShadow=true;stand.add(top,shaft,base);pads.push({top,shaft,base});}
  const lineMat=new THREE.MeshBasicMaterial({color:'#ff641b',depthTest:false,transparent:true,opacity:.85});
  const dotMat=new THREE.MeshBasicMaterial({color:'#ffe9a7',depthTest:false});
  for(let i=0;i<physics.links.length+physics.shocks.length;i++){
    const rod=new THREE.Mesh(new THREE.CylinderGeometry(.005,.005,1,6),lineMat);rod.renderOrder=10;pivotGroup.add(rod);rods.push(rod);
    for(let k=0;k<2;k++){const dot=new THREE.Mesh(new THREE.SphereGeometry(.018,8,6),dotMat);dot.renderOrder=11;pivotGroup.add(dot);dots.push(dot);}
  }
  ready=true;pose();updateUI();$('#loading').classList.add('done');$('#play').disabled=false;$('#pulse').disabled=false;
  window.__suspension={revision:'20261103-r2',get ready(){return ready;},get frames(){return frames;},rig,renderer,scene,camera,model,state,position,velocity,pads,reset,pause,pose,setView,setDisplay,
    get running(){return running;},get display(){return display;},
    setPose(values,deg=0){pause();for(const n of names)position[n]=manual[n]=THREE.MathUtils.clamp(values[n]||0,n[0]==='F'?-.33:-.15,.3);steering=THREE.MathUtils.degToRad(deg);$('#steer').value=deg;syncManual();updateUI();pose();},
    step(dt){simulationStep(dt);pose();},get diagnostics(){return rig.diagnostics;}};
}catch(error){console.error(error);$('#loading b').textContent='The model could not load';$('#load-detail').textContent=error.message;$('#status').textContent='LOAD FAILED';}
let previous=performance.now();
function animate(now){
  const dt=Math.min((now-previous)/1000,.05);previous=now;elapsed+=dt;
  if(ready){
    if(running||pulseAge>=0){accumulator+=dt;while(accumulator>=1/240){simulationStep(1/240);accumulator-=1/240;}pose();}
    if($('#turntable').checked&&!pointers.size){theta+=dt*.18;cameraUpdate();}
  }
  renderer.render(scene,camera);frames++;requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
