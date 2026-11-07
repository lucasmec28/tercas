"""Current nominal geometry authority keyed by content, never object identity."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from .en_ue125_300_authority import _sha


def _source_key():
    root=Path(__file__).parent
    names=['en_ue_family_geometry.py','catalog_torsion_section.py','catalogs.py','weak_pierin.py']
    names += [str(p.relative_to(root)) for p in sorted((root/'torsion_vlasov').glob('*.py'))]
    names += [str(p.relative_to(root)) for p in sorted(root.rglob('*.json'))]
    return _sha({n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names})


@lru_cache(maxsize=128)
def _prepared(index,source_key):
    from .catalog_torsion_section import prepare
    return json.dumps(prepare(index)['section'],sort_keys=True,separators=(',',':'),allow_nan=False)


def section(index):
    return json.loads(_prepared(index,_source_key()))
