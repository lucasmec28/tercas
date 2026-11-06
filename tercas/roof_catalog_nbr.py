"""Partial NBR height adapter for the explicitly qualified catalogue contour.

A valid local critical permits the FLT component. Missing distortional or weak
resistances never disappear into min(), and never become an interaction index.
"""
import copy
import math

KIND='own_catalog_Ue125_bending_components_v1'
KIND_V2='own_catalog_Ue125_bending_components_v2'
KINDS=(KIND,KIND_V2)
WEAK_PENDING='Resistências fracas próprias por sentido ausentes; interação §9.9 pendente, sem índice biaxial.'
PENDING='Distorção forte não qualificada; mínimo local–FLT–D e interação §9.9 pendentes. Não é dispensa.'


def section(data,evidence,geometry):
    """Pure saved-value mapping. Caller owns fresh/source or saved validation."""
    from .ue_catalog_nbr_bending import FIELD
    from .roof_top_load import digest
    local=evidence['strong']['local'];dist=evidence['strong']['distortional']
    if local.get('status')!='computed':
        raise ValueError('Ml e seção efetiva próprios não qualificados para este contorno/material.')
    version=evidence.get('schema')
    if version not in ('ue_catalog_nbr_bending_v1','ue_catalog_nbr_bending_v2'):
        raise ValueError('Versão do certificado NBR de catálogo não reconhecida.')
    v2=version=='ue_catalog_nbr_bending_v2'
    if v2 and (type(evidence.get('strong_bending_complete')) is not bool
        or evidence.get('biaxial_qualified') is not False):
        raise ValueError('Qualificação forte/biaxial ausente ou inválida no certificado v2.')
    complete=v2 and evidence['strong_bending_complete']
    if not complete and any(dist.get(k) is not None for k in ('MRd_Nmm','MRd_dist_Nmm','Mdist_Nmm')):
        raise ValueError('Capacidade distorcional fora do contrato parcial do catálogo.')
    if v2 and not complete and (dist.get('status')!='not_evaluated' or dist.get('exemption') is not False):
        raise ValueError('Pendência distorcional v2 incompatível com seu domínio.')
    if complete and (dist.get('status')!='computed_approximate' or dist.get('exemption') is not False
        or dist.get('elastic_approximation') is not True
        or any(isinstance(dist.get(k),bool) or not isinstance(dist.get(k),(int,float))
            or not math.isfinite(dist[k]) or dist[k]<=0 for k in ('Mdist_Nmm','MRd_Nmm','MRd_dist_Nmm'))
        or dist.get('MRd_Nmm')!=dist.get('MRd_dist_Nmm')):
        raise ValueError('Capacidade distorcional aproximada incompleta ou fora do contrato v2.')
    marker=data['ue_catalog_reference'];mat=marker['material']
    out=dict(kind=KIND,reference_id=marker['section_profile_id']+'_'+marker['material_sha256'],
        thickness_mm=data['properties']['t'],source_reference_field=FIELD,
        source_reference_sha256=digest(evidence),
        source_documents=copy.deepcopy(evidence.get('source_documents',[])),
        source_binding=copy.deepcopy(evidence['source_binding']),
        nodes_sha256=geometry['nodes_sha256'],section_profile_id=geometry['section_profile_id'],
        W_mm3=local['W_mm3'],Wc_mm3=local['Wc_mm3'],Ml_Nmm=local['Ml_Nmm'],
        fy_MPa=mat['fy_MPa'],E_MPa=mat['E_MPa'],G_MPa=mat['G_MPa'],
        MRd_section_effective_Nmm=local['MRd_local_Nmm'],MRd_distortional_Nmm=None,
        strong_distortional_exempt=False,strong_bending_complete=False,
        distortion_scope=PENDING,
        critical_source='Ml NBR Tabela12(b), com módulo externo do mesmo contorno nominal; sem críticos herdados de Ue100 ou Pierin.')
    if v2:
        out.update(kind=KIND_V2,strong_bending_complete=complete,biaxial_qualified=False,
            MRd_distortional_Nmm=dist['MRd_dist_Nmm'],Mdist_Nmm=dist['Mdist_Nmm'],
            distortional_source_sha256=digest(dist['analytical_evidence']) if dist.get('analytical_evidence') is not None else None,
            distortion_scope=dist['reason']+' '+WEAK_PENDING,
            critical_source=('Ml NBR Tabela12(b) e Mdist analítico aproximado qualificado no mesmo contorno/material; sem críticos herdados de Ue100 ou Pierin.' if complete else
                'Ml NBR Tabela12(b) do mesmo contorno/material; distorção pendente no domínio declarado, sem críticos herdados.'))
    return out


