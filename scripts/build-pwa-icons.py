"""Package the shared launcher foreground for installed web-app icons."""
import argparse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=ROOT / 'client/assets/brand/lamanotes-lamaui.webp')
parser.add_argument('--revision', default='notes-n1')
args = parser.parse_args()
source = Image.open(args.source).convert('RGBA')

def icon(size):
    canvas = Image.new('RGBA', (size, size), '#e7f1f5')
    mark = source.crop(source.getchannel('A').getbbox())
    mark.thumbnail((round(size * .64), round(size * .72)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(mark, ((size-mark.width)//2, (size-mark.height)//2))
    return canvas.convert('RGB')

public = ROOT / 'client/public'
for size in (192, 512):
    icon(size).save(public / f'lamanotes-icon-light-{size}.png')
    icon(size).save(public / f'lamanotes-icon-{size}.png')
    icon(size).save(public / f'lamanotes-{args.revision}-{size}.png')
icon(180).save(public / 'apple-touch-icon.png')
for size in (16, 32, 64):
    icon(size).save(public / f'favicon-{size}.png')
icon(256).save(public / 'favicon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(256,256)])
