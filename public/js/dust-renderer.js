import * as THREE from 'three';

// Full-resolution opaque/grain pass, bounded-resolution dust, depth-aware upscale.
export class DustRenderer {
  constructor(renderer, particles, {samples=0}={}) {
    this.renderer=renderer; this.particles=particles; this.enabled=true;
    this.world=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,samples,depthTexture:new THREE.DepthTexture(1,1,THREE.FloatType)});
    this.dust=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,depthBuffer:false});
    this.dustScene=new THREE.Scene();
    const source=particles.dust.mesh;
    this.mesh=new THREE.Mesh(source.geometry,source.material);this.mesh.frustumCulled=false;this.dustScene.add(this.mesh);
    this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
    this.size=new THREE.Vector2();this.stats={width:0,height:0,dustWidth:0,dustHeight:0,draws:0};
    this.material=new THREE.ShaderMaterial({
      uniforms:{worldColor:{value:this.world.texture},worldDepth:{value:this.world.depthTexture},dustColor:{value:this.dust.texture},dustSize:{value:new THREE.Vector2()},invProjection:{value:new THREE.Matrix4()},reversed:{value:1}},
      depthTest:false,depthWrite:false,
      vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
      fragmentShader:`varying vec2 vUv;uniform sampler2D worldColor,worldDepth,dustColor;
        uniform vec2 dustSize;uniform mat4 invProjection;uniform float reversed;
        float distanceAt(vec2 uv){float z=texture2D(worldDepth,uv).r;vec4 p=invProjection*vec4(uv*2.-1.,mix(z*2.-1.,z,reversed),1.);return -p.z/p.w;}
        void main(){
          float depth=distanceAt(vUv);vec2 p=vUv*dustSize-.5,base=floor(p),f=fract(p);vec4 cloud=vec4(0.);float sum=0.;
          for(int y=0;y<2;y++)for(int x=0;x<2;x++){
            vec2 offset=vec2(float(x),float(y)),uv=clamp((base+offset+.5)/dustSize,vec2(0.),vec2(1.));
            vec2 bilinear=mix(1.-f,f,offset);
            float delta=abs(distanceAt(uv)-depth);
            float weight=bilinear.x*bilinear.y*exp(-delta/max(.25,depth*.002));
            cloud+=texture2D(dustColor,uv)*weight;sum+=weight;
          }
          // No matching neighbour at a thin silhouette: preserve the solid edge.
          cloud=sum>.00001?cloud/sum:vec4(0.);
          gl_FragColor=vec4(texture2D(worldColor,vUv).rgb*(1.-cloud.a)+cloud.rgb,1.);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`,
    });
    const quad=new THREE.Mesh(new THREE.PlaneGeometry(2,2),this.material);quad.frustumCulled=false;this.scene.add(quad);
  }
  resize() {
    this.renderer.getDrawingBufferSize(this.size);const w=this.size.x,h=this.size.y;
    if(w===this.stats.width&&h===this.stats.height)return;
    const scale=Math.min(.5,960/w,540/h),dw=Math.max(1,Math.ceil(w*scale)),dh=Math.max(1,Math.ceil(h*scale));
    this.world.setSize(w,h);this.dust.setSize(dw,dh);this.material.uniforms.dustSize.value.set(dw,dh);
    Object.assign(this.stats,{width:w,height:h,dustWidth:dw,dustHeight:dh});
  }
  render(scene,camera) {
    const r=this.renderer,p=this.particles,u=p.uniforms;
    if(!this.enabled){u.uSoftDepth.value=0;r.render(scene,camera);return;}
    this.resize();
    const oldTarget=r.getRenderTarget(),auto=r.autoClear,shadow=r.shadowMap.autoUpdate;
    const color=r.getClearColor(new THREE.Color()),alpha=r.getClearAlpha(),visible=p.dust.mesh.visible;
    try{
      u.uSoftDepth.value=0;p.dust.mesh.visible=false;r.autoClear=true;
      r.setRenderTarget(this.world);r.render(scene,camera);p.dust.mesh.visible=visible;
      r.shadowMap.autoUpdate=false;r.setRenderTarget(this.dust);r.setClearColor(0,0);r.clear();
      u.uSoftDepth.value=1;u.uSceneDepth.value=this.world.depthTexture;
      u.uDustSize.value.set(this.dust.width,this.dust.height);
      u.uInvProjection.value.copy(camera.projectionMatrixInverse);u.uReversed.value=camera.reversedDepth?1:0;
      r.render(this.dustScene,camera);u.uSoftDepth.value=0;
      this.material.uniforms.invProjection.value.copy(camera.projectionMatrixInverse);this.material.uniforms.reversed.value=camera.reversedDepth?1:0;
      r.setRenderTarget(oldTarget);r.render(this.scene,this.camera);this.stats.draws++;
    }finally{u.uSoftDepth.value=0;p.dust.mesh.visible=visible;r.setRenderTarget(oldTarget);r.setClearColor(color,alpha);r.autoClear=auto;r.shadowMap.autoUpdate=shadow;}
  }
  async warmup(scene,camera) {
    const r=this.renderer,previous=r.getRenderTarget();this.resize();
    try{
      r.setRenderTarget(this.world);await r.compileAsync(scene,camera);
      r.setRenderTarget(this.dust);await r.compileAsync(this.dustScene,camera);
      r.setRenderTarget(null);await r.compileAsync(this.scene,this.camera);
      this.render(scene,camera);
    }finally{r.setRenderTarget(previous);}
  }
  dispose(){this.world.dispose();this.dust.dispose();this.material.dispose();this.scene.children[0].geometry.dispose();}
}
