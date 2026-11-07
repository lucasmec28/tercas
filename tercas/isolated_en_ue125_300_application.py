"""Explicit fy300 opt-in and source-bound saved readers. No historical promotion."""
import copy
from .isolated_en_application import digest, _inventory
from . import en_ue125_300_authority as authority
from .isolated_en_ue_catalog_application import _load_inventory, _validate_case as _validate_case_actions
CHOICE='isolated_en_ue125_300_model'
CHOICE_SCHEMA='isolated_EN_Ue125_300_choice_v1'
FIELD='isolated_EN_Ue125_300_component'
SCHEMA='isolated_EN_Ue125_300_saved_component_v1'
MATERIAL=dict(E_MPa=210000.,nu=.3,fyb_MPa=300.,fya_MPa=300.,gamma_M0=1.)
FLAGS=('whole_member_approved','physical_design_approved','complete_EN_design_qualified',
 'global_stability_qualified','combined_ELS_qualified','first_order_analysis_qualified',
 'historical_results_requalified','original_mechanics_changed','NBR_capacities_used','AISI_capacities_used')
SCOPE=('EN1993-1-3:2006, contorno próprio Ue125x50x17x2 ri=2, fy300: '
 '§6.1.6 tensões concomitantes e §6.1.10/Equação 6.27 M–V são componentes separadas. '
 'N=0; torção não é convertida em V. Condição suficiente seccional não aprova a barra, '
 'estabilidade, adequação da primeira ordem ou ELS completo.')

def identity(data):
    return digest(dict(reference=data.get('ue_catalog_reference'), properties=data.get('properties'),
        steel_name=data.get('steel_name'), member_application=data.get('member_application','purlin')))


def choice(data, *, enabled=True, declared=False, origin=''):
    return dict(schema=CHOICE_SCHEMA, enabled=enabled, intact_section_model_declared=declared,
        model_origin=origin, section_material_identity=identity(data))


def activate(data, *, model_origin):
    """Explicit new calculation declaration; never change numeric inputs.

    Shared by UI and authorized callers. Historical results are not an input
    and are never promoted; returns a copied input with the new choice only.
    """
    if not isinstance(model_origin,str) or not model_origin.strip():
        raise ValueError("Origem explícita do modelo nominal intacto necessária.")
    out=copy.deepcopy(data)
    c=choice(out,enabled=True,declared=True,origin=model_origin)
    reason=_domain(out,c)
    if reason:raise ValueError(reason)
    out[CHOICE]=c
    return out


def configuration(data):
    c=data.get(CHOICE)
    if c is None:return None
    if (not isinstance(c,dict) or set(c)!=set(choice(data)) or c.get('schema')!=CHOICE_SCHEMA
        or type(c.get('enabled')) is not bool or type(c.get('intact_section_model_declared')) is not bool
        or type(c.get('model_origin')) is not str or type(c.get('section_material_identity')) is not str):
        raise ValueError('Escolha EN Ue malformada; não foi convertida automaticamente.')
    return copy.deepcopy(c)


def reset_changed_declaration(data):
    c=configuration(data)
    if c is not None and c['section_material_identity']!=identity(data):
        data[CHOICE]=choice(data, enabled=c['enabled']);return True
    return False


def _domain(data,c):
    if c['section_material_identity']!=identity(data):return 'Seção/material/aplicação mudou; declaração anterior não se transfere.'
    if not c['intact_section_model_declared'] or not c['model_origin'].strip():
        return 'Adote explicitamente seção nominal intacta, sem furos/recortes, e registre a origem do modelo.'
    net=data.get('three_girt_model',{})
    if not isinstance(net,dict) or net.get('enabled') or data.get('member_application','purlin')!='purlin':
        return 'Componente exclusiva do vão isolado de terça; rede/travessa não coberta.'
    marker=data.get('ue_catalog_reference')
    if not isinstance(marker,dict) or marker.get('schema')!='ue_catalog_reference_v1':
        return 'Ativação explícita do contorno próprio Ue de catálogo necessária.'
    if type(data['properties'].get('fy_MPa')) not in (int,float) or data['properties']['fy_MPa']!=300.:
        return 'Material fora do domínio: resistência EN exige fyb=fya=300 MPa; nenhum aço é convertido.'
    if marker.get('catalog_index')!=26:return 'Somente contorno próprio Ue125x50x17x2, ri=2, índice 26.'
    expected=dict(E_MPa=200000.,G_MPa=77000.,fy_MPa=300.,fu_MPa=400.)
    if any(type(data['properties'].get(k)) not in (int,float) or data['properties'][k]!=v for k,v in expected.items()):
        return 'Contrato explícito: análise E=200000/G=77000 MPa e aço fy=300/fu=400 MPa.'
    return None


