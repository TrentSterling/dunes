// Well-known Glamis spots for the teleport menu (BLM landmark list, WGS 84).
// kind: 'hill' = start at the bottom facing up the climb, 'bowl' = start in the
// bottom of the bowl, 'camp' = park on the spot.
export const PLACES = [
  { id: 'comp', name: 'Competition Hill', kind: 'hill', lat: 32.984200, lon: -115.127517 },
  { id: 'olds', name: 'Oldsmobile Hill', kind: 'hill', lat: 32.962783, lon: -115.098883 },
  { id: 'brawley', name: 'Brawley Slide', kind: 'hill', lat: 32.944200, lon: -115.079917 },
  { id: 'lizard', name: 'Lizard Hill', kind: 'hill', lat: 32.927933, lon: -115.068067 },
  { id: 'china', name: 'China Wall', kind: 'hill', lat: 32.911750, lon: -115.040867 },
  { id: 'wall', name: 'The Wall', kind: 'hill', lat: 32.889833, lon: -115.041350 },
  { id: 'dogleg', name: 'Dogleg', kind: 'bowl', lat: 32 + 58 / 60 + 51 / 3600, lon: -(115 + 6 / 60 + 54 / 3600) },
  { id: 'fillers', name: "Filler's Hole", kind: 'bowl', lat: 32 + 58 / 60 + 22 / 3600, lon: -(115 + 6 / 60 + 39 / 3600) },
  { id: 'osborne', name: 'Osborne Overlook', kind: 'camp', lat: 32.983033, lon: -115.132900 },
  { id: 'glamisflats', name: 'Glamis Flats', kind: 'camp', lat: 32.992217, lon: -115.079150 },
  { id: 'gecko', name: 'Gecko Loop', kind: 'camp', lat: 32.939717, lon: -115.142767 },
  { id: 'start', name: 'Start bowl', kind: 'start' },
];

// map metres: origin lat 32.955 N, lon 115.11 W, +x east, -z north
export function placeXZ(p, meta) {
  const lat0 = meta?.lat0 ?? 32.955, lon0 = meta?.lon0 ?? -115.11;
  return { x: (p.lon - lon0) * Math.cos(lat0 * Math.PI / 180) * 111320, z: -(p.lat - lat0) * 110900 };
}
