"""Repeatable Kestrel build and render entry point. Usage: python tools/jet_pipeline.py build|render"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import vehicle_pipeline as pipeline

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'blender/kestrel'
OUTPUT=ROOT/'artifacts/vehicles/kestrel'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['build','render'])
    ap.add_argument('--blender'); ap.add_argument('--views',default='hero,side,top,rear')
    args=ap.parse_args()
    blender=pipeline.blender_path(args.blender)
    pipeline.OUTPUT=OUTPUT
    if args.action=='build':
        pipeline.run_blender(blender,SOURCE/'build.py',['--output',OUTPUT],'build.log')
        manifest=json.loads((OUTPUT/'kestrel.json').read_text())
        assert manifest['triangles']>10000 and len(manifest['articulated'])>=10
        target=ROOT/'assets/kestrel'; target.mkdir(exist_ok=True)
        for name in ['kestrel.glb','kestrel.json']: shutil.copy2(OUTPUT/name,target/name)
        print(json.dumps({k:manifest[k] for k in ['triangles','meshGroups','glbBytes','dimensions']},indent=2))
        print('Editable scene:',OUTPUT/'kestrel.blend')
        print('Viewer: http://localhost:5189/jet.html')
    else:
        pipeline.run_blender(blender,SOURCE/'render.py',
            ['--blend',OUTPUT/'kestrel.blend','--output',OUTPUT/'renders','--views',args.views],'render.log')

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('ERROR:',e,file=sys.stderr); sys.exit(1)