def _base(result,c):
    inv=_inventory(result)
    return dict(schema=SCHEMA, configuration=copy.deepcopy(c), scope=SCOPE, material=copy.deepcopy(MATERIAL),
        source_input_fingerprint=result['input_fingerprint'], section_material_identity=identity(result['input_data']),
        source_inventory=inv, records=[], ELU_cases=sum(r['limit_state']=='ELU' for r in inv),
        ELS_cases_excluded=sum(r['limit_state']=='ELS' for r in inv), **{k:False for k in FLAGS})


def _counts(ev):
    rows=ev['records']
    return dict(computed_cases=sum(r.get('check') is not None for r in rows),
        shear_computed_cases=sum(r.get('check') is not None for r in rows),
        shear_sufficient_cases=sum(bool(r.get('check') and r['check']['shear']['component_sufficient']) for r in rows),
        mv_computed_cases=sum(bool(r.get('check') and r['check']['mv']['index_upper'] is not None) for r in rows),
        mv_sufficient_cases=sum(bool(r.get('check') and r['check']['mv']['component_sufficient']) for r in rows),
        pending_demand_cases=sum(r.get('check') is None for r in rows),
        mv_pending_cases=sum(not r.get('check') or r['check']['mv']['index_upper'] is None for r in rows))


def _pending(result,c,reason):
    ev=_base(result,c)
    ev['reason']=reason
    ev['records']=[dict(combination_id=r['combination_id'],limit_state='ELU',status='pending',reason=reason,
        check=None,source_analysis_sha256=None,original_source_binding=None)
        for r in ev['source_inventory'] if r['limit_state']=='ELU']
    ev.update(_counts(ev));return ev



def _validate_source_contract(summary,data):
    from .roof_top_load import configuration as roof_configuration
    roof=roof_configuration(data)
    if not roof or not roof['enabled'] or roof['end_restraint']!='fork_free_warping':
        raise ValueError('Contrato original de garfos com empenamento livre requerido.')
    numerics=summary.get('numerics',{});domain=summary.get('analysis_domain',{})
    if (type(numerics.get('rotation_warning_rad')) not in (int,float)
        or numerics['rotation_warning_rad']!=.05
        or numerics.get('rotation_warning_is_normative_limit') is not False
        or domain.get('small_rotation_kinematics') is not True
        or domain.get('physical_hypotheses_verified') is not False):
        raise ValueError('Aviso de giro e hipóteses físicas originais não podem ser substituídos.')
    supports=summary.get('support_hypotheses')
    if not isinstance(supports,dict) or set(supports)!={'left','right'}:
        raise ValueError('Dois apoios originais requeridos.')
    for support in supports.values():
        if (not isinstance(support,dict) or support.get('twist')!='fixed'
            or support.get('warping')!='free_assumed'):
            raise ValueError('Hipótese torsional difere dos garfos originais com empenamento livre.')
    for load in summary['loads']:
        key='couple_N' if load['kind']=='uniform' else 'couple_Nmm'
        if type(load.get(key)) not in (int,float) or load[key]!=0:
            raise ValueError('Entradas desta rota não contêm binários livres adicionais.')


def _validate_case(summary,expected,data):
    _validate_case_actions(summary,expected,data)
    _validate_source_contract(summary,data)


