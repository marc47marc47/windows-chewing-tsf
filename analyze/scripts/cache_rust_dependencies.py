"""Populate a workspace-only Cargo vendor cache from locked, hash-verified crates."""
import concurrent.futures
import hashlib
import io
import json
import tarfile
import tomllib
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[2]
vendor=root/'.cache/rust-vendor'
vendor.mkdir(parents=True,exist_ok=True)
(vendor.parent/'vendor-config.toml').write_text(
    '[source.crates-io]\nreplace-with = "local-vendor"\n[source.local-vendor]\n'
    + 'directory = ' + json.dumps(vendor.as_posix()) + '\n', encoding='utf-8')
packages={}
for lock in (root/'Cargo.lock',root/'libchewing/Cargo.lock'):
    for p in tomllib.loads(lock.read_text())['package']:
        if p.get('source','').startswith('registry+'):
            packages[p['name'],p['version']]=p

def fetch(p):
    name,version=p['name'],p['version']
    destination=vendor/f'{name}-{version}'
    if (destination/'.cargo-checksum.json').exists(): return None
    request=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with request.open(f'https://static.crates.io/crates/{name}/{name}-{version}.crate',timeout=45) as response:
        archive=response.read()
    if hashlib.sha256(archive).hexdigest()!=p['checksum']:
        raise ValueError(f'Checksum mismatch: {name} {version}')
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
        tar.extractall(vendor,filter='data')
    checksums={str(f.relative_to(destination)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest()
               for f in destination.rglob('*') if f.is_file() and f.name!='.cargo-checksum.json'}
    (destination/'.cargo-checksum.json').write_text(json.dumps(dict(files=checksums,package=p['checksum'])))
    return f'{name} {version}'

errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    futures={pool.submit(fetch,p):p for p in packages.values()}
    for future in concurrent.futures.as_completed(futures):
        p=futures[future]
        try:
            result=future.result()
            if result: print(result,flush=True)
        except Exception as error:
            errors.append(dict(name=p['name'],version=p['version'],error=str(error)))
report=dict(packages=len(packages),errors=errors)
(root/'analyze/rust-dependency-cache.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
if errors: raise SystemExit(1)
