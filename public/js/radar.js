// GPU radar shares the driving surface's height textures and dune functions.
// Map shading, contours, rings, markers and compass never use Canvas2D.
import * as THREE from 'three';
import {TERRAIN_GLSL} from './terrain-render.js';
import {GlyphSurface, UI_COLORS as C} from './gpu-ui.js';

export const RADAR_RANGES = [300, 600, 1200, 2500];
const BOT_COLOR = '#ffb05c', PLAYER_COLOR = '#73e5f5';

export class Radar {
  constructor(renderer, terrain, atlas) {
    this.renderer=renderer; this.terrain=terrain; this.range=600;
    this.me={x:0,z:0,fx:0,fz:-1}; this.blips=[]; this.markers=[];
    this.drawCount=0; this.navDrawCount=0;
    this.target=new THREE.WebGLRenderTarget(512,512,{depthBuffer:false});
    this.navTarget=new THREE.WebGLRenderTarget(512,442,{depthBuffer:false});
    this.texture=this.target.texture; this.navTexture=this.navTarget.texture;
    this.overlay=new GlyphSurface(renderer,atlas,{target:this.target,capacity:4000});
    this.navOverlay=new GlyphSurface(renderer,atlas,{target:this.navTarget,capacity:2000});
    this.scene=new THREE.Scene();
    this.camera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
    this.uniforms={...terrain.uniforms,
      radarCenter:{value:new THREE.Vector2()},radarForward:{value:new THREE.Vector2(0,-1)},
      radarRange:{value:600},radarAspect:{value:1},radarCircular:{value:1}};
    this.material=new THREE.ShaderMaterial({
      uniforms:this.uniforms,depthTest:false,depthWrite:false,toneMapped:false,
      vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}`,
      fragmentShader:`precision highp float;varying vec2 vUv;
        uniform vec2 radarCenter,radarForward;
        uniform float radarRange,radarAspect,radarCircular;
        ${TERRAIN_GLSL}
        void main(){
          vec2 p=(vUv-.5)*2.;float radius=length(p);
          if(radarCircular>.5&&radius>.96){gl_FragColor=vec4(0.);return;}
          p.y*=radarAspect;
          vec2 right=vec2(-radarForward.y,radarForward.x);
          vec2 world=radarCenter+(right*p.x-radarForward*p.y)*radarRange/(radarCircular>.5?.94:1.);
          vec3 dune=duneHD(world);float h=baseHeight(world)+dune.x;
          vec2 slope=baseGrad(world)+dune.yz;
          vec3 normal=normalize(vec3(-slope.x,1.,-slope.y));
          float light=clamp(.43+.66*dot(normal,normalize(vec3(-.55,.75,-.35))),.1,1.);
          vec3 color=mix(vec3(.13,.22,.18),vec3(.75,.66,.45),light);
          float contour=abs(fract(h/10.+.5)-.5),width=max(fwidth(h/10.)*.7,.008);
          color*=1.-.25*(1.-smoothstep(width,width*2.,contour));
          float major=abs(fract(h/50.+.5)-.5);
          color=mix(color,vec3(.94,.84,.62),.2*(1.-smoothstep(width*.2,width*.4,major)));
          float alpha=radarCircular>.5?1.-smoothstep(.944,.96,radius):1.;
          gl_FragColor=vec4(color,alpha);
        }`,
    });
    this.mesh=new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.material);
    this.mesh.frustumCulled=false;this.scene.add(this.mesh);
  }

  draw(me,blips,{hud=true,nav=false}={}) {
    this.me={...me};const length=Math.hypot(me.fx,me.fz)||1;
    this.forward={x:me.fx/length,z:me.fz/length};this.blips=blips;
    this.counts={bots:blips.filter(b=>b.kind==='bot').length,players:blips.filter(b=>b.kind==='player').length};
    if(hud){this.renderView(this.target,this.overlay,this.forward,this.range,true);this.drawCount++;}
    if(nav){this.renderView(this.navTarget,this.navOverlay,{x:0,z:-1},450,false);this.navDrawCount++;}
  }

  project(point,forward=this.forward,range=this.range,width=256,height=256,circular=true) {
    const dx=point.x-this.me.x,dz=point.z-this.me.z,scale=width*.5/range*(circular?.94:1);
    let x=(-forward.z*dx+forward.x*dz)*scale,y=-(forward.x*dx+forward.z*dz)*scale;
    const angle=Math.atan2(y,x),distance=Math.hypot(dx,dz);let edge=false;
    if(circular){const max=width*.5*.84,d=Math.hypot(x,y);if(d>max){x*=max/d;y*=max/d;edge=true;}}
    else{const f=Math.max(Math.abs(x)/(width*.5-12),Math.abs(y)/(height*.5-12),1);edge=f>1;x/=f;y/=f;}
    return {x:width*.5+x,y:height*.5+y,edge,angle,distance,kind:point.kind};
  }

  renderView(target,g,forward,range,circular) {
    const r=this.renderer,previous=r.getRenderTarget(),auto=r.autoClear;
    const view=r.getViewport(new THREE.Vector4()),scissor=r.getScissor(new THREE.Vector4()),scissorTest=r.getScissorTest();
    const clear=r.getClearColor(new THREE.Color()),alpha=r.getClearAlpha();
    const width=circular?256:640,height=circular?256:552;
    this.uniforms.radarCenter.value.set(this.me.x,this.me.z);this.uniforms.radarForward.value.set(forward.x,forward.z);
    this.uniforms.radarRange.value=range;this.uniforms.radarAspect.value=height/width;this.uniforms.radarCircular.value=circular?1:0;
    r.setRenderTarget(target);r.setScissorTest(false);r.setClearColor(0,0);r.autoClear=false;r.clear();r.render(this.scene,this.camera);
    r.setRenderTarget(previous);r.setViewport(view);r.setScissor(scissor);r.setScissorTest(scissorTest);r.setClearColor(clear,alpha);r.autoClear=auto;
    g.begin(width,height);
    if(circular){
      for(const radius of [40,80,120])g.ring(128,128,radius,radius===120?1.6:.7,radius===120?C.paper:[.96,.93,.85,.35]);
      g.line(18,128,238,128,.6,[.96,.93,.85,.23]);g.line(128,18,128,238,.6,[.96,.93,.85,.23]);
      for(const [label,x,z]of [['N',0,-1],['E',1,0],['S',0,1],['W',-1,0]]){
        const sx=(-forward.z*x+forward.x*z)*108,sy=-(forward.x*x+forward.z*z)*108;
        g.rect(128+sx-9,128+sy-10,18,22,'#15251e',4);
        g.text(label,128+sx,128+sy-10,16,label==='N'?C.orange:C.paper,{align:'center'});
      }
    }
    const markers=[];
    for(const b of this.blips){
      const p=this.project(b,forward,range,width,height,circular),color=b.kind==='player'?PLAYER_COLOR:BOT_COLOR;
      markers.push({...p,name:b.name||''});
      if(p.edge){
        const tip=[p.x+Math.cos(p.angle)*5,p.y+Math.sin(p.angle)*5];
        for(const side of [-1,1]){const a=p.angle+side*2.3;g.line(p.x+Math.cos(a)*5,p.y+Math.sin(a)*5,...tip,4,'#0c1712');g.line(p.x+Math.cos(a)*5,p.y+Math.sin(a)*5,...tip,2,color);}
      }else if(b.kind==='player'){
        g.quad(p.x-6,p.y-6,12,12,'#0c1712',0,undefined,1,Math.PI/4);g.quad(p.x-4,p.y-4,8,8,color,0,undefined,1,Math.PI/4);
      }else{g.rect(p.x-5,p.y-5,10,10,'#0c1712',5);g.rect(p.x-3,p.y-3,6,6,color,3);}
    }
    if(circular){this.markers=markers;
      for(const side of [-1,1]){g.line(128+side*7,136,128,117,5,'#0c1712');g.line(128+side*7,136,128,117,2.5,C.paper);}
      g.rect(126,129,4,7,C.orange,2);
    }
    g.render({flipY:true});
  }

  dispose(){this.overlay.dispose();this.navOverlay.dispose();this.mesh.geometry.dispose();this.material.dispose();}
}
