"""MC presentation only: no new calculation, inferred data, or active verdict."""
import copy,json,math
from io import BytesIO
from contextlib import nullcontext
import pytest
from docx import Document
from tercas.presentation import fmt
from tercas.report_audit import (technical_number,technical_value,saved_issues,issue_text,
    report_mv_trace,report_els_trace,report_saved_issues,show_saved_issues,report_fingerprint)


def paragraphs(doc):return '\n'.join(p.text for p in doc.paragraphs)

def text(blob):
    doc=Document(BytesIO(blob))
    return paragraphs(doc)+'\n'+'\n'.join(c.text for t in doc.tables for r in t.rows for c in r.cells)


@pytest.mark.parametrize('value,expected',[(.012939,'0,012939'),(.0005621287530866161,'0,00056212875'),
    (-.0000001,'-1e-07'),(130.2366000123,'130,2366'),(0.,'0'),(-0.,'0'),(True,'True'),
    (None,'Não registrado'),(float('nan'),'Não finito — não utilizável'),('§9.8.5; 2026.11','§9.8.5; 2026.11')])
def test_selective_precision_never_changes_default_formatter(value,expected):
    assert technical_number(value)==expected
    assert fmt(.012939)=='0,01' and fmt(.00056212875)=='<0,01'


def test_near_threshold_and_subnormal_signs():
    assert technical_number(1+1e-12,limit=1)=='1 (>1)'
    assert technical_number(1-1e-12,limit=1)=='1 (<1)'
    assert technical_number(1.,limit=1)=='1'
    assert technical_number(math.ulp(0.))!='0'
    assert technical_number(-math.ulp(0.)).startswith('-')


def test_nested_precision_is_read_only_and_does_not_rewrite_references():
    obj={'J_mm4':.012939,'ref':'§9.8.5; SHA 0123.45','values':[None,.000001]};old=copy.deepcopy(obj)
    show=technical_value(obj);assert '0,012939' in show and obj['ref'] in show and obj==old


def global_result():
    checks=[]
    for cid in ('C01','C02'):
        checks.append(dict(id='ELU:'+cid+':MV',status='pending',limit_state='ELU',reason='Dados incompletos.',source='NBR14762:2010 9.8.4',diagnostic_index=987.654,trace={'combination_id':cid}))
    checks += [dict(id='torsion_warping',status='pending',limit_state='MODEL',reason='Demanda não qualificada.',source='saved schema',trace={}),
        dict(id='ELU:C03:local',status='fails',limit_state='ELU',reason='Critério não atendido.',source='Fonte salva',trace={'combination_id':'C03'}),
        dict(id='ignored_pass',status='meets',limit_state='ELU',reason='Must not become new conclusion',source='x',trace={}),
        dict(id='ignored_na',status='not_applicable',limit_state='ELU',reason='Excluded',source='x',trace={})]
    return {'global_verification':{'checks':checks,'display_summary':'Resumo original incompleto','status':'inconclusivo','counts':{'pending':999}}}


def test_group_saved_reasons_no_recalculation_counts_or_diagnostic_index():
    r=global_result();old=copy.deepcopy(r);groups=saved_issues(r)
    assert len(groups)==3 and groups[0]['combination_ids']==['C01','C02']
    doc=Document();report_saved_issues(doc,r);s=paragraphs(doc)
    assert 'ELU — Flexão e cortante concomitantes — Pendente no registro' in s
    assert 'C01, C02' in s and 'C03' in s and 'Não atende no registro' in s
    assert '987' not in s and 'Must not become' not in s and r==old
    assert r['global_verification']['counts']['pending']==999


class FakeUI:
    def __init__(self):self.messages=[]
    def caption(self,s):self.messages.append(s)
    def error(self,s):self.messages.append(s)
    def warning(self,s):self.messages.append(s)
    def expander(self,s,expanded=False):self.messages.append(s);return nullcontext()


def test_saved_reasons_ui_matches_word_without_new_checks():
    r=global_result();old=copy.deepcopy(r);ui=FakeUI();show_saved_issues(ui,r)
    assert 'Motivos do estado salvo' in ui.messages
    for g in saved_issues(r):assert issue_text(g) in ui.messages
    assert r==old
    assert saved_issues({})==[] and saved_issues({'global_verification':{'checks':None}})==[]


def mv_result(status='computed_fixed_load_position'):
    return {'NBR_branches':{'MV':{'status':status,'source':'NBR9.8.4 same position and combination',
        'result':{'x_mm':317.123456789,'a_mm':317.,'branch':'a_equals_x_left','index_squared':.44254102217222485}}}}


