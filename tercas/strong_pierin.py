"""Pierin Table 1 U local criticals; separate from immutable workbook data.

Nominal row matching is an adopted app convention, not a reconstructed INSTAB
model. Source G/nu remain unknown. No table scaling or automatic fallback.
"""
import copy
import json
import math
from functools import lru_cache
from pathlib import Path
from .catalogs import catalog_entry, critical_defaults
from .core.selecao import select
from .core.local_table12 import SOURCE as TABLE12_SOURCE

ORIGIN_PREFIX = 'Pierin2013 Tabela1 Mlx U | '
SECTION_FIELDS = ('h','bf','lip','t','A_cm2','Ix_cm4','Wx_cm3','Iy_cm4','J_mm4','Cw_mm6','ri_mm')
USE_LABELS = {
    'adopted_reference_original_configuration':'Mlx tabelado adotado nesta configuração nominal; conferir hipóteses da fonte',
    'reference_only_existing_input_preserved':'Referência documental; entrada legada/manual preservada',
    'not_evaluated_incompatible_pierin_reference':'Mlx tabelado não avaliado; referência incompatível com as entradas',
}


def use_label(reference):
    return USE_LABELS.get(reference.get('use_status'),'Referência documental')


def same(a, b):
    return (isinstance(a, (int, float)) and not isinstance(a, bool)
            and isinstance(b, (int, float)) and not isinstance(b, bool)
            and math.isfinite(a) and math.isfinite(b)
            and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8))


@lru_cache(maxsize=1)
def _database():
    return json.loads((Path(__file__).parent/'data/pierin_2013_U_strong_reference.json').read_text(encoding='utf-8'))


def reference_for_index(index):
    entry = catalog_entry(index)
    if entry['family'] != 'U':
        return {'status':'outside_U_scope','axial_calculation_implemented':False}
    db = _database()
    matches = [r for r in db['entries'] if r['dimensions_mm'] == entry['dimensions_mm']]
    if len(matches) != 1:
        return {'status':'not_tabulated','Mlx_Nmm':None,'Nl_N':None,
                'axial_calculation_implemented':False,
                'reason':'Sem linha nominal U exata na Tabela 1 de Pierin; sem interpolação ou substituição de espessura.'}
    r = {k:copy.deepcopy(v) for k,v in db.items() if k != 'entries'}
    r.update(copy.deepcopy(matches[0]))
    r.update(status='tabulated_adopted_reference',adopted_as_app_reference=True,
             axial_calculation_implemented=False,whole_member_approved=False,
             section_property_convention_pending=True,source_geometry_convention_unresolved=True,
             geometric_adoption='Linha nominal exata; propriedades do catálogo mantidas. A equivalência exata com a discretização INSTAB não foi demonstrada.',
             bending_axis='x — eixo de simetria da seção U; não transpor ao eixo y',
             source_origin=ORIGIN_PREFIX+matches[0]['id']+' | p'+str(matches[0]['printed_page'])+
                           '/PDF'+str(matches[0]['PDF_page'])+'; referência adotada; crítico elástico, não resistência')
    return r


def reference_for_inputs(data):
    r = reference_for_index(data['catalog_index'])
    if r['status'] != 'tabulated_adopted_reference':
        return r
    p = data['properties']; nominal = select(data['catalog_index'])['fields']; reasons = []
    if not same(p.get('E_MPa'), r['source_E_MPa']):
        reasons.append('E difere de 200000 MPa declarado para Pierin.')
    if not same(p.get('G_MPa'), 77000.):
        reasons.append('G difere da configuração original do app; G e ν da fonte não foram explicitados.')
    for key in SECTION_FIELDS:
        expected = nominal[key]['value']; value = p.get(key)
        if not ((expected is None and value is None) or same(expected,value)):
            reasons.append('Propriedade de seção '+key+' difere do catálogo associado à linha nominal Pierin.')
    r.update(app_original_G_MPa=77000.,original_configuration_unchanged=not reasons,
             compatibility_reasons=reasons,
             compatibility_note='G=77000 MPa é detector de alteração do app, não G da fonte. Compatibilidade nominal não certifica o elemento físico.',
             source_input_value_Nmm=data.get('Ml_Nmm'),source_input_origin=data.get('critical_origin',''))
    return r


def qualify(data, *, legacy=None):
    """Return override only for a recognizably inherited Pierin value/origin.

    Legacy Table12 projects and distinct independent manual criticals are not
    rewritten or silently migrated. Equal table values remain inherited even if
    their free-text source is edited. An automatic origin cannot change row/value.
    """
    r = reference_for_inputs(data)
    origin = data.get('critical_origin',''); automatic = ORIGIN_PREFIX in origin
    tabulated = r.get('status') == 'tabulated_adopted_reference'
    table12_origin = (TABLE12_SOURCE in origin and
                     ('; Ml calculado: ' in origin or '; derivação com E do aço selecionado: ' in origin))
    if table12_origin and not automatic:
        # Numerically verified legacy provenance wins over a coincident table
        # number. Reuse the existing qualifier, never duplicate its formula.
        if legacy is None:
            from .strong_critical_guard import qualify_legacy_strong_criticals
            legacy = qualify_legacy_strong_criticals(data)
        old_effective, old_evidence = legacy
        if (old_effective['Ml'].get('value') is not None and
                old_evidence['fields']['Ml'].get('inherited_automatic_table12')):
            r.update(use_status='reference_only_existing_input_preserved',legacy_table12_verified=True)
            return None, r
    inherited = automatic or (tabulated and same(data.get('Ml_Nmm'),r['Mlx_Nmm']))
    if not inherited:
        r['use_status'] = 'reference_only_existing_input_preserved'
        return None, r
    reasons = list(r.get('compatibility_reasons',[]))
    if table12_origin:
        reasons.append('Origem automática Tabela 12 não requalifica um número editado para coincidir com Pierin; selecione a fonte explicitamente.')
    if ('planilha V03, 03_Perfis, linha ' in origin
            and '; valores tabulados, não validação independente' in origin
            and critical_defaults(data['catalog_index'])['critical_origin'] not in origin):
        reasons.append('Origem automática do catálogo não corresponde à seção/linha selecionada.')
    if not tabulated or (automatic and origin != r.get('source_origin')):
        reasons.append('Origem automática Pierin não corresponde à seção/linha selecionada.')
    if tabulated and not same(data.get('Ml_Nmm'),r['Mlx_Nmm']):
        reasons.append('Ml informado difere do Mlx da linha Pierin; não requalificado por edição do valor.')
    if reasons:
        reason = ('Mlx U tabulado de Pierin não avaliado: '+'; '.join(reasons)+
                  ' Sem escala nem fallback automático; valor original preservado para auditoria.')
        r.update(use_status='not_evaluated_incompatible_pierin_reference',reason=reason)
        return {'value':None,'origin':origin,'reason':reason}, r
    r['use_status'] = 'adopted_reference_original_configuration'
    return {'value':data['Ml_Nmm'],'origin':origin}, r
