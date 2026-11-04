import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {clone} from 'three/addons/utils/SkeletonUtils.js';

export const LAYER_RIDER=4;
let asset;
export async function loadRider(){
  try{asset=await new GLTFLoader().loadAsync('assets/driver/rider.glb');}
  catch(error){console.warn('Rider unavailable:',error.message);}
  return asset;
}

export class DriverRider {
  static for(model){return asset&&model.eye&&model.steeringWheel?new DriverRider(model):null;}
  constructor(model){
    this.model=model;this.root=clone(asset.scene);this.root.name='Helmeted rider';this.bones={};this.rest=[];
    this.root.traverse(o=>{if(o.isBone){this.bones[o.name]=o;this.rest.push([o,o.quaternion.clone()]);}if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.frustumCulled=false;}});
    const e=model.eye;this.root.scale.setScalar(1.05);this.root.rotation.x=-.12;
    const anchor=new THREE.Vector3(0,1.70,.008).multiplyScalar(1.05).applyEuler(this.root.rotation);
    this.root.position.set(e.x,e.y+.025,e.z+.02).sub(anchor);model.body.add(this.root);
    model.root.updateMatrixWorld(true);
    const inv=model.body.matrixWorld.clone().invert(),wheel=inv.multiply(model.steeringWheel.matrixWorld);
    this.center=new THREE.Vector3().setFromMatrixPosition(wheel);this.axis=new THREE.Vector3().setFromMatrixColumn(wheel,1).normalize();
    this.left=new THREE.Vector3(1,0,0).addScaledVector(this.axis,-this.axis.x).normalize();this.down=new THREE.Vector3().crossVectors(this.axis,this.left);
    this.radius=model.arms?.r||.155;this.localHandTargets=[];this.local=null;
    this.update(0);
  }
  setLocal(on){if(this.local===on)return;this.local=on;this.root.traverse(o=>o.layers.set(on?LAYER_RIDER:0));}
  get handTargets(){return this.localHandTargets.map(p=>this.model.body.localToWorld(p.clone()));}
  point(name){return this.bones[name].getWorldPosition(new THREE.Vector3());}
  aim(name,child,target){
    const b=this.bones[name],from=this.point(child).sub(this.point(name)).normalize(),to=target.clone().sub(this.point(name)).normalize();
    const q=new THREE.Quaternion().setFromUnitVectors(from,to).multiply(b.getWorldQuaternion(new THREE.Quaternion()));
    b.quaternion.copy(b.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(q));b.updateWorldMatrix(false,true);
  }
  chain(upper,lower,end,target,pole){
    const S=this.point(upper),E=this.point(lower),W=this.point(end),l1=S.distanceTo(E),l2=E.distanceTo(W);
    const axis=target.clone().sub(S),length=Math.max(.001,Math.min(axis.length(),(l1+l2)*.995));axis.normalize();
    const a=(l1*l1-l2*l2+length*length)/(2*length),h=Math.sqrt(Math.max(0,l1*l1-a*a));
    const bend=pole.clone().sub(S);bend.addScaledVector(axis,-bend.dot(axis)).normalize();
    this.aim(upper,lower,S.clone().addScaledVector(axis,a).addScaledVector(bend,h));this.aim(lower,end,target);
  }
  update(steer=0){
    if(Math.abs(steer-(this.lastSteer??Infinity))<.001)return;
    this.lastSteer=steer;
    for(const [bone,q]of this.rest)bone.quaternion.copy(q);
    this.model.body.updateWorldMatrix(true,true);
    const body=this.model.body,e=this.model.eye;
    const world=p=>body.localToWorld(p);
    this.localHandTargets.length=0;
    for(const [side,sign]of [['l',1],['r',-1]]){
      const foot=new THREE.Vector3(e.x+sign*.12,.46,e.z+.84);
      this.chain('thigh_'+side,'calf_'+side,'foot_'+side,world(foot.clone()),world(new THREE.Vector3(e.x+sign*.16,.90,e.z+.42)));
      this.aim('foot_'+side,'ball_'+side,world(foot.clone().add(new THREE.Vector3(0,.015,.14))));
      const angle=THREE.MathUtils.clamp(steer*5,-.7,.7)+(sign<0?Math.PI:0);
      const grip=this.center.clone().addScaledVector(this.left,Math.cos(angle)*this.radius).addScaledVector(this.down,Math.sin(angle)*this.radius);
      const localWrist=grip.clone().addScaledVector(this.axis,.10);this.localHandTargets.push(localWrist);
      const wrist=world(localWrist.clone());
      this.chain('upperarm_'+side,'lowerarm_'+side,'hand_'+side,wrist,world(new THREE.Vector3(e.x+sign*.40,e.y-.43,e.z+.06)));
      this.aim('hand_'+side,'middle_01_'+side,world(grip));
      // A relaxed grip reads better than flat T-pose fingers outside the car.
      for(const finger of ['index','middle','ring','pinky'])for(const joint of ['02','03'])this.bones[`${finger}_${joint}_${side}`]?.rotateX(-.65);
    }
    this.root.updateWorldMatrix(false,true);
  }
}