def fresh_section(data,result):
    from .ue_catalog_nbr_bending import FIELD,qualify
    from .roof_top_load import geometry
    fresh=qualify(data)
    if fresh is None:raise ValueError('Consumo NBR do catálogo restrito ao contorno/material Ue125×50×17×2 qualificado; demais perfis pendentes.')
    if result.get('roof_top_load_evidence',{}).get('load_basis')=='direct_total_top_envelope':
        raise ValueError('Contorno próprio exige PP e ações externas separados; envoltória direta total não integrada nesta qualificação.')
    if fresh!=result.get(FIELD):raise ValueError('Evidência NBR do contorno próprio salva diverge da fonte qualificada.')
    return section(data,fresh,geometry(data))


def validate_section(saved,data,result,geometry):
    from .ue_catalog_nbr_bending import FIELD,validate_saved
    from .roof_biaxial_geometry import validate_geometry
    if saved.get('source_reference_field')!=FIELD:raise ValueError('Fonte NBR de catálogo substituída.')
    evidence=result.get(FIELD)
    validate_saved(evidence,data)
    validate_geometry(geometry,data)
    if saved!=section(data,evidence,geometry):
        raise ValueError('Componente FLT de catálogo diverge do certificado de contorno/material.')


def validate_curve(curve,source,me):
    """Independent arithmetic identities, not a new source or resistance solve."""
    W,fy,Ml=source['Wc_mm3'],source['fy_MPa'],source['Ml_Nmm']
    lam=math.sqrt(W*fy/me)
    chi,branch=(1.,'stocky') if lam<=.6 else (1.11*(1-.278*lam**2),'intermediate') if lam<1.336 else (1/lam**2,'elastic')
    lp=math.sqrt(chi*W*fy/Ml)
    rho,local=(1.,'gross') if lp<=.673 else ((1-.22/lp)/lp,'effective')
    values=dict(lambda0=lam,chi_flt=chi,flt_branch=branch,lambda_p_reduced_stress=lp,
        local_branch=local,Wceff_mm3=W*rho,MRd_flt_Nmm=chi*W*rho*fy/1.1,gamma=1.1)
    if any(curve.get(k)!=v for k,v in values.items()):
        raise ValueError('Curva FLT de catálogo não corresponde ao certificado/Me salvo.')


def partial_fields(separate_axis,*,strong_complete=False):
    if strong_complete:
        out=dict(bending_component_status='computed_strong_pure_bending',missing_bending_components=[])
        if separate_axis:
            out['biaxial_pending']=dict(status='not_evaluated',index=None,
                missing=['weak_positive','weak_negative'],reason=WEAK_PENDING,whole_member_approved=False)
        return out
    out=dict(bending_component_status='pending_distortional',missing_bending_components=['distortional'],
        MRd_bending_component_Nmm=None,bending_component_index=None,governing_bending_components=[])
    if separate_axis:
        out['biaxial_pending']=dict(status='not_evaluated',index=None,
            missing=['strong_distortional','weak_positive','weak_negative'],
            reason=PENDING+' Resistências fracas próprias por sentido ausentes.',whole_member_approved=False)
    return out
