// Night sky over the dunes: deep blue horizon glow, thousands of stars, the
// Milky Way band and a bright moon that lights the sand.
import * as THREE from 'three';

export const MOON_DIR = new THREE.Vector3(-0.45, 0.62, -0.64).normalize();

export function makeNightSky() {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uMoon: { value: MOON_DIR.clone() }, uTime: { value: 0 } },
    vertexShader: /* glsl */`
      varying vec3 vDir;
      void main(){ vDir = normalize((modelMatrix * vec4(position, 0.0)).xyz); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */`
      uniform vec3 uMoon; uniform float uTime; varying vec3 vDir;
      float h3(vec3 p){ p = fract(p*0.3183099 + 0.1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
      float stars(vec3 d, float scale, float thresh){
        vec3 c = floor(d*scale); vec3 f = d*scale - c;
        float r = h3(c);
        if (r < thresh) return 0.0;
        vec3 sp = vec3(h3(c+7.1), h3(c+3.3), h3(c+5.9))*0.7 + 0.15;
        float dd = length(f - sp);
        float tw = 0.75 + 0.25*sin(uTime*(2.0 + 5.0*h3(c+1.7)) + r*40.0);
        return smoothstep(0.09, 0.0, dd) * (r - thresh)/(1.0 - thresh) * tw;
      }
      void main(){
        vec3 d = normalize(vDir);
        float up = clamp(d.y, -0.2, 1.0);
        vec3 col = mix(vec3(0.020, 0.030, 0.060), vec3(0.003, 0.006, 0.016), smoothstep(0.0, 0.6, up));
        col += vec3(0.05, 0.06, 0.09) * exp(-max(up, 0.0)*9.0);          // faint glow on the horizon
        // Milky Way: a soft band of dust and many faint stars
        vec3 gal = normalize(vec3(0.35, 0.25, 0.9));
        float band = exp(-pow(dot(d, gal)/0.16, 2.0));
        float neb = h3(floor(d*60.0))*0.5 + h3(floor(d*23.0))*0.5;
        col += vec3(0.030, 0.030, 0.042) * band * (0.6 + 0.6*neb);
        float s = stars(d, 180.0, 0.985) * 1.6 + stars(d, 420.0, 0.99 - 0.03*band) * 0.9;
        col += vec3(0.95, 0.97, 1.0) * s * smoothstep(-0.02, 0.08, d.y);
        // moon disc with a little shading and a halo
        float md = dot(d, uMoon);
        float disc = smoothstep(0.99985, 0.99992, md);
        col = mix(col, vec3(1.25, 1.22, 1.15) * (0.9 + 0.1*h3(floor(d*900.0))), disc);
        col += vec3(0.20, 0.23, 0.30) * pow(max(md, 0.0), 300.0) + vec3(0.04, 0.05, 0.07) * pow(max(md, 0.0), 12.0);
        col *= smoothstep(-0.25, 0.0, d.y) * 0.85 + 0.15;
        gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    side: THREE.BackSide, depthWrite: false, fog: false,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), mat);
  mesh.scale.setScalar(120000);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1;
  mesh.visible = false;
  return mesh;
}