def test_mv_common_trace_reports_absent_demands_not_reconstructed():
    ev=mv_result();old=copy.deepcopy(ev);doc=Document();report_mv_trace(doc,ev,'CASE_SIGNED',-1500.)
    s=paragraphs(doc);assert 'CASE_SIGNED' in s and '317,12346' in s and '0,44254102' in s
    assert 'lado esquerdo' in s and 'M nesta posição: não registrado' in s and 'V nesta posição: não registrado' in s
    assert ev==old


def test_mv_no_point_does_not_claim_partition_as_physical_load_position():
    doc=Document();report_mv_trace(doc,mv_result(),'NO_P',0.)
    s=paragraphs(doc);assert 'a registrado é partição inativa' in s and 'a registrado=317 mm' not in s


def test_mv_support_limit_keeps_signed_demands_two_states_and_saved_tie():
    a=dict(x_mm=500.,a_mm=None,a_limit='a→0+',position_limit='interior após P no limite',branch='a_bound_left',index_squared=4.,M_Nmm=-125000.,V_N=0.)
    b=dict(x_mm=0.,a_mm=None,a_limit='a→0+',position_limit='a→0+, x<a',branch='support_layer_before_P',index_squared=4.,M_Nmm=0.,V_N=-2000.)
    raw=dict(status='computed',position='support_limit',source='NBR9.8.4 same combination; analytical support limit',result=a,limit_states={'interior_q_only':a,'support_layer':b},governing_state='interior_q_only',governing_states=['interior_q_only','support_layer'])
    ev={'NBR_branches':{'MV':raw}};old=copy.deepcopy(ev);doc=Document();report_mv_trace(doc,ev,'P_ELU_01_APOIO',-1000.)
    s=paragraphs(doc);assert s.count('— governante salvo')==2 and 'a→0+' in s
    assert 'M nesta posição=-0,125 kN·m' in s and 'V nesta posição=-2 kN' in s
    assert 'a registrado=0' not in s and ev==old


def test_mv_pending_candidate_values_are_not_released():
    ev=mv_result('not_evaluated');doc=Document();report_mv_trace(doc,ev,'PENDING',100.)
    s=paragraphs(doc);assert 'Traço não concluído' in s and '0,442' not in s and '317' not in s


def test_els_criterion_and_method_are_separate_and_not_inferred_from_inputs():
    r={'input_data':{'ELS_limit_mm':9999.,'ELS_origin':'not consumed'}}
    e={'ELS':{'status':'computed_bending_component','criterion_status':'meets','deflection_mm':.000123456789,'x_mm':1500.123456789,'limit_mm':.012939,'limit_origin':'Critério fornecido no ensaio','source':'Base normativa já salva'}}
    old=copy.deepcopy((r,e));doc=Document();report_els_trace(doc,r,e,'DIRECT_ELS')
    s=paragraphs(doc);assert 'Base do método: Base normativa já salva' in s and 'Limite declarado salvo: 0,012939 mm' in s
    assert 'Critério fornecido no ensaio' in s and '0,00012345679' in s and '9999' not in s
    assert 'não define por si só o limite adotado' in s and 'Atende' not in s and (r,e)==old


def test_els_missing_limit_does_not_use_declared_input_or_zero():
    r={'input_data':{'ELS_limit_mm':22.}};e={'ELS':{'status':'not_evaluated','criterion_status':'missing_declared_limit'}}
    doc=Document();report_els_trace(doc,r,e,'C')
    s=paragraphs(doc);assert 'Limite declarado salvo: não disponível' in s and 'Grandeza ELS não disponível' in s and '22' not in s


def test_uncontracted_upper_bound_is_not_promoted_as_conservative():
    doc=Document();report_els_trace(doc,{}, {'ELS':{'upper_bound_mm':.1,'limit_mm':1.}},'UNKNOWN')
    assert not doc.paragraphs


@pytest.fixture(scope='module')
def aa_result():
    from tercas import ue_family_reference as family,aa_component as aa
    from tercas.application import calculate
    from tercas.study_completion import complete_result
    d=family.load_reference(1.5,4000.,5.)
    d.update(load_mode='direct',q_sls=0.,q_parallel_sls=.305,P_sls=0.,P_parallel_sls=0.,x_sls=2000.)
    return complete_result(calculate(aa.activate(d)))


def test_full_word_technical_precision_and_saved_els_without_live_solver(aa_result,monkeypatch):
    from tercas import aa_component as aa
    from tercas.report import word
    r=copy.deepcopy(aa_result);old=copy.deepcopy(r)
    def denied(*a,**k):pytest.fail('Reading MC must not calculate or load live proof')
    monkeypatch.setattr(aa,'_bundle',denied);monkeypatch.setattr(aa,'_sources',denied)
    monkeypatch.setattr('tercas.application.calculate',denied);monkeypatch.setattr('tercas.study_completion.complete_result',denied)
    s=text(word(r));assert '0,075064244 mm' in s and 'não flecha exata' in s
    assert 'Motivos do estado salvo' in s and 'Não é prescrição normativa automática' in s
    j=technical_number(r['input_snapshot']['selected_section']['fields']['J_mm4']['value']);assert j in s
    assert r==old


