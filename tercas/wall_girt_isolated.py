"""Own isolated girt: existing manual lines, local forces and explicit supports.

No facade face is guessed. In the contour frame +x points down and +y right;
force [parallel, -normal] is therefore already local. Roof choices stay dormant.
"""
import copy
from .torsion_study import configuration, blank_choice, FIELD

SCHEMA='wall_girt_isolated_vlasov_choice_v1'

def choice():
    out=blank_choice();out['schema']=SCHEMA
    return out


def active(data):
    from .ue_catalog_reference import FIELD as OWN, GIRT_SCHEMA
    return (data.get('member_application')=='wall_girt'
        and data.get(OWN,{}).get('schema')==GIRT_SCHEMA
        and not data.get('three_girt_model',{}).get('enabled'))


def roles(data):
    if data.get('load_mode')=='area':
        from .torsion_study_ui import active_roles
        return active_roles(data)
    from .direct_roof_separated import combinations
    cs=combinations(data)
    return [role for role,field in (('EXTERNAL','external_q_vector'),('P','P_vector'))
            if any(any(c[field].values()) for c in cs)]


def points(data,cg):
    """Declared offsets only; PP cannot be overridden by the manual records."""
    from .load_application_policy import active as ct_active
    if ct_active(data):
        from .ue_catalog_reference import section_for
        sc=section_for(data)['properties']['shear_center_xy_mm']
        return {role:list(sc) for role in ('PP',*roles(data))}
    c=configuration(data)
    if not c or not c['enabled'] or c['schema']!=SCHEMA:raise ValueError('Declare o modelo Vlasov próprio da travessa e suas linhas locais; linhas da terça não se transferem.')
    out={'PP':list(cg)}
    for role in roles(data):
        r=c['load_lines'].get(role)
        if not r or not r['declared'] or not r['origin'].strip() or any(x is None for x in r['xy_from_CG_mm']):
            raise ValueError('Linha local não declarada: '+role)
        out[role]=[cg[i]+r['xy_from_CG_mm'][i] for i in (0,1)]
    return out


def geometry(data):
    from .load_application_policy import active as ct_active, geometry as ct_geometry
    if ct_active(data):return ct_geometry(data)
    from .ue_catalog_reference import section_for
    s=section_for(data);cg=s['properties']['centroid_xy_mm'];sc=s['properties']['shear_center_xy_mm']
    lines=points(data,cg)
    # Compatibility envelope consumed only by direct_torsion.actions, which
    # uses declared_lines individually, never this absent-action placeholder.
    external=lines.get('EXTERNAL',cg)
    return dict(coherent_torsion_section=True,CG_xy_mm=list(cg),SC_xy_mm=list(sc),
        x_from_CG_mm=external[0]-cg[0],y_from_CG_mm=external[1]-cg[1],declared_lines=lines)


def attach_direct(result,c):
    from . import direct_torsion, direct_self_weight
    from .torsion_study import pending_evidence
    data=result['input_data']
    try:
        if not direct_self_weight.active(data):raise ValueError('Ações diretas totais legadas não separam PP; adote explicitamente ações externas sem PP.')
        geometry(data)
    except ValueError as exc:
        out=copy.deepcopy(result);out['torsion_evidence']=pending_evidence(result,str(exc));return out
    return direct_torsion.attach(result,c)


def validate_case(summary,expected,data):
    """Saved-source replay without source files, section generation or solver."""
    from .ue_catalog_reference import digest,GIRT_SCHEMA,FIELD as OWN
    if not active(data) or data[OWN]['schema']!=GIRT_SCHEMA:raise ValueError('Identidade isolada da travessa divergente.')
    if summary.get('member_id')!='WALL_GIRT':raise ValueError('Campo não identifica a travessa isolada.')
    lines=points(data,summary['section']['properties']['centroid_xy_mm'])
    actual=[]
    for a in summary['loads']:
        if a['name']=='zero_combination' and not expected and not any(a['q_xy_N_mm']):continue
        if a['application_xy_mm']!=lines.get(a['name']):raise ValueError('Linha de carga da travessa diverge da declaração original.')
        row=dict(name=a['name'],kind=a['kind'],vector=a['q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N'])
        if a['kind']=='point':row.update(s_mm=a['s_mm'],existing_point_position=a['existing_point_position'])
        actual.append(row)
    if digest(actual)!=digest(expected):raise ValueError('Forças locais/posição P divergem da combinação original da travessa.')


