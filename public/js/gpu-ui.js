import * as THREE from 'three';

let atlasPromise;
export function loadGlyphAtlas() {
  return atlasPromise ||= Promise.all([
    new THREE.TextureLoader().loadAsync('assets/fonts/barlow-sdf.png'),
    fetch('assets/fonts/barlow-sdf.json').then(r => { if(!r.ok) throw Error('Font atlas unavailable'); return r.json(); }),
  ]).then(([texture, metrics]) => {
    texture.flipY=false; texture.colorSpace=THREE.NoColorSpace; texture.generateMipmaps=false;
    texture.minFilter=texture.magFilter=THREE.LinearFilter;
    return {texture,metrics};
  });
}

const colors=new Map();
export function rgba(hex,alpha=1) {
  if(Array.isArray(hex))return hex;
  if(!colors.has(hex)){const value=parseInt(hex.replace('#',''),16);colors.set(hex,[(value>>16&255)/255,(value>>8&255)/255,(value&255)/255]);}
  return [...colors.get(hex),alpha];
}
export const UI_COLORS={paper:'#f6eedb',muted:'#b7b2a6',ink:'#101712',panel:'#141e19',line:'#435047',orange:'#ff9b48',green:'#9bd5a4'};

// One instanced quad batch for glyphs and UI primitives, rendered by the game GPU.
export class GlyphSurface {
  constructor(renderer,atlas,{capacity=24000,target=null}={}) {
    this.renderer=renderer;this.atlas=atlas;this.capacity=capacity;this.target=target;
    this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(0,1,1,0,-1,1);
    const geometry=new THREE.InstancedBufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute([0,0,0,1,0,0,0,1,0,0,1,0,1,0,0,1,1,0],3));
    this.attrs={};
    for(const name of ['rect','uvBox','tint','style','clipBox']){
      const a=new THREE.InstancedBufferAttribute(new Float32Array(capacity*4),4).setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute(name,a);this.attrs[name]=a;
    }
    this.material=new THREE.ShaderMaterial({
      uniforms:{viewport:{value:new THREE.Vector2(1,1)},flipY:{value:1},glyphs:{value:atlas.texture},picture:{value:atlas.texture}},
      vertexShader:`attribute vec4 rect,uvBox,tint,style,clipBox;uniform vec2 viewport;uniform float flipY;varying vec2 vUv,vPoint,vSize,vScreen;varying vec4 vColor,vStyle,vClip;
      void main(){vec2 p=position.xy;vec2 center=(p-.5)*rect.zw;float c=cos(style.z),s=sin(style.z);center=mat2(c,s,-s,c)*center;
      vec2 screen=rect.xy+rect.zw*.5+center;gl_Position=vec4(screen.x/viewport.x*2.-1.,(1.-screen.y/viewport.y*2.)*flipY,0.,1.);
      vScreen=screen;vClip=clipBox;vUv=uvBox.xy+p*uvBox.zw;vPoint=(p-.5)*rect.zw;vSize=rect.zw;vColor=tint;vStyle=style;}`,
      fragmentShader:`precision highp float;uniform sampler2D glyphs,picture;varying vec2 vUv,vPoint,vSize,vScreen;varying vec4 vColor,vStyle,vClip;
      void main(){if(vScreen.x<vClip.x||vScreen.y<vClip.y||vScreen.x>vClip.z||vScreen.y>vClip.w)discard;vec4 color=vColor;float alpha=1.;
      if(vStyle.x>.5&&vStyle.x<1.5){float d=texture2D(glyphs,vUv).r;float a=max(fwidth(d)*.7,.003);alpha=smoothstep(.5-a,.5+a,d);}
      else{float radius=min(vStyle.y,min(vSize.x,vSize.y)*.5);vec2 q=abs(vPoint)-(vSize*.5-radius);float d=length(max(q,0.))+min(max(q.x,q.y),0.)-radius;
      if(vStyle.x>2.5)d=abs(length(vPoint)-(min(vSize.x,vSize.y)-vStyle.y)*.5)-vStyle.y*.5;
      alpha=1.-smoothstep(-.75,.75,d);if(vStyle.x>1.5&&vStyle.x<2.5)color*=texture2D(picture,vUv);}
      gl_FragColor=vec4(color.rgb,color.a*alpha);}`,
      transparent:true,depthTest:false,depthWrite:false,toneMapped:false,side:THREE.DoubleSide,
    });
    this.mesh=new THREE.Mesh(geometry,this.material);this.mesh.frustumCulled=false;this.scene.add(this.mesh);
    this.count=0;this.glyphCount=0;this.renderCount=0;this.frameText=[];
  }
  begin(width,height){this.width=width;this.height=height;this.count=0;this.glyphCount=0;this.frameText=[];this.clip=[0,0,width,height];this.material.uniforms.viewport.value.set(width,height);}
  quad(x,y,w,h,color,mode=0,uv=[0,0,1,1],radius=0,angle=0){
    if(w<=0||h<=0||this.count>=this.capacity)return;
    const offset=this.count++*4;
    this.attrs.rect.array.set([x,y,w,h],offset);this.attrs.uvBox.array.set(uv,offset);
    this.attrs.tint.array.set(rgba(color),offset);this.attrs.style.array.set([mode,radius,angle,0],offset);
    this.attrs.clipBox.array.set(this.clip,offset);
  }
  rect(x,y,w,h,color,radius=0){this.quad(x,y,w,h,color,0,undefined,radius);}
  ring(x,y,radius,width,color){this.quad(x-radius,y-radius,radius*2,radius*2,color,3,undefined,width);}
  line(x1,y1,x2,y2,width,color){const length=Math.hypot(x2-x1,y2-y1);this.quad((x1+x2-length)/2,(y1+y2-width)/2,length,width,color,0,undefined,0,Math.atan2(y2-y1,x2-x1));}
  image(texture,x,y,w,h,{radius=0,uv=[0,0,1,1],alpha=1}={}){this.material.uniforms.picture.value=texture;this.quad(x,y,w,h,[1,1,1,alpha],2,uv,radius);}
  measure(text,size){let length=0;for(const c of String(text)){const g=this.atlas.metrics.glyphs[c]||this.atlas.metrics.glyphs['?'];length+=g.advance*size/this.atlas.metrics.size;}return length;}
  fit(text,size,width){text=String(text);if(this.measure(text,size)<=width)return text;while(text&&this.measure(text+'...',size)>width)text=text.slice(0,-1);return text+'...';}
  text(text,x,y,size=18,color=UI_COLORS.paper,{align='left',maxWidth=Infinity}={}){
    text=this.fit(String(text),size,maxWidth);this.frameText.push(text);
    if(align==='right')x-=this.measure(text,size);else if(align==='center')x-=this.measure(text,size)/2;
    const m=this.atlas.metrics,scale=size/m.size,baseline=y+size;
    for(const char of text){const g=m.glyphs[char]||m.glyphs['?'];
      this.quad(x+g.bx*scale,baseline+g.by*scale,g.w*scale,g.h*scale,color,1,[g.x/m.width,g.y/m.height,g.w/m.width,g.h/m.height]);
      this.glyphCount++;x+=g.advance*scale;
    }return x;
  }
  wrap(text,x,y,size,color,width,lineHeight=size*1.3){let line='',row=0;for(const word of String(text).split(/\s+/)){
    if(line&&this.measure(line+' '+word,size)>width){this.text(line,x,y+row++*lineHeight,size,color);line=word;}else line+=(line?' ':'')+word;
  }if(line)this.text(line,x,y+row++*lineHeight,size,color);return row*lineHeight;}
  render({clear=false,flipY=false}={}){
    const r=this.renderer,previous=r.getRenderTarget(),auto=r.autoClear,view=r.getViewport(new THREE.Vector4()),scissor=r.getScissor(new THREE.Vector4()),scissorTest=r.getScissorTest();
    this.mesh.geometry.instanceCount=this.count;
    for(const a of Object.values(this.attrs)){a.clearUpdateRanges();a.addUpdateRange(0,this.count*4);a.needsUpdate=true;}
    r.setRenderTarget(this.target);r.setScissorTest(false);
    r.autoClear=false;
    if(clear){const color=r.getClearColor(new THREE.Color()),alpha=r.getClearAlpha();r.setClearColor(0x000000,0);r.clear();r.setClearColor(color,alpha);}
    // Render targets are sampled with glTF's top-left image convention.
    this.material.uniforms.flipY.value=flipY?-1:1;
    r.render(this.scene,this.camera);this.renderCount++;
    r.setRenderTarget(previous);r.setViewport(view);r.setScissor(scissor);r.setScissorTest(scissorTest);r.autoClear=auto;
  }
  dispose(){this.mesh.geometry.dispose();this.material.dispose();this.target?.dispose();}
}