def attach_dense(result,section):
    if CHOICE not in result['input_data']:return result
    out=copy.deepcopy(result)
    try:c=configuration(out['input_data'])
    except ValueError as e:out[FIELD]=_pending(out,out['input_data'][CHOICE],str(e));return out
    if c is None or not c['enabled']:return out
    reason=_domain(out['input_data'],c)
    if reason:out[FIELD]=_pending(out,c,reason);return out
    from .ue_catalog_reference import preserved as source_preserved
    from .isolated_en_ue125_300 import calculate
    try:
        source=source_preserved(out)
        if source is None:raise ValueError('Fonte Ue original ausente.')
        normal=authority.read();b=source['source_binding']
        if (section['nodes_sha256']!=normal['nodes_sha256'] or section['profile_id']!=normal['profile_id']
            or b['nodes_sha256']!=normal['nodes_sha256'] or b['catalog_index']!=26):
            raise ValueError('Contorno não pertence à autoridade EN300 original.')
        loads=_load_inventory(out)
        records=out.get('torsion_evidence',{}).get('records',[])
        if [(r['combination_id'],r['limit_state']) for r in records]!=[(r['combination_id'],r['limit_state']) for r in _inventory(out)]:
            raise ValueError('Inventário Vlasov integral divergente.')
    except (ValueError,KeyError,TypeError) as e:out[FIELD]=_pending(out,c,str(e));return out
    ev=_base(out,c);ev.update(normal_snapshot=normal,catalog_source_binding=copy.deepcopy(b))
    for rec in records:
        if rec['limit_state']!='ELU':continue
        row=dict(combination_id=rec['combination_id'],limit_state='ELU',status='pending',reason=None,
            check=None,source_analysis_sha256=None,original_source_binding=None)
        d=rec.get('analysis')
        if rec['status']!='elastic_demand_computed' or not isinstance(d,dict):row['reason']='Demanda Vlasov indisponível.'
        else:
            try:
                if d.get('schema')!='single_vlasov_member_demand_v1' or digest(d['section'])!=digest(section):
                    raise ValueError('Campo integral original requerido antes da compactação.')
                if d['combination_id']!=rec['combination_id'] or d['limit_state']!='ELU':raise ValueError('Caso/estado divergente.')
                _validate_case(d,loads[rec['combination_id']],out['input_data'])
                row['source_analysis_sha256']=digest(d)
                rec['EN_ue125_300_dense_source_sha256']=digest(d)
                row['check']=calculate(d,normal_snapshot=normal,model_origin=c['model_origin'])
                row['status']='computed'
            except (ValueError,KeyError,TypeError,ArithmeticError) as e:row['reason']=str(e)
        ev['records'].append(row)
    ev.update(_counts(ev));out[FIELD]=ev;return out

def finalize(result):
    if CHOICE not in result['input_data']:return result
    out=copy.deepcopy(result)
    try:
        c=configuration(out['input_data'])
        if c is None or not c['enabled']:return out
        reason=_domain(out['input_data'],c)
    except ValueError as e:c=out['input_data'][CHOICE];reason=str(e)
    if FIELD not in out:out[FIELD]=_pending(out,c,reason or 'Demanda Vlasov integral indisponível; calcule explicitamente no contorno Ue ativo.')
    ev=out[FIELD];ev['source_torsion_snapshot_sha256']=digest(out.get('torsion_evidence'))
    summaries={r['combination_id']:r for r in out.get('torsion_evidence',{}).get('records',[])}
    for row in ev['records']:row['source_summary_record_sha256']=digest(summaries.get(row['combination_id']))
    ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'});return out



