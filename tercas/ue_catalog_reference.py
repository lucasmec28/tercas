"""Explicit Ue catalogue contour adoption, with independent immutable provenance.

Reconstructed after the disposable checkout was lost. Historical approval and
critical values are not recovered by name, thickness or scalar coincidence.
"""
import copy
import hashlib
import json
import math

FIELD='ue_catalog_reference'
SCHEMA='ue_catalog_reference_v1'
EVIDENCE='ue_catalog_reference_evidence'
DENSITY_KG_M3=7850.
MATERIAL_KEYS=('E_MPa','G_MPa','fy_MPa','fu_MPa')
OLD_REFERENCE_FIELDS=('homogeneous_reference','homogeneous_lengths','homogeneous_reference_evidence',
    'ue_reference','ue_model','ue_source_documents','active_numeric_reference','ue_reference_evidence',
    'ue_family_reference','ue_family_model','ue_family_sources','ue_family_reference_evidence',
    'own_ue_isolated_application')
SCOPE=('Contorno próprio nominal Ue da linha exata de Pierin, com cantos arredondados '
       'discretizados. Área, massa, inércias, J, Cw, CG, centro de cisalhamento e ω '
       'derivados juntos. PP no CG e ações externas no topo selecionado. '
       'Demanda elástica de Vlasov e componente G8.1; nenhum crítico tabelado, '
       'operador efetivo ou denominador H4 é herdado. Sem aprovação global.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def claims_reference(data):
    return isinstance(data,dict) and FIELD in data


def _isolated(data):
    network=data.get('three_girt_model',{})
    if not isinstance(network,dict):
        raise ValueError('Modelo de três travessas malformado; não converter em terça isolada.')
    if data.get('member_application','purlin')!='purlin' or network.get('enabled'):
        raise ValueError('Contorno Ue próprio exclusivo da terça isolada nesta etapa.')


def _source(index):
    from .catalogs import catalog_entry
    from .catalog_torsion_section import prepare
    if catalog_entry(index)['family']!='Ue':
        raise ValueError('Esta ativação é exclusiva dos 83 Ue; U simples permanece na rota anterior.')
    return prepare(index,arc_segments=32)


def material(data):
    p=data.get('properties',{});out={}
    for key in MATERIAL_KEYS:
        value=p.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Material positivo e finito necessário: '+key)
        out[key]=value
    if out['fu_MPa']<out['fy_MPa']:raise ValueError('fu não pode ser menor que fy.')
    return out


def _properties(packet):
    n=packet['nominal_identity'];s=packet['section'];p=s['properties']
    d=n['dimensions_mm']
    return dict(d,ri_mm=n['inner_radius_mm'],A_cm2=p['A_mm2']/100,
        mass_kg_m=p['A_mm2']*DENSITY_KG_M3*1e-6,
        Ix_cm4=p['Ix_strong_mm4']/1e4,Iy_cm4=p['Iy_weak_mm4']/1e4,
        Wx_cm3=p['Ix_strong_mm4']/(d['h']/2)/1e3,
        J_mm4=p['J_mm4'],Cw_mm6=p['Cw_mm6'])


def _identity(packet,index):
    n=packet['nominal_identity'];s=packet['section']
    return dict(schema=SCHEMA,catalog_index=index,catalog_id=n['catalog_id'],
        geometry_schema=packet['schema'],nominal_identity_sha256=packet['nominal_identity_sha256'],
        nodes_sha256=s['nodes_sha256'],section_profile_id=s['profile_id'])


def _domain(data,*,activation=False):
    _isolated(data)
    from .model_domain import evidence,VERSION
    domain=evidence(data)
    if domain['conflict']:raise ValueError(domain['conflict'])
    from .roof_top_load import enabled
    if activation and not enabled(data):raise ValueError('Selecione primeiro o esquema de carga no topo.')
    if data.get('load_mode')=='direct':
        from .direct_self_weight import active
        if activation and not active(data):
            raise ValueError('Modo direto exige ações externas sem PP explicitamente declaradas; totais legados não são decompostos.')
    elif data.get('load_mode')!='area':raise ValueError('Modo de carregamento não reconhecido.')
    return VERSION


def activate(data):
    """Explicit user adoption; never mutate actions or silently restore old data."""
    version=_domain(data,activation=True);packet=_source(data['catalog_index']);mat=material(data)
    own=_properties(packet);out=copy.deepcopy(data)
    old=data.get(FIELD)
    if isinstance(old,dict) and old.get('nominal_identity_sha256')==packet['nominal_identity_sha256']:
        superseded=copy.deepcopy(old.get('superseded_section_inputs',{}))
    else:
        keys=('properties','property_origin','Ml_Nmm','Mdist_Nmm','critical_origin','weak_axis','weak_catalog')+OLD_REFERENCE_FIELDS
        superseded={k:copy.deepcopy(data[k]) for k in keys if k in data}
    out['properties'].update(own)
    out['property_origin']='Contorno próprio nominal Ue; propriedades geométricas calculadas juntas; material original preservado.'
    for key in OLD_REFERENCE_FIELDS:out.pop(key,None)
    out.pop(EVIDENCE,None)
    out.update(Ml_Nmm=None,Mdist_Nmm=None,critical_origin='Críticos próprios pendentes para este contorno; tabelados anteriores preservados somente para auditoria.',weak_axis={})
    wc=data.get('weak_catalog',{})
    out['weak_catalog']={k:copy.deepcopy(wc[k]) for k in ('Lx_mm',) if isinstance(wc,dict) and k in wc}
    out['model_domain']=version
    out[FIELD]=dict(_identity(packet,data['catalog_index']),geometric_properties=own,properties_sha256=digest(own),
        material=mat,material_sha256=digest(mat),density_kg_m3=DENSITY_KG_M3,
        superseded_section_inputs=superseded,old_criticals_inactive=True,whole_member_approved=False)
    from .isolated_en_application import reset_changed_declaration
    reset_changed_declaration(out)
    validate(out)
    return out


def _same(a,b):
    return (not isinstance(a,bool) and isinstance(a,(float,int)) and math.isfinite(a)
        and math.isclose(a,b,rel_tol=2e-12,abs_tol=1e-9))


def validate(data):
    if not claims_reference(data):return None
    version=_domain(data)
    if data.get('model_domain')!=version:raise ValueError('Domínio do contorno próprio alterado; reaplique explicitamente.')
    if any(key in data for key in OLD_REFERENCE_FIELDS):
        raise ValueError('Referências antigas e contorno próprio não podem coexistir.')
    packet=_source(data['catalog_index']);expected=_identity(packet,data['catalog_index']);marker=data[FIELD]
    fields=set(expected)|{'geometric_properties','properties_sha256','material','material_sha256',
        'density_kg_m3','superseded_section_inputs','old_criticals_inactive','whole_member_approved'}
    if not isinstance(marker,dict) or set(marker)!=fields:
        raise ValueError('Marcador de contorno próprio ausente, malformado ou desconhecido.')
    if any(marker.get(k)!=v for k,v in expected.items()):
        raise ValueError('Identidade nominal do contorno próprio mudou; reaplique explicitamente.')
    own=_properties(packet);saved=marker['geometric_properties']
    if (not isinstance(saved,dict) or set(saved)!=set(own) or
        any(not _same(saved[k],v) or not _same(data['properties'].get(k),v) for k,v in own.items()) or
        marker['properties_sha256']!=digest(saved)):
        raise ValueError('Propriedades não correspondem ao mesmo contorno próprio; reaplique explicitamente.')
    if marker['material']!=material(data) or marker['material_sha256']!=digest(marker['material']):
        raise ValueError('Material alterado; reaplique explicitamente o contorno próprio.')
    if (marker['density_kg_m3']!=DENSITY_KG_M3 or marker['old_criticals_inactive'] is not True or
        marker['whole_member_approved'] is not False or not isinstance(marker['superseded_section_inputs'],dict)):
        raise ValueError('Escopo ou auditoria do contorno próprio alterados.')
    return packet


def _binding(marker):
    keys=('schema','catalog_index','catalog_id','geometry_schema','nominal_identity_sha256',
        'nodes_sha256','section_profile_id','properties_sha256','material_sha256','material','density_kg_m3')
    return {k:copy.deepcopy(marker[k]) for k in keys}


def source_binding(data):
    if validate(data) is None:raise ValueError('Contorno próprio Ue não selecionado.')
    return _binding(data[FIELD])


def section_for(data):
    packet=validate(data)
    if packet is None:raise ValueError('Contorno próprio Ue não selecionado.')
    return packet['section']


def attach_source(result):
    if not claims_reference(result['input_data']):return copy.deepcopy(result)
    from .application import fingerprint
    data=result['input_data'];packet=validate(data)
    if fingerprint(data)!=result.get('input_fingerprint'):raise ValueError('Resultado de contorno próprio desatualizado.')
    marker=data[FIELD];out=copy.deepcopy(result)
    ev=dict(schema='ue_catalog_reference_evidence_v1',source_input_fingerprint=result['input_fingerprint'],
        source_binding=_binding(marker),scope=SCOPE,
        geometric_properties=copy.deepcopy(marker['geometric_properties']),
        catalogue_comparison=copy.deepcopy(packet['catalogue_comparison']),
        superseded_section_inputs=copy.deepcopy(marker['superseded_section_inputs']),
        old_criticals_inactive=True,whole_member_approved=False)
    ev['snapshot_sha256']=digest(ev);out[EVIDENCE]=ev
    return out


def preserved(result):
    """Verify saved values only; never reopen a catalogue or run a section solve."""
    ev=result.get(EVIDENCE)
    if ev is None:return None
    from .application import fingerprint
    data=result['input_data'];marker=data.get(FIELD)
    if (not isinstance(ev,dict) or not isinstance(marker,dict) or ev.get('schema')!='ue_catalog_reference_evidence_v1'
        or marker.get('schema')!=SCHEMA or marker.get('catalog_index')!=data.get('catalog_index')
        or marker.get('density_kg_m3')!=DENSITY_KG_M3
        or result.get('input_fingerprint')!=fingerprint(data)
        or ev.get('source_input_fingerprint')!=result.get('input_fingerprint')
        or ev.get('snapshot_sha256')!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
        or ev.get('source_binding')!=_binding(marker)
        or ev.get('geometric_properties')!=marker.get('geometric_properties')
        or ev.get('superseded_section_inputs')!=marker.get('superseded_section_inputs')
        or marker.get('properties_sha256')!=digest(marker.get('geometric_properties'))
        or marker.get('material_sha256')!=digest(marker.get('material'))
        or marker.get('material')!=material(data)
        or marker.get('old_criticals_inactive') is not True or marker.get('whole_member_approved') is not False
        or ev.get('old_criticals_inactive') is not True or ev.get('whole_member_approved') is not False):
        raise ValueError('Snapshot do contorno Ue incompatível; recalcule explicitamente.')
    if any(not _same(data['properties'].get(k),v) for k,v in ev['geometric_properties'].items()):
        raise ValueError('Snapshot de propriedades próprias divergente das entradas.')
    return copy.deepcopy(ev)


def attach_resistance(result,section):
    """G8.1 on the same section; no inherited pure-bending denominator for H4."""
    data=result['input_data'];binding=source_binding(data)
    if section!=section_for(data):raise ValueError('Seção resistente e fonte Ue divergentes.')
    from .aisi_torsion_component import attach_dense,FIELD as AISI_FIELD
    out=attach_dense(result,section);ev=out[AISI_FIELD]
    if ev.get('H4_computed_cases') or any(r.get('H4') is not None for r in ev.get('records',[])):
        raise ValueError('H4 não pode herdar denominadores de outro contorno.')
    ev['ue_catalog_source_binding']=binding
    ev['ue_catalog_scope']='G8.1 do mesmo contorno; H4 pendente de capacidades flexionais próprias.'
    return out
