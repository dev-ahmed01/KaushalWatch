"""One-time Google Drive OAuth then resumable source downloads, no manual uploads."""
import argparse,json
from pathlib import Path
from kwtrust.drive_sync import sync_manifest
p=argparse.ArgumentParser()
p.add_argument('--manifest',type=Path,default=Path('drive-sources.json'))
p.add_argument('--output-dir',type=Path,default=Path('local_drive_sources'))
p.add_argument('--token',type=Path,default=Path('.private/drive-token.json'))
p.add_argument('--client-secret',type=Path)
p.add_argument('--group',choices=['clips','full-videos','annotations'],default='clips')
p.add_argument('--headless',action='store_true')
a=p.parse_args()
print(json.dumps(sync_manifest(a.manifest,a.output_dir,token=a.token,client_secret=a.client_secret,selected_group=a.group,headless=a.headless),indent=2))