def _validate_preserved(result):
    ev=result.get(FIELD)
    if ev is None:return None
    from .application import fingerprint
    from .ue_catalog_reference import preserved as source_preserved
    from .isolated_en_ue125_300 import validate_saved_many
    try:
        c=configuration(result['input_data']);base=_base(result,c)
        if (c is None or not c['enabled'] or fingerprint(result['input_data'])!=result['input_fingerprint']
            or any(digest(ev.get(k))!=digest(v) for k,v in base.items() if k!='records')
            or ev['source_torsion_snapshot_sha256']!=digest(result.get('torsion_evidence'))
            or ev['snapshot_sha256']!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})):
            raise ValueError('Snapshot EN300 incompatível com entradas/fontes salvas.')
        expected=[(r['combination_id'],'ELU') for r in base['source_inventory'] if r['limit_state']=='ELU']
        if [(r['combination_id'],r['limit_state']) for r in ev['records']]!=expected:raise ValueError('Inventário ELU divergente.')
        computed=any(r['status']=='computed' for r in ev['records'])
        loads=_load_inventory(result) if computed else {}
        source=source_preserved(result) if computed else None
        if computed:
            # The closed batch below authenticates the original normal snapshot
            # before any shear certificate or proof can be accepted.
            if source is None or digest(ev['catalog_source_binding'])!=digest(source['source_binding']):raise ValueError('Fonte original substituída.')
        summaries={r['combination_id']:r for r in result.get('torsion_evidence',{}).get('records',[])}
        requests=[]
        for row in ev['records']:
            summary=summaries.get(row['combination_id'])
            if row['source_summary_record_sha256']!=digest(summary):raise ValueError('Fonte compacta alterada.')
            if row['status']=='computed':
                if _domain(result['input_data'],c) or summary['status']!='elastic_demand_computed':raise ValueError('Fora do domínio declarado.')
                if summary.get('EN_ue125_300_dense_source_sha256')!=row['source_analysis_sha256']:raise ValueError('Hash integral substituído.')
                _validate_case(summary['analysis'],loads[row['combination_id']],result['input_data'])
                requests.append(dict(check=row['check'],summary=summary['analysis'],
                    source_sha256=row['source_analysis_sha256']))
            elif row['status']!='pending' or row['check'] is not None or not row['reason']:raise ValueError('Pendência inválida.')
        if requests:
            validate_saved_many(requests,normal_snapshot=ev['normal_snapshot'],model_origin=c['model_origin'])
        if any(type(ev.get(k)) is not int or ev[k]!=v for k,v in _counts(ev).items()):raise ValueError('Contagem EN300 divergente.')
    except (KeyError,TypeError,AttributeError,IndexError) as e:raise ValueError('Registro EN300 incompleto/malformado.') from e
    return ev


def preserved(result):
    """Public saved reader retains its complete detached snapshot contract."""
    return copy.deepcopy(_validate_preserved(result))


def _presentation_view(result):
    """Detached lightweight view, only AFTER complete source-bound validation.

    UI, Word and panorama do not consume dense arrays or per-piece replay
    controls. Never copy those merely to discard them. This is not a cached
    validation: each call authenticates every input, source and authority.
    """
    ev=_validate_preserved(result)
    if ev is None:return None
    rows=[]
    for row in ev['records']:
        projected={k:v for k,v in row.items() if k!='check'}
        check=row.get('check')
        projected['check']=None if check is None else {
            k:v for k,v in check.items() if k not in ('source_demand','pieces')}
        rows.append(projected)
    return copy.deepcopy(dict({k:v for k,v in ev.items() if k!='records'},records=rows))


def global_context(result, *, sectional=False):
    ev=_presentation_view(result)
    if ev is None:return None
    context=dict(reason=SCOPE+f" {ev['computed_cases']} casos ELU calculados; {ev['pending_demand_cases']} pendentes.",
        binding=dict(snapshot_sha256=ev['snapshot_sha256'],scope=SCOPE))
    observed=sum(bool(r.get('check') and r['check']['stress']['criteria']['normal'].get('observed_exceedance')) for r in ev['records'])
    if observed:
        context['reason']+=f' Excesso normal observado por testemunha concomitante no campo linear em {observed} casos; não é máximo global nem validação da primeira ordem.'
    if sectional:
        from .isolated_en_panorama import sectional_context
        context['sectional']=sectional_context(result,ev,en300=True)
        if not ev['ELU_cases']:context['reason']='Nenhuma combinação ELU selecionada. '+context['reason']
    return context
