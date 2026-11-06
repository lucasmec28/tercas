"""Read-only compatibility audit; takes the normal inventory path explicitly."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tercas import en_ue_shear as s
source=Path(sys.argv[1]);normal=json.loads(source.read_text())
pairs=[]
for index in s.available_indices():
    shear=s.qualified_reference(index)
    binding=normal['entries'][str(index)]['source_binding']
    s.validate_saved(shear,binding)
    pairs.append(dict(catalog_index=index,catalog_id=binding['catalog_id'],
        nominal_identity_sha256=binding['nominal_identity_sha256'],nodes_sha256=binding['nodes_sha256'],
        shear_reference_sha256=shear['content_sha256'],
        normal_reference_sha256=normal['entries'][str(index)]['qualified_content_sha256']))
result=dict(compatible_count=len(pairs),binding_keys=list(s.BINDING_KEYS),
    normal_inventory_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    normal_inventory_content_sha256=normal['content_sha256'],
    shear_inventory_content_sha256=s.INVENTORY_SHA256,
    scope='Identity/material compatibility only; neither authority grants the other component',pairs=pairs)
(ROOT/'qa/en_ue_shear/normal_identity_compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
print('Compatible nominal/node/material identities:',len(pairs))
