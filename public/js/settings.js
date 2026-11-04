// In-game menu (M): Controls, Key bindings, Quality, Weather, Teleport and Game tabs built from a schema.
// Settings are saved in the browser so they stick between sessions.

import { PLACES } from './places.js';

const KEY = 'glamis-settings-v1';

export const DEFAULTS = {
  quality: 'ultra', renderScale: 1, shadows: 'ultra', particles: 1,
  weather: 'clear', tod: 16.8, night: false, wind: 1,
  autoTrans: true, wheelieControl: true, steerAssist: true, steerSens: 1, volume: 0.8, camMode: 0, cockpitFov: 78, radarCockpit: 'hud', liveMirrors: true, driverArms: false, invertLook: false,
  car: 'pro',
  gravity: 9.81, grip: 1, softness: 1, sandTex: 'all',
  aiCount: 6, aiSkill: 1, radar: true, radarRange: 600, labels: true, showHelp: false,
};

// Settings that change the shared world: when one player changes them online,
// everyone's game follows. (Your car choice and per-PC display/sound/camera stay yours.)
export const GLOBAL_KEYS = ['weather', 'tod', 'night', 'wind', 'gravity', 'grip', 'softness', 'wheelieControl', 'steerAssist', 'aiCount', 'aiSkill'];

export function loadSettings() {
  let s = {};
  try { s = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { s = {}; }
  // the photo sand texture went from a test patch to the whole map
  if (s.sandTexV !== 2) { s.sandTex = 'all'; s.sandTexV = 2; }
  // the new GLX pro rail: start everyone in it once
  if (s.proCarV !== 1) { s.car = 'pro'; s.proCarV = 1; }
  // cockpit field of view: back to the wide 78 deg default (58 / 68 were test defaults, never picked by a player)
  if (s.cockpitFovV !== 3) { if (s.cockpitFov === undefined || [58, 68].includes(Number(s.cockpitFov))) s.cockpitFov = 78; s.cockpitFovV = 3; }
  return { ...DEFAULTS, ...s };
}
export function saveSettings(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode */ } }

const fmtTod = (h) => { const hh = Math.floor(h), mm = Math.round((h % 1) * 60); const ap = hh >= 12 ? 'PM' : 'AM'; return `${((hh + 11) % 12) + 1}:${String(mm).padStart(2, '0')} ${ap}`; };

