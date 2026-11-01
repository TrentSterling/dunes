// ruts: coast-down in fresh sand vs. in an existing rut, and crossing ruts at 90 deg
import * as THREE from 'three';
import { SandrailPhysics } from '../public/js/vehicle-physics.js';
const mk = () => ({ sample: ()=>({h:0,dx:0,dz:0}), height:()=>0, normal:(x,z,t)=>t.set(0,1,0) });
function coast(T, label) {
  const c = new SandrailPhysics(T); c.reset(0, 0, 0);
  for (let i=0;i<100;i++) c.update(0.01);
  // creep slowly to press a deep rut, then measure coast from 10 m/s
  c.vel.set(0,0,10); c.wheels.forEach(w=>w.omega=10/w.r); c.axleOmega=10/c.wheels[2].r;
  let i=0; while (c.forwardSpeed>0.5 && i<3000) { c.update(0.01); i++; }
  console.log(label, 'coast distance', c.pos.z.toFixed(1), 'm, rear sink', c.wheels[2].sink.toFixed(3), 'lat drift', c.pos.x.toFixed(2));
  return c;
}
const T = mk();
coast(T, 'fresh sand     ');
coast(T, 'in its own ruts');
// crossing
const c = new SandrailPhysics(T); c.reset(-15, 8, Math.PI/2); for (let i=0;i<100;i++) c.update(0.01);
let maxAy=0, prevVy=0, flip=0;
for (let i=0;i<300;i++){ c.input.throttle=Math.max(0,Math.min(1,(8-c.forwardSpeed)*0.3+0.15)); c.update(0.01); const ay=(c.vel.y-prevVy)/0.01; prevVy=c.vel.y; if(i>20) maxAy=Math.max(maxAy,Math.abs(ay)); if(new THREE.Vector3(0,1,0).applyQuaternion(c.quat).y<0.5) flip=1; }
console.log('crossing ruts at 18 mph: peak vertical accel', (maxAy/9.81).toFixed(2), 'g, x', c.pos.x.toFixed(1), 'flip', flip);
