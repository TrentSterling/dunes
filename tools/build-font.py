"""Build the checked-in SDF glyph atlas. No browser canvas text rasterization."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt
from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1]
folder = root / 'assets/fonts'
source = folder / 'BarlowCondensed-Bold.ttf'
size, pad, width = 64, 10, 2048
font = ImageFont.truetype(str(source), size)
codes = sorted(c for c in TTFont(source).getBestCmap() if c >= 32 and c < 65536)
rows, glyphs = [], {}
x = y = row_height = 0
for code in codes:
    char = chr(code)
    left, top, right, bottom = font.getbbox(char, anchor='ls')
    w, h = max(1, right-left)+pad*2, max(1, bottom-top)+pad*2
    if x+w > width:
        x, y, row_height = 0, y+row_height, 0
    mask = Image.new('L', (w, h))
    ImageDraw.Draw(mask).text((pad-left, pad-top), char, font=font, fill=255, anchor='ls')
    pixels = np.asarray(mask) > 127
    if pixels.any():
        field = distance_transform_edt(pixels)-distance_transform_edt(~pixels)
        sdf = np.clip(128+field*(127/pad), 0, 255).astype(np.uint8)
    else:
        sdf = np.zeros((h,w),dtype=np.uint8)
    rows.append((Image.fromarray(sdf),x,y))
    glyphs[char] = dict(x=x,y=y,w=w,h=h,advance=font.getlength(char),bx=left-pad,by=top-pad)
    x += w
    row_height = max(row_height,h)
height = 1 << (y+row_height-1).bit_length()
atlas = Image.new('L',(width,height))
for glyph,gx,gy in rows:
    atlas.paste(glyph,(gx,gy))
atlas.save(folder/'barlow-sdf.png',optimize=True)
(folder/'barlow-sdf.json').write_text(json.dumps(dict(font='Barlow Condensed Bold',size=size,range=pad,width=width,height=height,glyphs=glyphs),ensure_ascii=True,separators=(',',':'))+'\n')
print(f'SDF atlas: {len(glyphs)} glyphs, {width} x {height}')
