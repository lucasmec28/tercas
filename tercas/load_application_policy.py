"""Versioned applied-load model. Only new calculation boundaries adopt it.

Stored geometry/line choices remain in the input, inactive for applied forces.
The centroid, shear centre, force vectors, span and connections are not changed.
An absent marker retains the historical applied-load model during replay.
"""
import copy

FIELD = 'load_application_policy'
MODE = 'all_actions_at_shear_center_v1_20261108'
NBR_SCHEMA = 'nbr_ue_family_application_v7_all_actions_CT'
NBR_GIRT_SCHEMA = 'nbr_ue_wall_girt_application_v2_all_actions_CT'
NBR_SCHEMAS = (NBR_SCHEMA, NBR_GIRT_SCHEMA)
ORIGIN = 'Versioned applied-load model'
DIRECT_BASIS = 'direct_external_and_profile_PP_at_shear_center_v1'


def active(data):
    if FIELD not in data:return False
    if data[FIELD] != MODE:raise ValueError('Modelo de aplicação das cargas desconhecido; entradas preservadas.')
    return True


def adopt(data):
    """A fresh calculation, never a reader or source-validation operation."""
    active(data)
    out=copy.deepcopy(data);out[FIELD]=MODE
    return out


def has_contour(data):
    from . import ue_catalog_reference, ue_reference, ue_family_reference
    return any(m.claims_reference(data) for m in (ue_catalog_reference,ue_reference,ue_family_reference))


def applies_to_new(data):
    from .homogeneous_reference import FIELD as HOMOGENEOUS
    network=data.get('three_girt_model',{})
    if has_contour(data) or HOMOGENEOUS in data or (isinstance(network,dict) and network.get('enabled') is True):return True
    from .catalogs import catalog_entry
    return type(data.get('catalog_index')) is int and catalog_entry(data['catalog_index'])['family'] in ('U','Ue')


def for_calculation(data):
    active(data)
    return adopt(data) if applies_to_new(data) else copy.deepcopy(data)


def geometry(data):
    from .torsion_study import section_for
    if not active(data):raise ValueError('Modelo de aplicação não adotado.')
    s=section_for(data);p=s['properties'];cg=p['centroid_xy_mm'];sc=p['shear_center_xy_mm']
    return dict(load_application_policy=MODE,coherent_torsion_section=True,
        CG_xy_mm=list(cg),SC_xy_mm=list(sc),height_above_SC_mm=0.,x_from_SC_mm=0.,
        x_from_CG_mm=sc[0]-cg[0],y_from_CG_mm=sc[1]-cg[1],
        nodes_sha256=s['nodes_sha256'],section_profile_id=s['profile_id'],
        source=ORIGIN,load_line='shear_center')


def lines(section, roles):
    cg=section['properties']['centroid_xy_mm'];sc=section['properties']['shear_center_xy_mm']
    return {r:dict(xy_mm=list(sc),xy_from_CG_mm=[sc[i]-cg[i] for i in (0,1)],
        origin=ORIGIN,load_application_policy=MODE) for r in roles}


def torsion_choice(data):
    """Load lines only: keep the established isolated fork/free-warping model."""
    from .torsion_study import blank_choice, ROLES
    from .wall_girt_isolated import SCHEMA as GIRT_SCHEMA
    g=geometry(data);c=blank_choice()
    if data.get('member_application')=='wall_girt':c['schema']=GIRT_SCHEMA
    for role in (*ROLES,'EXTERNAL') if c['schema']==GIRT_SCHEMA else ROLES:
        c['load_lines'][role]=dict(declared=True,
            xy_from_CG_mm=[g['x_from_CG_mm'],g['y_from_CG_mm']],origin=ORIGIN)
    return c


def source_scope(data, text):
    if not active(data):return text
    return (text.replace('O torque físico do PP no CG está fora desta idealização. ', '')
        .replace('PP físico no CG pode produzir torque, fora desta componente idealizada de flexão. ', '')
        .replace('PP no CG pode gerar torque físico fora desta idealização. ', '')
        .replace('PP no CG pode gerar torque fora desta referência. ', ''))
