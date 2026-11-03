import * as THREE from 'three';

const V = a => new THREE.Vector3(...a);
const X = new THREE.Vector3(1, 0, 0);
const Y = new THREE.Vector3(0, 1, 0);
const clamp = THREE.MathUtils.clamp;
const rotate = (point, pivot, q) => point.clone().sub(pivot).applyQuaternion(q).add(pivot);
const axisRotation = (axis, a) => new THREE.Quaternion().setFromAxisAngle(axis, a);

// Small constraint systems, solved from the authored neutral assembly each time.
// Finite differences keep the constraint definitions directly inspectable.
function solve(values, residual, iterations = 28) {
  const n = values.length, h = 1e-5;
  for (let it = 0; it < iterations; it++) {
    const f = residual(values);
    if (Math.max(...f.map(Math.abs)) < 1e-9) break;
    const rows = f.map((v, i) => [...values.map((_, j) => {
      const probe = [...values]; probe[j] += h;
      return (residual(probe)[i] - v) / h;
    }), -v]);
    for (let col = 0; col < n; col++) {
      let pivot = col;
      for (let r = col + 1; r < n; r++) if (Math.abs(rows[r][col]) > Math.abs(rows[pivot][col])) pivot = r;
      [rows[pivot], rows[col]] = [rows[col], rows[pivot]];
      if (Math.abs(rows[col][col]) < 1e-12) return values;
      const d = rows[col][col];
      for (let j = col; j <= n; j++) rows[col][j] /= d;
      for (let r = 0; r < n; r++) if (r !== col) {
        const m = rows[r][col];
        for (let j = col; j <= n; j++) rows[r][j] -= m * rows[col][j];
      }
    }
    for (let j = 0; j < n; j++) values[j] += clamp(rows[j][n], -.12, .12);
  }
  return values;
}

export class SuspensionRig {
  constructor(model, physics, shockScene, shockParts, authoredNodes) {
    this.model = model; this.physics = physics; this.corners = {}; this.parts = [];
    this.shocks = {}; this.segments = []; this.diagnostics = {}; this.replacedNodes = [];
    model.updateMatrixWorld(true);
    const node = name => {
      // Only real glTF nodes may own a rig transform. Loader-created material
      // primitives can have the same generated name as a different assembly.
      const result = authoredNodes.get(name);
      if (!result) throw new Error(`Missing rig part: ${name}`);
      result.userData.rest = {p: result.position.clone(), q: result.quaternion.clone(), s: result.scale.clone()};
      return result;
    };
    for (const w of physics.wheels) {
      const links = physics.links.filter(l => l.wheel === w.name).map(l => ({...l, a: V(l.a), b: V(l.b), object: node(l.node)}));
      const c = {spec: w, name: w.name, rest: V(w.center), wheel: node(w.node), upright: node('Upright_' + w.name), links};
      c.lower = links.find(l => l.node.endsWith('Lower_0'));
      if (w.steer) {
        c.lower2 = links.find(l => l.node.endsWith('Lower_2'));
        c.upper = links.find(l => l.node.endsWith('Upper_0'));
        c.upper2 = links.find(l => l.node.endsWith('Upper_2'));
        c.lowAxis = c.lower2.a.clone().sub(c.lower.a).normalize();
        c.upAxis = c.upper2.a.clone().sub(c.upper.a).normalize();
        c.kingpin = c.upper.b.clone().sub(c.lower.b);
      } else c.rods = links.filter(l => /Lower_2|Upper_0/.test(l.node));
      this.corners[w.name] = c;
    }
    for (const s of physics.shocks) {
      const original = node(s.node);
      original.removeFromParent();
      this.replacedNodes.push(original);
      this.shocks[s.node] = {...s, a: V(s.a), b: V(s.b), parts: []};
    }
    // Bake the exported rest transform into each separate authored component.
    shockScene.updateMatrixWorld(true);
    for (const p of shockParts) {
      const source = shockScene.getObjectByName(p.node);
      if (!source) throw new Error(`Missing split shock component: ${p.node}`);
      const meshes = []; source.traverse(m => { if (m.isMesh) meshes.push(m); });
      for (const mesh of meshes) {
        mesh.geometry = mesh.geometry.clone().applyMatrix4(mesh.matrixWorld);
        mesh.removeFromParent(); model.add(mesh);
        mesh.matrixAutoUpdate = false; mesh.matrix.identity();
        mesh.castShadow = true; mesh.receiveShadow = true;
        this.shocks[p.shock].parts.push({...p, mesh}); this.parts.push(mesh);
      }
    }
    this.steeringWheel = authoredNodes.get('SteeringWheel');
    this.steeringRest = this.steeringWheel?.quaternion.clone();
    this.pose({FL: 0, FR: 0, RL: 0, RR: 0}, 0);
  }

