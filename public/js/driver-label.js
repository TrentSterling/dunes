import * as THREE from 'three';

const view = new THREE.Vector3();
// Test in view space: reversed depth puts points behind the eye at negative NDC z.
// The caller refreshes camera matrices after moving the camera this frame.
export function placeDriverLabel(label, position, camera, show, text, width, height) {
  label.visible = false;
  if (!show) return;
  view.copy(position); view.y += 2.2;
  view.applyMatrix4(camera.matrixWorldInverse);
  if (view.z >= -camera.near || view.z <= -camera.far) return;
  view.applyMatrix4(camera.projectionMatrix);
  if (!Number.isFinite(view.x + view.y) || Math.abs(view.x) > 1 || Math.abs(view.y) > 1) return;
  label.visible = true; label.text = text;
  label.x = (view.x * .5 + .5) * width;
  label.y = (-view.y * .5 + .5) * height;
}
