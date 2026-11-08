"""Exact historical test oracle; never synthesizes a commit or production source."""
import hashlib
import json
from pathlib import Path
import subprocess

REF = '89785b61c2b01a7d5ec350b00c10fc5e9bc8e90d'
PATH = 'tercas/torsion_vlasov/section.py'
SHA256 = 'a0fbb76a1051879aa67446586a2100e6015344a9b636826321ecc1af5d4f3797'
BLOB_SHA1 = '37371fb0e43790c11f32c16e23ea41949182546d'
SIZE = 9170
URL = 'https://github.com/lucasmec28/tercas/blob/' + REF + '/' + PATH
FIXTURE = Path(__file__).parent / 'fixtures' / 'historical_section_897'


def verify(raw):
    if (len(raw) != SIZE or hashlib.sha256(raw).hexdigest() != SHA256
            or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != BLOB_SHA1):
        raise AssertionError('Historical oracle bytes differ from the independently recovered pinned source')
    return raw


def load():
    source=json.loads((FIXTURE/'source.json').read_text())
    if source != dict(encoding='base64',sha=BLOB_SHA1,display_url=URL,
                      display_title='section.py',sha256=SHA256,bytes=SIZE,ref=REF):
        raise AssertionError('Historical oracle provenance differs from the pinned source')
    result=subprocess.run(['git','show',REF+':'+PATH],capture_output=True,
                          cwd=Path(__file__).resolve().parents[1],check=False)
    if result.returncode == 0:
        return verify(result.stdout)
    # Do not mask permission, executable, repository, or other Git failures.
    message=result.stderr.decode('utf-8',errors='replace')
    missing=("exists on disk, but not in" in message or
             "does not exist in" in message or
             "invalid object name" in message or "bad object" in message)
    if result.returncode != 128 or not missing:
        raise subprocess.CalledProcessError(result.returncode,result.args,
                                            output=result.stdout,stderr=result.stderr)
    return verify((FIXTURE/'section.py').read_bytes())