  rigid(object, pivot, q) {
    const r = object.userData.rest;
    object.position.copy(rotate(r.p, pivot, q));
    object.quaternion.copy(q).multiply(r.q); object.scale.copy(r.s);
  }

  span(link, b, telescope = false) {
    const d0 = link.b.clone().sub(link.a), d1 = b.clone().sub(link.a);
    const q = new THREE.Quaternion().setFromUnitVectors(d0.clone().normalize(), d1.clone().normalize());
    this.rigid(link.object, link.a, q);
    if (telescope) {
      const localAxis = d0.clone().normalize().applyQuaternion(link.object.userData.rest.q.clone().invert());
      const axis = [Math.abs(localAxis.x), Math.abs(localAxis.y), Math.abs(localAxis.z)].indexOf(Math.max(Math.abs(localAxis.x), Math.abs(localAxis.y), Math.abs(localAxis.z)));
      link.object.scale.setComponent(axis, link.object.userData.rest.s.getComponent(axis) * d1.length() / d0.length());
      link.object.position.copy(link.a).add(b).multiplyScalar(.5);
    }
    this.segments.push({name: link.node, a: link.a.clone(), b: b.clone(), lengthError: d1.length() - d0.length(), telescoping: telescope});
  }

  pose(travel, steering) {
    this.segments = [];
    for (const c of Object.values(this.corners)) {
      // The authored rear radius-rod assembly reaches a linkage singularity
      // around 163 mm droop. Stop on its neutral-connected branch, before that
      // point, rather than stretching a rigid rod or jumping to a folded branch.
      const dy = clamp(travel[c.name] || 0, c.spec.steer ? -this.physics.droop_m : -.15, this.physics.bump_m);
      let q, hub, lowQ;
      if (c.spec.steer) {
        const restLen = c.kingpin.length();
        const evaluate = angles => {
          const loQ = axisRotation(c.lowAxis, angles[0]), upQ = axisRotation(c.upAxis, angles[1]);
          const low=rotate(c.lower.b,c.lower.a,loQ),up=rotate(c.upper.b,c.upper.a,upQ);
          const kingpin=up.clone().sub(low).normalize();
          const uprightQ=new THREE.Quaternion().setFromUnitVectors(c.kingpin.clone().normalize(),kingpin);
          uprightQ.premultiply(axisRotation(kingpin,steering));
          const hub=c.rest.clone().sub(c.lower.b).applyQuaternion(uprightQ).add(low);
          return {loQ,upQ,low,up,uprightQ,hub};
        };
        const angles = solve([0, 0], a => {
          const p = evaluate(a);
          return [p.hub.y - c.rest.y - dy, p.up.distanceTo(p.low) - restLen];
        });
        const p = evaluate(angles); lowQ = p.loQ;
        // The test stand holds commanded hub height while steering around the
        // moving kingpin, including its authored inclination.
        q=p.uprightQ;hub=p.hub;
        for (const l of [c.lower, c.lower2]) this.rigid(l.object, c.lower.a, p.loQ);
        for (const l of [c.upper, c.upper2]) this.rigid(l.object, c.upper.a, p.upQ);
        for (const l of [c.lower, c.lower2, c.upper, c.upper2]) {
          const end = l.node.includes('Lower') ? p.low : p.up;
          this.segments.push({name: l.node, a: l.a.clone(), b: end.clone(), lengthError: end.distanceTo(l.a) - l.b.distanceTo(l.a)});
        }
        const tie = c.links.find(l => l.node.startsWith('TieRod'));
        const tieEnd = tie.b.clone().sub(c.lower.b).applyQuaternion(q).add(p.low);
        // The exported rack is fixed. Tie-rod visual length follows the authored
        // steering command; this is not an Ackermann/rack constraint solution.
        this.span(tie, tieEnd, true);
        c.closureError = Math.abs(p.up.distanceTo(p.low) - restLen);
      } else {
        const makeQ = a => new THREE.Quaternion().setFromEuler(new THREE.Euler(...a, 'XYZ'));
        const angles = solve([0, 0, 0], a => {
          const r = makeQ(a), h = rotate(c.rest, c.lower.a, r);
          return [h.y - c.rest.y - dy, ...c.rods.map(l => rotate(l.b, c.lower.a, r).distanceTo(l.a) - l.b.distanceTo(l.a))];
        }, 45);
        q = makeQ(angles); lowQ = q; hub = rotate(c.rest, c.lower.a, q);
        this.rigid(c.lower.object, c.lower.a, q);
        this.segments.push({name: c.lower.node, a: c.lower.a.clone(), b: rotate(c.lower.b, c.lower.a, q), lengthError: 0});
        for (const l of c.rods) this.span(l, rotate(l.b, c.lower.a, q));
        this.span(c.links.find(l => l.node.startsWith('Halfshaft')), rotate(c.links.find(l => l.node.startsWith('Halfshaft')).b, c.lower.a, q), true);
        c.closureError = Math.max(...c.rods.map(l => Math.abs(rotate(l.b, c.lower.a, q).distanceTo(l.a) - l.b.distanceTo(l.a))));
      }
      for (const object of [c.wheel, c.upright]) {
        object.position.copy(hub); object.quaternion.copy(q).multiply(object.userData.rest.q);
      }
      c.hub = hub; c.rotation = q; c.travel = hub.y - c.rest.y;
      c.camber = THREE.MathUtils.radToDeg(Math.asin(clamp(X.clone().applyQuaternion(q).y, -1, 1))) * (c.name.endsWith('L') ? -1 : 1);
      for (const s of Object.values(this.shocks).filter(s => s.wheel === c.name)) {
        const end = rotate(s.b, c.lower.a, lowQ);
        this.poseShock(s, end);
      }
    }
    if (this.steeringWheel) this.steeringWheel.quaternion.copy(this.steeringRest).multiply(axisRotation(Y, steering * 5));
    this.model.updateMatrixWorld(true);
    this.diagnostics = {
      maxClosureError: Math.max(...Object.values(this.corners).map(c => c.closureError)),
      maxRigidLengthError: Math.max(...this.segments.filter(s => !s.telescoping).map(s => Math.abs(s.lengthError))),
      corners: Object.fromEntries(Object.values(this.corners).map(c => [c.name, {travel: c.travel, camber: c.camber, hub: c.hub.toArray(), closureError: c.closureError}])),
      shocks: Object.fromEntries(Object.values(this.shocks).map(s => [s.node, {length: s.length, compression: s.compression, a: s.a.toArray(), b: s.end.toArray()}])),
    };
    return this.diagnostics;
  }