def render_choice(st,data,key):
    from .load_application_policy import active, applies_to_new
    if active(data) or applies_to_new(data):return
    from .torsion_study import LABELS
    from .ue_catalog_reference import GIRT_SCHEMA,FIELD as OWN
    if data.get(OWN,{}).get('schema')!=GIRT_SCHEMA:
        st.caption('Para demanda isolada, adote explicitamente o contorno próprio da travessa. Declarações antigas são preservadas.')
        return
    c=configuration(data)
    previous=c if c and c['schema']!=SCHEMA else None
    if previous:c=None
    with st.expander('Travessa isolada — linhas locais e Vlasov',expanded=False):
        st.caption('Boca para baixo: +x local é vertical para baixo; +y local é horizontal para a direita. Forças [paralela, −normal]. Garfos ideais nos extremos, empenamento livre, sem rigidez de telha e sem inferir vínculos de Leff. A linha da cobertura não se transfere à fachada.')
        enabled=st.checkbox('Adotar modelo Vlasov isolado com garfos e empenamento livre',value=bool(c and c['enabled']),key=key+'_girt_enabled')
        if c is None and not enabled:return
        c=copy.deepcopy(c) if c else choice();c['enabled']=enabled
        if previous:
            c['load_lines']=copy.deepcopy(previous['load_lines'])
            for row in c['load_lines'].values():row['declared']=False
        data[FIELD]=c
        if not enabled:return
        try:required=roles(data)
        except ValueError as exc:st.warning(str(exc));return
        st.caption('PP uma vez no CG. Reutilize as declarações por ação; nenhum ponto da fachada é presumido. Confira os offsets ao trocar aplicação ou seção.')
        for role in required:
            old=c['load_lines'].get(role,dict(declared=False,xy_from_CG_mm=[None,None],origin=''))
            rec=copy.deepcopy(old)
            rec['declared']=st.checkbox('Declarar linha — '+LABELS.get(role,'Carga externa direta q'),value=old['declared'],key=key+'_girt_'+role)
            if not rec['declared'] and role not in c['load_lines']:continue
            if rec['declared']:
                for i,axis in enumerate(('x local, vertical para baixo','y local, horizontal para a direita')):
                    v=rec['xy_from_CG_mm'][i]
                    rec['xy_from_CG_mm'][i]=st.number_input(role+': '+axis+' desde CG [mm]',value=None if v is None else float(v),format='%.6f',key=key+'_girt_'+role+'_'+str(i))
                rec['origin']=st.text_input('Origem/hipótese da linha — '+role,value=rec['origin'],key=key+'_girt_'+role+'_origin')
            c['load_lines'][role]=rec


def height_model_adopted(data):
    """Explicit isolated load-line/fork contract; never manufacture roof input."""
    from .torsion_study import SUPPORTS
    c=configuration(data)
    return bool(active(data) and c and c['enabled'] and c['schema']==SCHEMA
                and c['support_hypothesis']==SUPPORTS)


def height_actions(data,bundle,combo):
    """Authentic per-action local arms for NBR/FLT consumers, without a solver.

    Unknown external lines remain None; no common facade face or zero arm is
    inferred. Source combination and bundle are replayed from the input actions.
    """
    from .ue_catalog_reference import section_for
    if not active(data):raise ValueError('Fonte própria de travessa isolada necessária.')
    if data.get('load_mode')=='direct':
        from .direct_roof_separated import combinations
        if bundle is not None or combo not in combinations(data):raise ValueError('Combinação direta de altura divergente das entradas.')
    else:
        from .batch import area_bundle
        expected=area_bundle(data)
        if bundle!=expected or combo not in expected['combinations']:raise ValueError('Combinação de área/altura divergente das entradas.')
    s=section_for(data);cg=s['properties']['centroid_xy_mm'];sc=s['properties']['shear_center_xy_mm']
    c=configuration(data);adopted=height_model_adopted(data)
    if bundle is None:
        vectors=[('EXTERNAL',combo['external_q_vector']),('PP',combo['profile_PP_q_vector'])]
    else:
        vectors=[(name,{axis:factor*bundle['case_vectors_N_mm'][name][axis] for axis in ('normal','parallel')})
            for name,factor in combo['coefficients'].items() if name!='P']
    def arm(name):
        from .load_application_policy import active as ct_active, ORIGIN
        if ct_active(data):return 0.,0.,ORIGIN
        if name=='PP':return cg[1]-sc[1],cg[0]-sc[0],'PP uma vez no CG do mesmo contorno.'
        record=c['load_lines'].get(name) if adopted else None
        if not record or not record['declared'] or not record['origin'].strip() or any(v is None for v in record['xy_from_CG_mm']):
            return None,None,'Linha local não declarada: '+name
        dx,dy=record['xy_from_CG_mm']
        return cg[1]+dy-sc[1],cg[0]+dx-sc[0],record['origin']
    out=[]
    for name,v in vectors:
        if not any(v.values()):continue
        h,x,origin=arm(name)
        out.append(dict(name=name,kind='uniform',q_down_N_mm=v['normal'],q_parallel_N_mm=v['parallel'],
            height_above_SC_mm=h,x_from_SC_mm=x,load_line_source=origin))
    v=combo['P_vector']
    if any(v.values()):
        h,x,origin=arm('P')
        out.append(dict(name='P',kind='point',P_down_N=v['normal'],P_parallel_N=v['parallel'],s_mm=combo['x_mm'],
            height_above_SC_mm=h,x_from_SC_mm=x,load_line_source=origin,position=combo.get('point_position','fixed')))
    return out
