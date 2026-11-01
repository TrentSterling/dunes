// Weather presets: sky, clouds, haze, sunlight, wind and blowing sand.
import * as THREE from 'three';

export const WEATHER = {
  clear:     { label: 'Clear',         turbidity: 2.2, rayleigh: 1.1, mie: 0.004, clouds: 0.12, cloudDensity: 0.35, fog: 0.000032, sun: 1.0,  env: 1.0, wind: 1.3, blow: 0,   tint: 0 },
  hazy:      { label: 'Hazy',          turbidity: 7.0, rayleigh: 1.6, mie: 0.012, clouds: 0.10, cloudDensity: 0.30, fog: 0.00009,  sun: 0.85, env: 1.15, wind: 2.5, blow: 0.1, tint: 0.25 },
  cloudy:    { label: 'Partly cloudy', turbidity: 3.0, rayleigh: 1.2, mie: 0.005, clouds: 0.45, cloudDensity: 0.55, fog: 0.00004,  sun: 0.95, env: 1.1, wind: 3.0, blow: 0.1, tint: 0 },
  overcast:  { label: 'Overcast',      turbidity: 6.0, rayleigh: 1.0, mie: 0.008, clouds: 0.95, cloudDensity: 0.85, fog: 0.00007,  sun: 0.28, env: 1.9, wind: 4.0, blow: 0.15, tint: 0.1 },
  windy:     { label: 'Windy',         turbidity: 4.5, rayleigh: 1.3, mie: 0.008, clouds: 0.25, cloudDensity: 0.45, fog: 0.00008,  sun: 0.9,  env: 1.1, wind: 9.0, blow: 0.6, tint: 0.35 },
  sandstorm: { label: 'Sandstorm',     turbidity: 12,  rayleigh: 2.0, mie: 0.02,  clouds: 0.6,  cloudDensity: 0.8,  fog: 0.0042,   sun: 0.35, env: 1.4, wind: 15,  blow: 1.0, tint: 1.0 },
};

const DUST = new THREE.Color(0.78, 0.62, 0.44);

export class Weather {
  constructor({ scene, sky, particles }) {
    this.scene = scene; this.sky = sky; this.particles = particles;
    this.name = 'clear';
    this.p = { ...WEATHER.clear };
    this.windDir = Math.PI * 0.35; // wind blows toward the ESE (prevailing W/NW wind at Glamis)
    this.windScale = 1;
    this.blowAcc = 0;
  }

  set(name) {
    if (!WEATHER[name]) name = 'clear';
    this.name = name;
    this.p = { ...WEATHER[name] };
    const su = this.sky.material.uniforms;
    su.turbidity.value = this.p.turbidity; su.rayleigh.value = this.p.rayleigh; su.mieCoefficient.value = this.p.mie;
    su.cloudCoverage.value = this.p.clouds; su.cloudDensity.value = this.p.cloudDensity;
    this.scene.fog.density = this.p.fog;
    this.particles.uniforms.uFogDensity.value = this.p.fog;
    this.applyWind();
  }

  get windSpeed() { return this.p.wind * this.windScale; }

  applyWind() {
    const w = this.windSpeed;
    this.particles.wind = [Math.sin(this.windDir) * w, Math.cos(this.windDir) * w];
  }

  // after the time-of-day lighting is set, blend in the weather's haze colour
  tintFog(fogColor) {
    fogColor.lerp(DUST, this.p.tint * 0.85);
    if (this.p.tint >= 1) {
      // in a sandstorm the sky disappears into the dust
      this.sky.visible = false;
      this.scene.background = fogColor.clone();
    } else {
      this.sky.visible = true;
      this.scene.background = null;
    }
    return fogColor;
  }

  // blowing sand: streamers of dust skimming the ground around the camera
  update(dt, camera, terrain) {
    const amt = this.p.blow * Math.min(1.5, this.windScale);
    if (amt <= 0) return;
    const P = this.particles, w = this.windSpeed;
    const wx = Math.sin(this.windDir), wz = Math.cos(this.windDir);
    this.blowAcc += dt * amt * 140 * P.emitScale;
    let guard = 0;
    while (this.blowAcc >= 1 && guard++ < 400) {
      this.blowAcc -= 1;
      // spawn upwind so the dust drifts through the view
      const r = 8 + Math.random() * 90, a = Math.random() * Math.PI * 2;
      const x = camera.position.x + Math.sin(a) * r - wx * 30, z = camera.position.z + Math.cos(a) * r - wz * 30;
      const gy = terrain.height(x, z);
      const big = Math.random() < amt * 0.5;
      P.dust.spawn(x, gy + 0.2 + Math.random() * (big ? 6 : 1.2), z,
        wx * w * (0.7 + Math.random() * 0.5), 0.2 + Math.random() * 0.6, wz * w * (0.7 + Math.random() * 0.5),
        3 + Math.random() * 4, big ? 3 + Math.random() * 4 : 0.8 + Math.random() * 1.2, 0.6 + Math.random(), 0.9 + Math.random() * 0.2, gy,
        (big ? 0.08 : 0.12) * Math.min(1, amt + 0.3));
    }
    // fine saltating grains (only near the camera, they're tiny)
    let g = dt * amt * 900 * P.emitScale;
    g = Math.floor(g) + (Math.random() < g % 1 ? 1 : 0);
    for (let i = 0; i < g; i++) {
      const r = 2 + Math.random() * 25, a = Math.random() * Math.PI * 2;
      const x = camera.position.x + Math.sin(a) * r - wx * 6, z = camera.position.z + Math.cos(a) * r - wz * 6;
      const gy = terrain.height(x, z);
      P.grains.spawn(x, gy + 0.02, z, wx * w * 0.8, 0.5 + Math.random() * 1.5, wz * w * 0.8,
        0.6 + Math.random() * 0.8, 0.008 + Math.random() * 0.015, 0, 0.9 + Math.random() * 0.2, gy, 0.8);
    }
  }
}
