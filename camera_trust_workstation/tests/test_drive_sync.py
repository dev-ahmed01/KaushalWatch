import hashlib,json
from pathlib import Path
import pytest
from kwtrust.drive_sync import load_manifest,sha256_file,sync_one


def test_manifest_rejects_path_traversal_and_untrusted_ids(tmp_path):
    p=tmp_path/'m.json';p.write_text(json.dumps({'version':'KWTRUST_DRIVE_ASSETS_V1','files':[{'name':'../secret.env','id':'ABCDEFGHIJKLMN1234567890'}]}))
    with pytest.raises(ValueError):load_manifest(p)
    p.write_text(json.dumps({'version':'KWTRUST_DRIVE_ASSETS_V1','files':[{'name':'source.avi','id':'ABCDEFGHIJKLMN1234567890'}]}))
    assert len(load_manifest(p))==1


class FakeResponse:
    status_code=206
    def __init__(self,b,*,n,headers=None):self.b=b;self.n=n;self.headers=headers or {}
    def json(self):return self.b
    def raise_for_status(self):return None
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def iter_content(self,chunk_size):
        for i in range(0,len(self.b),chunk_size):yield self.b[i:i+chunk_size]

class FakeSession:
    def __init__(self,data):self.data=data;self.ranges=[]
    def get(self,url,params,**kwargs):
        if params.get('alt')!='media':
            return FakeResponse({'id':'ABCDEFGHIJKLMN1234567890','size':str(len(self.data)),'name':'source.avi'},n=0)
        rng=kwargs['headers']['Range']
        self.ranges.append(rng)
        a,b=(int(i) for i in rng.removeprefix('bytes=').split('-'))
        b=min(b,len(self.data)-1)
        data=self.data[a:b+1]
        return FakeResponse(data,n=len(data),headers={'Content-Length':str(len(data)),
                             'Content-Range':f'bytes {a}-{b}/{len(self.data)}'})


def test_chunked_resume_verified_binary(tmp_path):
    payload=bytes(range(256))*50
    s=FakeSession(payload)
    target={'id':'ABCDEFGHIJKLMN1234567890','name':'source.avi',
            'sha256':hashlib.sha256(payload).hexdigest()}
    folder=tmp_path/'clips';folder.mkdir()
    (folder/'source.avi.part').write_bytes(payload[:4096])
    out=sync_one(s,target,folder,chunk_size=4096)
    assert out['bytes']==len(payload)
    assert (folder/'source.avi').read_bytes()==payload
    assert s.ranges[0].startswith('bytes=4096-')
    assert sync_one(s,target,folder)['cached'] is True
    assert sha256_file(folder/'source.avi')==target['sha256']


def test_mismatched_hash_rejected_and_keeps_untrusted_part(tmp_path):
    data=b'a'*100
    s=FakeSession(data)
    item={'id':'ABCDEFGHIJKLMN1234567890','name':'source.avi','sha256':'0'*64}
    with pytest.raises(ValueError,match='frozen research-source'):
        sync_one(s,item,tmp_path,chunk_size=50)
    assert not (tmp_path/'source.avi').exists()
    assert (tmp_path/'source.avi.part').exists()


def test_reject_unhonored_ranges(tmp_path):
    s=FakeSession(b'abc')
    orig=s.get
    def get(*a,**k):
        r=orig(*a,**k)
        if k.get('params',{}).get('alt')=='media':r.status_code=200
        return r
    s.get=get
    with pytest.raises(ValueError,match='honor byte-range'):
        sync_one(s,{'id':'ABCDEFGHIJKLMN1234567890','name':'source.avi'},tmp_path)
