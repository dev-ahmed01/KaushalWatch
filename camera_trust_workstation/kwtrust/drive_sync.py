"""Direct authenticated Google Drive download with resume and source verification.

The ChatGPT connector's transfer limit does not apply to this client. OAuth
credentials are never embedded in generated reports or the Docker image.
Requires optional `google-auth` and `google-auth-oauthlib` dependencies.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote

SCOPES = ('https://www.googleapis.com/auth/drive.readonly',)
FILE_ID = re.compile(r'^[A-Za-z0-9_-]{12,150}$')
SAFE_FILENAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,130}$')


def load_manifest(path: Path)->list[dict]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('version')!='KWTRUST_DRIVE_ASSETS_V1' or not isinstance(data.get('files'),list):
        raise ValueError('Unrecognized approved Drive source manifest')
    files=data['files']
    if len(files)>150 or not files:raise ValueError('Unexpected Drive manifest size')
    names=set()
    for f in files:
        if (not FILE_ID.fullmatch(f.get('id','')) or
                not SAFE_FILENAME.fullmatch(f.get('name','')) or
                f['name'] in names or f['name'].startswith('.')):
            raise ValueError('Invalid/duplicate Drive source identifier or target filename')
        names.add(f['name'])
        if 'sha256' in f and (not re.fullmatch('[0-9a-f]{64}',f['sha256'])):
            raise ValueError('Invalid pinned SHA256')
    return files


def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as fd:
        for part in iter(lambda:fd.read(8*1024*1024),b''):
            h.update(part)
    return h.hexdigest()


def _authorize(token: Path | None, client_secret: Path | None, *,headless=False):
    try:
        from google.oauth2.credentials import Credentials
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise RuntimeError('Install optional requirements-drive.txt for Google Drive access') from e
    if token is not None and token.is_file():
        creds=Credentials.from_authorized_user_file(str(token),SCOPES)
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Stored outside repository with user-controlled permissions.
            token.parent.mkdir(parents=True,exist_ok=True)
            token.write_text(creds.to_json(),encoding='utf-8')
        if not creds.valid:raise ValueError('Saved Google credentials expired, reauthorize locally')
        return creds
    if client_secret is not None:
        if headless:raise ValueError('First OAuth login requires an interactive browser')
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as e:
            raise RuntimeError('Install google-auth-oauthlib to authorize Drive') from e
        if token is None:raise ValueError('Provide a secure --token-output path')
        flow=InstalledAppFlow.from_client_secrets_file(str(client_secret),SCOPES)
        creds=flow.run_local_server(port=0,open_browser=True)
        token.parent.mkdir(parents=True,exist_ok=True)
        token.write_text(creds.to_json(),encoding='utf-8')
        try:token.chmod(0o600)
        except OSError:pass
        return creds
    creds, _=google.auth.default(scopes=SCOPES)
    if not creds.valid:creds.refresh(Request())
    return creds


def sync_one(session, item: dict, output_dir: Path, *,chunk_size=8*1024*1024,
             retries=4, max_size=6_000_000_000)->dict:
    """Download an approved file with bounded-size streaming and resumable Range.

    Uses Drive's authenticated media endpoint, which is independent of the
    ChatGPT connector transfer. Never logs OAuth tokens or source bytes.
    """
    if not FILE_ID.fullmatch(item['id']) or not SAFE_FILENAME.fullmatch(item['name']):
        raise ValueError('Invalid Drive ID or filename')
    output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/item['name']; part=output_dir/(item['name']+'.part')
    api=f'https://www.googleapis.com/drive/v3/files/{quote(item["id"],safe="")}'
    response=session.get(api,params={'fields':'id,name,size,mimeType,md5Checksum,trashed','supportsAllDrives':'true'},timeout=40)
    response.raise_for_status(); meta=response.json()
    if meta.get('id')!=item['id'] or meta.get('trashed') or not meta.get('size'):
        raise ValueError('Drive source metadata missing/mismatched')
    size=int(meta['size'])
    if size<=0 or size>max_size:raise ValueError('Drive file exceeds approved streaming size bound')
    checksum=item.get('sha256')
    if target.is_file():
        if target.stat().st_size==size and (checksum is None or sha256_file(target)==checksum):
            return {'name':target.name,'bytes':size,'sha256':sha256_file(target),'cached':True}
        raise ValueError(f'Existing local source differs from pinned Drive file: {target.name}')
    start=part.stat().st_size if part.exists() else 0
    if start>size:raise ValueError('Partial download longer than expected source')
    attempts=0
    while start<size:
        try:
            headers={'Range':f'bytes={start}-{min(start+chunk_size,size)-1}'}
            with session.get(api,params={'alt':'media','supportsAllDrives':'true'},headers=headers,
                             timeout=150,stream=True) as resp:
                resp.raise_for_status()
                if resp.status_code!=206:
                    raise ValueError('Drive did not honor byte-range; refusing unsafe resume')
                requested=headers['Range'].removeprefix('bytes=')
                content_range=resp.headers.get('Content-Range','')
                if not content_range.startswith(f'bytes {start}-') or not content_range.endswith(f'/{size}'):
                    raise ValueError(f'Unexpected Drive Content-Range for {requested}')
                content_len=int(resp.headers.get('Content-Length','0'))
                if content_len<=0 or content_len>chunk_size:
                    raise ValueError('Unexpected chunk length')
                with part.open('ab') as fd:
                    received=0
                    for block in resp.iter_content(chunk_size=1024*1024):
                        if not block:continue
                        received+=len(block)
                        if received>content_len:raise ValueError('Drive returned too many bytes')
                        fd.write(block)
                    fd.flush();os.fsync(fd.fileno())
                if received!=content_len:raise OSError('Incomplete chunk received')
                start+=received;attempts=0
        except (OSError,ConnectionError) as exc:
            attempts+=1
            if attempts>retries:raise RuntimeError('Drive transfer interrupted after retries') from exc
            time.sleep(min(2**attempts,8))
            start=part.stat().st_size if part.exists() else 0
    if part.stat().st_size!=size:raise ValueError('Incomplete Drive binary')
    sha=sha256_file(part)
    if checksum is not None and sha!=checksum:
        raise ValueError('Drive contents differ from frozen research-source SHA-256; preserving part for forensic checking')
    os.replace(part,target)
    return {'name':target.name,'bytes':size,'sha256':sha,'cached':False}


def sync_manifest(manifest: Path,output_dir: Path, *,token=None,client_secret=None,
                  selected_group='clips',headless=False)->dict:
    files=[f for f in load_manifest(manifest) if f.get('group')==selected_group]
    if not files:raise ValueError('No approved files in selected group')
    creds=_authorize(Path(token) if token else None,Path(client_secret) if client_secret else None,headless=headless)
    from google.auth.transport.requests import AuthorizedSession
    session=AuthorizedSession(creds)
    results=[sync_one(session,f,output_dir) for f in files]
    # Report contains only source names/hashes, never credentials or source media.
    return {'status':'DRIVE_PINNED_SOURCE_SYNCED','group':selected_group,'files':results,
            'physical_camera_custody_verified':False}