def test_invalid_aa_ui_and_word_warn_same_saved_summary_and_hide_new_detail(aa_result):
    from tercas import aa_component as aa,aa_component_ui as ui
    from tercas.report import word
    r=copy.deepcopy(aa_result);r[aa.FIELD]['snapshot_sha256']='0'*64;old=copy.deepcopy(r)
    fake=FakeUI();ui.show(fake,r)
    assert ui.SAVED_GLOBAL_NOTICE in fake.messages
    s=text(word(r));assert ui.SAVED_GLOBAL_NOTICE in s and 'Critério e grandeza ELS salvos' not in s
    assert r['global_verification']['display_summary'] in s and r==old


def test_final_fingerprint_stays_with_previous_body():
    doc=Document();p=doc.add_paragraph('Último trecho completo.')
    report_fingerprint(doc,'abc123')
    assert p.paragraph_format.keep_with_next is True
    assert doc.paragraphs[-1].paragraph_format.keep_together is True


@pytest.mark.parametrize('kind',['legacy','empty','wrong_result','finite_position'])
def test_support_incomplete_saved_trace_never_promotes_interior_adapter(kind):
    ev=mv_result('computed');raw=ev['NBR_branches']['MV']
    if kind!='legacy':raw.update(position='support_limit',limit_states={},governing_state='interior_q_only')
    if kind in ('wrong_result','finite_position'):
        a=dict(x_mm=500.,a_mm=None,a_limit='a→0+',index_squared=.25)
        b=dict(x_mm=0.,a_mm=None,a_limit='a→0+',index_squared=.5625)
        raw['limit_states']={'interior_q_only':a,'support_layer':b}
        if kind=='finite_position':a['a_mm']=500.;raw['result']=a
    before=copy.deepcopy(ev);doc=Document();report_mv_trace(doc,ev,'OLD_APOIO',1500.,point_position='support_limit',expected_a_mm=0.)
    s=paragraphs(doc);assert 'Traço M–V legado, incompleto ou inconsistente' in s
    assert 'Estado governante salvo' not in s and 'a registrado=' not in s and 'Σ índices² registrado=' not in s
    assert 'Estados limites distintos preservados' not in s and ev==before


def test_finite_position_mismatch_is_not_hidden_by_case_label():
    doc=Document();report_mv_trace(doc,mv_result(),'C',100.,point_position='center',expected_a_mm=500.)
    s=paragraphs(doc);assert 'posição divergente da combinação salva' in s and '0,442' not in s


def test_missing_case_identity_is_not_assumed_to_be_common_model_scope():
    r={'global_verification':{'checks':[dict(id='unknown_ELU',limit_state='ELU',status='pending',reason='',source='',trace={})]}}
    s=issue_text(saved_issues(r)[0]);assert 'combinação/escopo não registrado' in s and 'escopo comum do modelo' not in s


@pytest.mark.parametrize('change',['declared_list','winner_list','contradictory_list','false_max','missing_tie','duplicate_winner'])
def test_support_governing_names_and_saved_maximum_must_be_coherent(change):
    a=dict(x_mm=500.,a_mm=None,a_limit='a→0+',index_squared=.25)
    b=dict(x_mm=0.,a_mm=None,a_limit='a→0+',index_squared=.5625)
    raw=dict(status='computed',position='support_limit',result=b,
        limit_states={'interior_q_only':a,'support_layer':b},governing_state='support_layer',governing_states=['support_layer'])
    if change=='declared_list':raw['governing_state']=[]
    elif change=='winner_list':raw['governing_states']=[[]]
    elif change=='contradictory_list':raw['governing_states']=['interior_q_only']
    elif change=='false_max':raw.update(result=a,governing_state='interior_q_only',governing_states=['interior_q_only'])
    elif change=='missing_tie':a['index_squared']=b['index_squared']
    else:raw['governing_states']=['support_layer','support_layer']
    ev={'NBR_branches':{'MV':raw}};before=copy.deepcopy(ev);doc=Document()
    report_mv_trace(doc,ev,'CORRUPT_APOIO',1500.,point_position='support_limit')
    s=paragraphs(doc);assert 'incompleto ou inconsistente' in s
    assert 'governante salvo;' not in s and 'Σ índices² registrado=' not in s and ev==before


def test_nontextual_branch_cannot_crash_saved_report():
    ev=mv_result();ev['NBR_branches']['MV']['result']['branch']=[]
    doc=Document();report_mv_trace(doc,ev,'MALFORMED_BRANCH',0.)
    assert 'identificador não textual' in paragraphs(doc)
