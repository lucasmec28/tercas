"""Read-only coordinate anchors for qualified, explicitly adopted contours.

R01 values come from own_properties in data/torsion_profiles, whose hashes
are enforced by torsion_study.section_for. The Ue125 anchor is independently
computed from the explicitly adopted catalogue contour and nominal-identity
hash. A report reader neither opens source files nor rebuilds a section. The numeric
comparison tolerance is the existing source-coordinate consistency tolerance
of torsion_vlasov.section.from_frozen_profile, not a design acceptance limit.
"""
import math
from .ltb_load_height import finite

ANCHORS = {1.2: {'profile_id': 'R01_Ue100x50x17x1.20_rounded_faceted_209_frozen',
       'nodes_sha256': '004c9cee5033877e4cf1c619627c968c02413aea26fe67a0a5422218ec003f7d',
       'source_file_sha256': 'f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005',
       'CG_xy_mm': [17.277651394999594, 49.400000000000006],
       'SC_xy_mm': [-25.535500764037124, 49.400000000000055]},
 1.5: {'profile_id': 'OWN_Ue100x50x17_t1p50_ri1p50_n12_a16_v1_cd50bf66f299',
       'nodes_sha256': 'cd50bf66f299d1c072b5a45016cf2ffca777b390332d3386175c34d53c234931',
       'source_file_sha256': '9a30115583275a30ab25eb8c782398a8aa5d547b8272743da9cd2f8342f880d4',
       'CG_xy_mm': [17.109102491457765, 49.25],
       'SC_xy_mm': [-25.33166429056801, 49.25000000000007]},
 2.0: {'profile_id': 'OWN_Ue100x50x17_t2p00_ri2p00_n12_a16_v1_13c8bf700cce',
       'nodes_sha256': '13c8bf700cce34d8fb2bc607e9ae06c305cc59cd7e0e67234a38fb0218704638',
       'source_file_sha256': 'fde5d287a73df9adf1b9ab3e392d7207c3423acb7a8894de5553d402cc7aef90',
       'CG_xy_mm': [16.82745087591539, 49.00000000000001],
       'SC_xy_mm': [-24.985063393599717, 49.000000000000014]},
 2.25: {'profile_id': 'OWN_Ue100x50x17_t2p25_ri2p25_n12_a16_v1_e30a0bd327de',
        'nodes_sha256': 'e30a0bd327deb1523b527a5737a9f14ac8f8fd189c884588c0339ef7c0b80e47',
        'source_file_sha256': '8db5d3c4a037e01e665860c1ad8878bab01330cc07fc4165f74a40c0862ec562',
        'CG_xy_mm': [16.686268820177016, 48.875],
        'SC_xy_mm': [-24.80851687520163, 48.87500000000005]},
 2.65: {'profile_id': 'OWN_Ue100x50x17_t2p65_ri2p65_n12_a16_v1_243974742f83',
        'nodes_sha256': '243974742f83ef47937ec56c938718a37b3e037248c4016eddae0d42af062746',
        'source_file_sha256': '40aada8e49914bb1384c8ac205d8035225d5c033e1e76de8fa65f022ebdd99f1',
        'CG_xy_mm': [16.45986627571013, 48.675000000000004],
        'SC_xy_mm': [-24.521504760050956, 48.674999999999976]},
 3.0: {'profile_id': 'OWN_Ue100x50x17_t3p00_ri3p00_n12_a16_v1_c3d1e69d48f6',
       'nodes_sha256': 'c3d1e69d48f6ad2980e6779eb2509e42e07a2b957ce71c158095fda6b71a4e00',
       'source_file_sha256': 'e45b3298a2a95cca875b558269046090751e3bff2fa1b9dfae3cc0c1a2a97919',
       'CG_xy_mm': [16.261232028914485, 48.5],
       'SC_xy_mm': [-24.26575607573298, 48.500000000000036]},
 3.35: {'profile_id': 'OWN_Ue100x50x17_t3p35_ri3p35_n12_a16_v1_90bf516ec976',
        'nodes_sha256': '90bf516ec9761304d22aba266bdf9c2f06bf6f73bc6989b46194bbd5d218eab3',
        'source_file_sha256': 'f1e9676c843459bcb7c14341a32ab10cc90c8ab6765e056fe9bcd47e3b58dd05',
        'CG_xy_mm': [16.062084276097462, 48.325],
        'SC_xy_mm': [-24.005669538520483, 48.32500000000011]}}


