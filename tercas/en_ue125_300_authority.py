"""Frozen own-contour fy300 normal authority. No builder/solver at read time."""
import copy
import hashlib
import json
import math
from pathlib import Path

PIN = '1c0505339281278b7472802dbf892fe6154c7cb56ef256ab731af3255108862f'
PATH = Path(__file__).parent/'data/en_ue125_300_normal_20261106.json'
SOURCE_PINS = {'en_ue125_300_builder.py': 'a44e7669cce771bc08525d9667739adbe5144e9f43c93ef661aa80bca2ed338d', 'en_ue_catalog_operators.py': '86f8c5d6fb78b344f89d1f4e8adce789cf2a9790d3461d965a1fad83e3e62222', 'catalog_torsion_section.py': '127b16a5a9dd2aa3d2dc16986f107e0a90b8bb022b2b358321aa6d7a8ccb61ec', 'catalogs.py': '36946b7de35df3ebc32f45881a2aab68e1777fe22e071a8b771272ba7f44cf6d', 'weak_pierin.py': '4e7b2cd4bdca6fdcd72832bc5250917e2618bd43ab9c26c4fce4066584f8ea25', 'three_girt_en_normal/en1993_normal_components.py': '2f407a8d96ff24ed5541efe7a1507cacde9a21d3729db83a8f627e54b6efc745', 'torsion_vlasov/intervals.py': 'c738ca89326f9fd9198199d6df48197f4fa5c632094d33fe13b62626f08f4168', 'core/catalogo_documentado.json': '329866603c8af367bd6060ad309e5c2600e0786c10304e7e4c12b1789a0dd211', 'data/pierin_2013_weak_reference.json': '2ab2314ce2e53cc39dbfd5e2e0d1268c599247fc24b913dffbbac76abfa5a702', 'torsion_vlasov/section.py': '28bf452fd1ccb4e7836735b55693ad0f531fced1e544e38865436a11f9852c60'}


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def validate(value):
    v=copy.deepcopy(value); digest=v.pop('content_sha256',None)
    if digest != PIN or _sha(v)!=PIN:
        raise ValueError('Outside the frozen own-contour fy300 authority')
    for relative,digest in SOURCE_PINS.items():
        if hashlib.sha256((Path(__file__).parent/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError('Derivation source snapshot changed: '+relative)
    return copy.deepcopy(value)


def read():
    return validate(json.loads(PATH.read_text()))


def require_component(certificate, axis, value, *, N=0.):
    v=validate(certificate)
    if type(N) not in (int,float) or not math.isfinite(N) or N!=0:
        raise ValueError('Only N=0 is qualified')
    if axis not in ('Mx','My') or type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Finite signed EN moment required')
    if value==0:return None
    return copy.deepcopy(v['components'][axis+('_positive' if value>0 else '_negative')])
