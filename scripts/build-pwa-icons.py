"""Import the shared Notes mark and its versioned web/Windows icons."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
args = parser.parse_args()
source = args.source_root.resolve()
exporter = source.parents[3] / 'scripts/export-web-brand.py'
public = ROOT / 'client/public'
output = public / 'brand'
record = json.loads(subprocess.check_output([sys.executable, str(exporter), '--source-root', str(source),
    '--app', 'notes', '--output-dir', str(output)], text=True))
files = record['files']
for name in ('lamanotes-lamaui.webp', 'lamanotes-home-mark.webp'):
    shutil.copy2(output / files['mark'], ROOT / 'client/assets/brand' / name)
for size in (192, 512):
    for alias in (f'lamanotes-icon-{size}.png', f'lamanotes-icon-light-{size}.png'):
        shutil.copy2(output / files['icons'][str(size)], public / alias)
shutil.copy2(output / files['apple'], public / 'apple-touch-icon.png')
for size in (16, 32, 64):
    shutil.copy2(output / files['favicons'][str(size)], public / f'favicon-{size}.png')
shutil.copy2(output / files['ico'], public / 'favicon.ico')
shutil.copy2(output / files['ico'], ROOT / 'windows-client/lamanotes.ico')
manifest_path = public / 'site.webmanifest'
raw_manifest = manifest_path.read_text()
manifest = json.loads(raw_manifest)
manifest['icons'] = [{'src': 'brand/' + files['icons'][str(size)], 'sizes': f'{size}x{size}',
    'type': 'image/png', 'purpose': 'any'} for size in (192, 512)]
manifest['icons'].append({'src': 'brand/' + files['maskable'], 'sizes': '512x512',
    'type': 'image/png', 'purpose': 'maskable'})
icons = json.dumps(manifest['icons'], indent=2).replace('\n', '\n  ')
updated, count = re.subn(r'(?s)("icons": )\[.*?\](,\n  "theme_color")', lambda match: match[1] + icons + match[2], raw_manifest)
if count != 1:
    raise ValueError('The Notes icon section was not found')
manifest_path.write_text(updated)
(ROOT / 'client/assets/brand/lamaui-source.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