export const SCHEMA = [
  { tab: 'Controls', items: [
    { key: 'autoTrans', label: 'Gearbox', type: 'choice', options: [[true, 'Automatic'], [false, 'Manual (Q / E)']] },
    { key: 'wheelieControl', label: 'Wheelie control', type: 'choice', options: [[true, 'On'], [false, 'Off (full send)']], hint: 'Key V' },
    { key: 'steerAssist', label: 'Countersteer assist', type: 'choice', options: [[true, 'On'], [false, 'Off']], hint: 'Key G' },
    { key: 'steerSens', label: 'Steering speed', type: 'range', min: 0.5, max: 1.8, step: 0.05, fmt: v => Math.round(v * 100) + '%' },
    { key: 'camMode', label: 'Camera', type: 'choice', options: [[0, 'Chase'], [1, 'Far'], [2, 'Cockpit'], [3, 'Hood'], [4, 'Side']], hint: 'Key C' },
    { key: 'cockpitFov', label: 'Cockpit field of view', type: 'range', min: 60, max: 90, step: 1, fmt: v => `${v}° (${Math.round(2 * Math.atan(Math.tan(v * Math.PI / 360) * 16 / 9) * 180 / Math.PI)}° wide)`, hint: 'Vertical angle of the cockpit camera' },
    { key: 'invertLook', label: 'Invert look up/down', type: 'choice', options: [[false, 'Off'], [true, 'On']] },
    { key: 'volume', label: 'Sound volume', type: 'range', min: 0, max: 1, step: 0.05, fmt: v => Math.round(v * 100) + '%' },
    { type: 'keys', rows: [
      ['Mouse', 'Drag to look around, scroll to zoom'], ['M or Esc', 'This menu (controller: Start)'],
      ['Controller', 'Right stick looks around. Change any key or button in the Key bindings tab.'],
    ] },
  ] },
  { tab: 'Key bindings', items: [{ type: 'bindings' }] },
  { tab: 'Quality', items: [
    { key: 'quality', label: 'Graphics preset', type: 'choice', options: [['ultra', 'Ultra'], ['high', 'High'], ['low', 'Low']], hint: 'Terrain detail and tire-track resolution. Reloads the game.', reload: true },
    { key: 'renderScale', label: 'Render resolution', type: 'range', min: 0.5, max: 2, step: 0.25, fmt: v => Math.round(v * 100) + '%', hint: 'Above 100% supersamples for the sharpest image.' },
    { key: 'shadows', label: 'Shadows', type: 'choice', options: [['off', 'Off'], ['low', 'Low'], ['high', 'High'], ['ultra', 'Ultra']] },
    { key: 'sandTex', label: 'Photo sand textures', type: 'choice', options: [['off', 'Off'], ['patch', 'Test patch at start'], ['all', 'Everywhere']], hint: 'Poly Haven scanned sand. Turn off for slower PCs.' },
    { key: 'liveMirrors', label: 'Live mirrors (cockpit)', type: 'choice', options: [[true, 'On'], [false, 'Off']], hint: 'Real reflections in the rear-view mirrors. Turn off for more fps in the cockpit view.' },
    { key: 'driverArms', label: 'Driver arms (cockpit)', type: 'choice', options: [[true, 'Show'], [false, 'Hide']], hint: 'The driver\'s arms and gloves on the steering wheel in the driver\'s seat view.' },
    { key: 'particles', label: 'Sand and dust amount', type: 'range', min: 0.25, max: 2, step: 0.25, fmt: v => Math.round(v * 100) + '%' },
  ] },
  { tab: 'Weather', items: [
    { key: 'weather', label: 'Weather', hint: 'Weather, time and wind are shared with all players.', type: 'choice', options: [['clear', 'Clear'], ['hazy', 'Hazy'], ['cloudy', 'Partly cloudy'], ['overcast', 'Overcast'], ['windy', 'Windy'], ['sandstorm', 'Sandstorm']] },
    { key: 'night', label: 'Night mode', type: 'choice', options: [[false, 'Off'], [true, 'On (moonlight, N for light bars)']], hint: 'Key T steps through the day into night' },
    { key: 'tod', label: 'Time of day', type: 'range', min: 6.2, max: 19.4, step: 0.1, fmt: fmtTod, lazy: true },
    { key: 'wind', label: 'Wind strength', type: 'range', min: 0, max: 2, step: 0.1, fmt: v => Math.round(v * 100) + '%' },
  ] },
  { tab: 'Teleport', items: [
    { type: 'actions', key: 'tp', label: 'Hill climbs', list: PLACES.filter(p => p.kind === 'hill').map(p => [p.id, p.name]) },
    { type: 'actions', key: 'tp', label: 'Bowls', list: PLACES.filter(p => p.kind === 'bowl').map(p => [p.id, p.name]) },
    { type: 'actions', key: 'tp', label: 'Camps and start', list: PLACES.filter(p => p.kind === 'camp' || p.kind === 'start').map(p => [p.id, p.name]),
      hint: 'Real Glamis spots from the BLM map. Hill climbs start you at the bottom facing up. Key L jumps to the next one.' },
  ] },
  { tab: 'Game', items: [
    { key: 'gravity', label: 'Gravity', type: 'range', min: 1, max: 20, step: 0.01, fmt: v => `${v.toFixed(2)} m/s² · ${(v / 9.81).toFixed(2)} g`,
      presets: [[1.62, 'Moon'], [3.71, 'Mars'], [9.81, 'Earth'], [14.7, '1.5 g']], hint: 'Arrow keys fine-tune by 0.01. Shared with all players.' },
    { key: 'softness', label: 'Sand softness', type: 'range', min: 0.4, max: 2, step: 0.05, fmt: v => Math.round(v * 100) + '%', hint: 'How deep tires sink. Shared with all players.' },
    { key: 'grip', label: 'Sand grip', type: 'range', min: 0.5, max: 1.5, step: 0.01, fmt: v => Math.round(v * 100) + '%', hint: 'Lower lets the rails slide more. Shared with all players.' },
    { key: 'car', label: 'Your sandrail', type: 'choice', options: [['pro', 'GLX pro'], ['pro2', 'GLX pro 2'], ['flamerail', 'Flame rail'], ['black', 'Black'], ['blue', 'Blue'], ['green', 'Green'], ['silver', 'Silver'], ['yellow', 'Yellow'], ['trax', 'Trax'], ['classic', 'Classic']], hint: 'Switch rides without leaving the dunes.' },
    { key: 'aiCount', label: 'Computer sandrails', type: 'range', min: 0, max: 12, step: 1, fmt: v => String(v) },
    { key: 'aiSkill', label: 'Computer driving', type: 'choice', options: [[0.75, 'Cruising'], [1, 'Normal'], [1.3, 'Aggressive']] },
    { key: 'radar', label: 'Radar', type: 'choice', options: [[true, 'On'], [false, 'Off']] },
    { key: 'radarCockpit', label: 'Radar in the cockpit', type: 'choice', options: [['hud', 'Screen corner'], ['dash', 'Dash screen only']], hint: 'Cars with a dash GPS screen (GLX pro) always show the map there too' },
    { key: 'radarRange', label: 'Radar range', type: 'choice', options: [[300, '300 m'], [600, '600 m'], [1200, '1.2 km'], [2500, '2.5 km']] },
    { key: 'labels', label: 'Name tags', type: 'choice', options: [[true, 'On'], [false, 'Off']] },
    { key: 'showHelp', label: 'Help panel', type: 'choice', options: [[true, 'On'], [false, 'Off']] },
  ] },
];