# A different height/contour is never selected through a thickness-only key.
# Nominal catalogue geometry, 32 facets per quarter-circle, ri=2 mm.
CATALOG_UE125 = {
    'profile_id': 'OWN_PIERIN_NOMINAL_planilha_v03_r31_980dc2f8d7fbf830',
    'nodes_sha256': '3814f4cd9fcfa474b6e3fcbd21eedb3fdee38818eca0440abb4408fd506143e2',
    'nominal_identity_sha256': '980dc2f8d7fbf830fcdae22160f06a103c576fccccde62525824795dfe18c716',
    'catalog_index': 26, 'catalog_id': 'planilha_v03_r31',
    'CG_xy_mm': [15.116450045292856, 61.5],
    'SC_xy_mm': [-23.516981965583753, 61.49999999999999],
    'dimensions_mm': {'h': 125., 'bf': 50., 'lip': 17., 't': 2., 'ri_mm': 2.},
}


def _catalog_anchor(geometry):
    a=CATALOG_UE125;b=geometry.get('ue_catalog_source_binding')
    return a if (isinstance(b,dict) and geometry.get('section_profile_id')==a['profile_id']
        and geometry.get('nodes_sha256')==a['nodes_sha256']
        and all(b.get(k)==a[k] for k in ('catalog_index','catalog_id','nominal_identity_sha256','nodes_sha256'))
        and b.get('section_profile_id')==a['profile_id']) else None


def supported_geometry(geometry):
    anchor=ANCHORS.get(geometry.get('t_mm'))
    return bool(_catalog_anchor(geometry) or (anchor and geometry.get('section_profile_id')==anchor['profile_id']
        and geometry.get('nodes_sha256')==anchor['nodes_sha256']))


def validate_geometry(geometry, data):
    from .torsion_study import PINS
    t=data['properties']['t'];catalog=_catalog_anchor(geometry);anchor=catalog or ANCHORS.get(t)
    if (anchor is None or (catalog is None and PINS.get(t)!=anchor['source_file_sha256'])
        or geometry.get('coherent_torsion_section') is not True
        or geometry.get('section_profile_id')!=anchor['profile_id']
        or geometry.get('nodes_sha256')!=anchor['nodes_sha256']):
        raise ValueError('Geometria por eixo não vinculada ao contorno pinado.')
    if catalog:
        from .ue_catalog_reference import FIELD,_binding,digest
        marker=data.get(FIELD)
        if (not isinstance(marker,dict) or geometry['ue_catalog_source_binding']!=_binding(marker)
            or marker.get('catalog_index')!=data.get('catalog_index')
            or marker.get('material_sha256')!=digest(marker.get('material'))
            or any(data['properties'].get(k)!=v for k,v in marker.get('material',{}).items())
            or any(data['properties'].get(k)!=v for k,v in catalog['dimensions_mm'].items())):
            raise ValueError('Vínculo do contorno nominal Ue125 ou material divergente.')
    def same(a,b):return math.isclose(finite(a,'coordenada salva'),b,rel_tol=2e-12,abs_tol=1e-10)
    for key in ('CG_xy_mm','SC_xy_mm'):
        value=geometry.get(key)
        if not isinstance(value,list) or len(value)!=2 or not all(same(a,b) for a,b in zip(value,anchor[key])):
            raise ValueError('CG/CT salvo diverge das coordenadas do contorno pinado.')
    h,b=(125.,50.) if catalog else (100.,50.);line=data['roof_top_load']['load_line']
    if not all(same(data['properties'].get(k),v) for k,v in [('h',h),('bf',b),('t',t)]):
        raise ValueError('Dimensões de entrada divergem do contorno pinado.')
    x=0. if line=='web_midplane' else (b-t)/2
    y=h-t/2;cg,sc=anchor['CG_xy_mm'],anchor['SC_xy_mm']
    expected=dict(h_mm=h,bf_mm=b,t_mm=t,load_x_from_web_midplane_mm=x,
        web_midplane_to_flange_midwidth_mm=(b-t)/2,height_above_SC_mm=y-sc[1],
        x_from_CG_mm=x-cg[0],y_from_CG_mm=y-cg[1],x_from_SC_mm=x-sc[0])
    if geometry.get('load_line')!=line or not all(same(geometry.get(k),v) for k,v in expected.items()):
        raise ValueError('Linha/posição de carga salva diverge do contorno e esquema pinados.')
