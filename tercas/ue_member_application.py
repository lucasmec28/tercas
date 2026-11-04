"""Explicit application contract for an isolated own-reference Ue member.

No source property, critical, support or force is inferred from a new label.
The transformation preserves local actions; roof values can remain inactive.
"""
import copy
import math

FIELD='own_ue_isolated_application'
SCHEMA='own_Ue_isolated_application_20261104_v1'
KINDS=('purlin','wall_girt')
LABELS={'purlin':'Terça de cobertura','wall_girt':'Travessa lateral isolada — boca para baixo'}
TEXT=('Travessa isolada biapoiada Ue, boca para baixo: normal é horizontal, paralelo é vertical. '
      'Vento normal ao fechamento; PP/permanentes verticais no vão livre. '
      'Sem crédito de tirantes/molas, fechamento ou redistribuição de três travessas. '
      'N=B=0 designa somente a componente flexional, não comprova ações físicas nulas. '
      'Torção, ligações, introdução local e aprovação global permanecem fora deste contrato.')


def token(kind):
    if kind not in KINDS:raise ValueError('Aplicação própria desconhecida.')
    return dict(schema=SCHEMA,member_application=kind,
                structural_model='isolated_simply_supported_member',
                tie_or_cladding_stiffness_credit=False,three_girt_redistribution=False)


def valid_token(supplied,kind):
    return (isinstance(supplied,dict) and kind in KINDS and supplied==token(kind)
        and all(type(supplied.get(k)) is bool for k in ('tie_or_cladding_stiffness_credit','three_girt_redistribution')))


def expected(canonical,data):
    """Build a declared application vector from the unchanged numeric source."""
    from .member_application import member_kind,ELS_DEFAULTS
    kind=member_kind(data)
    if FIELD not in data:
        if kind!='purlin':raise ValueError('Travessa própria requer aplicação explícita do novo contrato isolado; alterar somente o rótulo não ativa a fonte.')
        return canonical
    supplied=data[FIELD]
    if not valid_token(supplied,kind):
        raise ValueError('Contrato de aplicação própria inválido ou divergente da aplicação.')
    out=copy.deepcopy(canonical);out.update(member_application=kind,wall_els=copy.deepcopy(ELS_DEFAULTS))
    out[FIELD]=token(kind)
    if 'ue_model' in out:out['ue_model']['member_application']=kind
    if 'ue_family_model' in out:out['ue_family_model']['member_application']=kind
    return out


def editable(data):
    return {'wall_els'} if FIELD in data else set()


def editor_errors(data):
    if FIELD not in data:return []
    from .member_application import ELS_DEFAULTS
    cfg=data.get('wall_els')
    if not isinstance(cfg,dict) or set(cfg)!=set(ELS_DEFAULTS):
        return ['wall_els próprio exige os cinco campos preservados do critério.']
    errors=[]
    if not isinstance(cfg.get('origin'),str):errors.append('Origem wall_els deve ser texto.')
    for key in set(ELS_DEFAULTS)-{'origin'}:
        v=cfg[key]
        if v is not None:
            try:ok=type(v) in (int,float) and math.isfinite(v) and float(v)==v
            except (ValueError,TypeError,OverflowError):ok=False
            if not ok:errors.append('Valor wall_els não editável sem perda: '+key)
    return errors


def apply(data,kind):
    """Explicit change only. No rotations, zeroing, load additions or index reuse."""
    from . import ue_family_reference as family,ue_reference as single
    module=family if family.claims_reference(data) else single
    state=module.assess(data)
    if not state.get('active'):raise ValueError('Ative fonte própria íntegra antes de mudar sua aplicação.')
    token(kind)
    canonical=(family.source(data['properties']['t'],data['L_mm'],data['inclination']['value'])
               if module is family else single.source(L_mm=data['L_mm'],angle=data['inclination']['value']))
    declaration=dict(member_application=kind,**{FIELD:token(kind)})
    out=expected(canonical,declaration)
    for key in module.EDITABLE:
        if key in data:out[key]=copy.deepcopy(data[key])
        else:out.pop(key,None)
    if 'wall_els' in data:out['wall_els']=copy.deepcopy(data['wall_els'])
    return module.activate(out)


def annotate_evidence(record,data):
    """Add the new context only to explicitly contracted results; old output equal."""
    if FIELD not in data:return record
    from .member_application import wall_convention,normal_els_limit
    out=copy.deepcopy(record);kind=data['member_application']
    out['application_contract']=copy.deepcopy(data[FIELD]);out['member_application']=kind
    out['model']['member_application']=kind
    if kind=='wall_girt':
        out['scope']+=' '+TEXT
        out['application_convention']=wall_convention()
        out['normal_component_limit']=normal_els_limit(data)
    return out


def validate_saved_context(data,source):
    """Check saved application links only; no live source or mechanical solve."""
    model=source.get('model')
    has_context=(FIELD in data or 'wall_els' in data or
        any(k in source for k in ('application_contract','member_application','normal_component_limit','application_convention')) or
        (isinstance(model,dict) and 'member_application' in model))
    if not has_context:return
    from .member_application import normal_els_limit,wall_convention
    kind=data.get('member_application','purlin')
    declaration=data.get(FIELD);saved=source.get('application_contract')
    model=source.get('model')
    if (not valid_token(declaration,kind) or not valid_token(saved,kind)
        or saved!=declaration or source.get('member_application')!=kind
        or not isinstance(model,dict) or model.get('member_application')!=kind):
        raise ValueError('Vínculo de aplicação própria salvo incompatível entre entrada e fonte.')
    if kind=='wall_girt':
        import math
        limit=source.get('normal_component_limit');expected_limit=normal_els_limit(data)
        if (not isinstance(limit,dict) or set(limit)!={'value','origin'}
            or type(limit.get('value')) not in (int,float) or not math.isfinite(limit['value'])
            or limit!=expected_limit or source.get('application_convention')!=wall_convention()):
            raise ValueError('Eixos/critério horizontal da fonte salva divergentes da travessa.')
    elif any(k in source for k in ('normal_component_limit','application_convention')):
        raise ValueError('Fonte salva de terça contém contexto de travessa incompatível.')