  poseShock(s, end) {
    const top = s.a, bottom = s.b;
    const dir0 = top.clone().sub(bottom).normalize(), dir1 = top.clone().sub(end).normalize();
    const length0 = top.distanceTo(bottom), length = top.distanceTo(end), delta = length - length0;
    const turn = new THREE.Quaternion().setFromUnitVectors(dir0, dir1);
    for (const p of s.parts) {
      let scale = 1, shift = 0;
      if (p.kind === 'top') shift = delta;
      else if (p.kind === 'spring') { scale = Math.max(.06, 1 + delta / (p.springMax - p.springMin)); shift = p.springMin * (1 - scale); }
      else if (p.kind === 'slider') shift = delta * (p.axialCenter - p.springMin) / (p.springMax - p.springMin);
      else if (p.kind === 'shaft') {
        // Render the exposed chrome span plus its original overlap inside the
        // barrel. Only this span changes length; barrel and eyes stay rigid.
        scale = Math.max(.02, 1 + delta / (p.axialMax - p.axialMin));
        shift = p.axialMin * (1 - scale);
      }
      const a = dir0, k = scale - 1;
      const axial = new THREE.Matrix4().set(1+k*a.x*a.x,k*a.x*a.y,k*a.x*a.z,0, k*a.y*a.x,1+k*a.y*a.y,k*a.y*a.z,0, k*a.z*a.x,k*a.z*a.y,1+k*a.z*a.z,0, 0,0,0,1);
      p.mesh.matrix.makeTranslation(...end.toArray())
        .multiply(new THREE.Matrix4().makeRotationFromQuaternion(turn))
        .multiply(new THREE.Matrix4().makeTranslation(...dir0.clone().multiplyScalar(shift).toArray()))
        .multiply(axial).multiply(new THREE.Matrix4().makeTranslation(...bottom.clone().negate().toArray()));
      p.mesh.matrixWorldNeedsUpdate = true;
    }
    s.end = end; s.length = length; s.compression = length0 - length;
  }
}
