"""Fixed no-contact/panel domain without mandatory physical inputs or migration."""
import copy,json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from docx import Document
from streamlit.testing.v1 import AppTest
from tercas.application import defaults,example,calculate,build_spec,rows,fingerprint
from tercas.batch import calculate_batch
from tercas.catalog_scan import inputs_for_section
from tercas.model_domain import VERSION,TEXT,ORIGIN,LIMIT,HISTORICAL,evidence,export_inputs
from tercas.weak_axis import capacities

APP=str(Path(__file__).resolve().parents[1]/'app.py')


def base(q=.1):
 d=example();d.update(q_uls=q,P_uls=0.,q_sls=q,P_sls=0.)
 return d


def weak():
 return dict(W_mm3=10000.,Wc_mm3=20000.,Ml_Nmm=4e6,Mdist_Nmm=None,
  Nex_N=1e6,Nez_N=1e6,r0_mm=20.,j_mm=-10.,Cm=1.,Cs=1,
  plain_u_no_distortion=True,provenance='SYNTHETIC same section and weak sense')


def mechanisms(r):
 # Domain evidence may record whether a token was supplied; numbers cannot change.
 out=copy.deepcopy({k:r[k] for k in ('NBR_branches','FLT_segments','section_checks','ELS','inclination_evidence')})
 out['NBR_branches']['distortional'].pop('model_domain',None)
 return out


@pytest.mark.parametrize('q',[.1,-.1,0.])
@pytest.mark.parametrize('declaration',[None,{'condition':'not_declared'}, {'condition':'not_declared','origin':''}, {'condition':'no_flange_panel'}])
def test_fixed_domain_accepts_legacy_and_empty_origin_both_signs(q,declaration):
 d=base(q)
 if declaration is not None:d['u_panel_condition']=copy.deepcopy(declaration)
 frozen=copy.deepcopy(d);h=fingerprint(d);r=calculate(d)
 assert d==frozen and r['input_data']==frozen and r['input_fingerprint']==h
 assert 'model_domain' not in defaults(d['catalog_index']) and 'model_domain' not in example()
 assert r['NBR_branches']['distortional']['status']=='not_applicable'
 assert r['model_domain_evidence']['status']=='fixed_model_domain'
 assert r['model_domain_evidence']['origin']==ORIGIN
 assert not r['model_domain_evidence']['input_token_present']
 assert not r['model_domain_evidence']['physical_conditions_verified']
 assert not r['whole_member_approved']


@pytest.mark.parametrize('q,p',[(1.,-2000.),(-1.,2000.)])
def test_sign_reversal_does_not_invent_panel_exception_inside_fixed_domain(q,p):
 d=base(q);d['P_uls']=p;r=calculate(d)
 assert r['NBR_branches']['distortional']['status']=='not_applicable'
 assert 'sem ligação de mesa a painel' in r['NBR_branches']['distortional']['reason']


@pytest.mark.parametrize('qx,qy',[(.1,.1),(.1,-.1),(-.1,.1),(-.1,-.1),(0.,.1),(0.,-.1)])
def test_fixed_domain_allows_documented_weak_bending_without_new_field(qx,qy):
 d=base(qx);d['q_parallel_uls']=qy;d['weak_axis']={s:weak() for s in ('positive','negative')}
 d['weak_axis']['negative']['Cs']=-1
 r=calculate(d)
 assert r['inclination_evidence']['ELU']['biaxial']['status']=='computed_fixed_position'
 assert all(c.get('MRd_Nmm') for c in capacities(d,'U').values())
 assert not r['whole_member_approved']


@pytest.mark.parametrize('condition',['top_panel_other_free','bottom_panel_other_free','other_specific_analysis'])
@pytest.mark.parametrize('q',[.1,-.1])
def test_explicit_conflict_preserved_and_not_masked_by_mdist_or_manual_flag(condition,q):
 d=base(q);d['u_panel_condition']={'condition':condition,'origin':'SYNTHETIC explicit physical panel'}
 d.update(q_parallel_uls=.1,Mdist_Nmm=1e100)
 d['weak_axis']={s:weak() for s in ('positive','negative')}
 for s in d['weak_axis'].values():s['Mdist_Nmm']=1e100
 before=copy.deepcopy(d);r=calculate(d)
 assert d==before and r['input_data']==before
 assert r['model_domain_evidence']['status']=='outside_fixed_model_domain'
 assert r['model_domain_evidence']['physical_declaration']==before['u_panel_condition']
 assert r['NBR_branches']['distortional']['status']=='not_evaluated'
 assert not any(v.get('MRd_Nmm') for v in capacities(d,'U').values())
 assert r['inclination_evidence']['ELU']['biaxial']['status']=='not_evaluated'
 assert r['critical_warnings'] and not r['whole_member_approved']
 exported=export_inputs(d)
 assert exported['u_panel_condition']==before['u_panel_condition']
 assert calculate(exported)['model_domain_evidence']['conflict']


def test_pierin_optin_cannot_overrule_explicit_physical_conflict():
 from test_u_pierin_optin import opted
 d=opted();d['u_panel_condition']={'condition':'top_panel_other_free'}
 r=calculate(d)
 assert r['weak_sense_assumption']
 assert not r['inclination_evidence']['ELU']['weak_axis_capacities']['positive'].get('MRd_Nmm')


@pytest.mark.parametrize('token',[None,False,1,{},[], 'unrecognized_domain'])
def test_incompatible_token_rejected_without_input_mutation(token):
 d=base();d['model_domain']=token;frozen=copy.deepcopy(d)
 with pytest.raises(ValueError,match='model_domain incompatível'):build_spec(d)
 assert d==frozen


def test_export_reimport_records_domain_without_mutating_legacy_inputs_or_numbers():
 d=base();d['q_parallel_uls']=.1;d['weak_axis']={s:weak() for s in ('positive','negative')}
 frozen=copy.deepcopy(d);before=calculate(d)
 exported=export_inputs(d);reloaded=json.loads(json.dumps(exported,allow_nan=False));after=calculate(reloaded)
 assert d==frozen and 'model_domain' not in d
 assert exported['model_domain']==VERSION
 assert {k:exported[k] for k in d}==d
 assert mechanisms(before)==mechanisms(after)
 for k in ('version','text','origin','limit','status','physical_conditions_verified','conflict'):
  assert before['model_domain_evidence'][k]==after['model_domain_evidence'][k]
 assert after['model_domain_evidence']['input_token_present']
 assert export_inputs(reloaded)==reloaded


def test_batch_export_reimport_and_all_combinations_record_domain():
 d=base();d.update(load_mode='area',selected_types=['ELU normal']);d['area_inputs'].update(wind_up_kgf_m2=60.,wind_down_kgf_m2=40.)
 r=calculate_batch(d);new=calculate_batch(export_inputs(d))
 assert r['summary']==new['summary']
 assert r['model_domain_evidence']['version']==VERSION
 assert r['common_input_snapshot']['model_domain_evidence']['version']==VERSION
 for a,b in zip(r['cases'],new['cases']):
  assert a['rows']==b['rows']
  assert a['evidence']['NBR_branches']['distortional']['model_domain']['version']==VERSION
 assert r['input_data']==d


def test_ue_and_independent_mechanics_unchanged_by_declaration_or_domain_token():
 d=defaults(0);old=calculate(d)
 for changed in (export_inputs(d),dict(d,u_panel_condition={'condition':'not_declared'})):
  r=calculate(changed)
  for k in ('NBR_branches','FLT_segments','section_checks','ELS','inclination_evidence'):assert r[k]==old[k]
 d=base();r0=calculate(d);changed=copy.deepcopy(d);changed['u_panel_condition']={'condition':'top_panel_other_free'};r=calculate(changed)
 for k in ('FLT_segments','section_checks','ELS'):assert r[k]==r0[k]
 for k in r['NBR_branches']:
  if k!='distortional':assert r['NBR_branches'][k]==r0['NBR_branches'][k]
 assert r['input_data']['segments']==d['segments']


def test_profile_application_and_3d_preserve_metadata_without_mechanical_changes():
 from test_three_girt_system import ready
 from tercas.three_girt_application import calculate as diagnostic
 d=ready();frozen=copy.deepcopy(d);r=diagnostic(d);with_token=diagnostic(export_inputs(d))
 assert d==frozen and r['input_data']==frozen
 assert with_token['cases']==r['cases']
 assert r['model_domain_evidence']['version']==VERSION
 for code in ('not_declared','no_flange_panel','top_panel_other_free'):
  changed=copy.deepcopy(d);changed['u_panel_condition']={'condition':code}
  out=diagnostic(changed)
  assert out['cases']==r['cases']
  assert out['input_data']['u_panel_condition']==changed['u_panel_condition']
  assert not out['resistance_qualified'] and not out['ELS_qualified'] and not out['whole_member_approved']
  if code=='top_panel_other_free':assert out['model_domain_evidence']['conflict'] in out['limitations']
 tagged=export_inputs(base());tagged['u_panel_condition']={'condition':'not_declared'}
 for index in (0,tagged['catalog_index']):
  changed=inputs_for_section(tagged,index)
  assert changed['model_domain']==VERSION and changed['u_panel_condition']==tagged['u_panel_condition']
 tagged['member_application']='wall_girt'
 assert calculate(tagged)['model_domain_evidence']['version']==VERSION


def all_text(blob):
 doc=Document(BytesIO(blob))
 return '\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)


def test_reports_current_and_historical_do_not_recalculate_or_requalify():
 from tercas.report import word,batch_word
 d=base();r=calculate(d);assert TEXT in all_text(word(r)) and ORIGIN in all_text(word(r))
 d['load_mode']='area';d['selected_types']=['ELU normal'];batch=calculate_batch(d)
 assert TEXT in all_text(batch_word(batch))
 for item,writer in [(r,word),(batch,batch_word)]:
  item.pop('model_domain_evidence');frozen=copy.deepcopy(item);text=all_text(writer(item))
  assert HISTORICAL in text and TEXT not in text and item==frozen
  assert 'Cada combinação é recalculada.' not in text
 from test_three_girt_system import ready
 from tercas.three_girt_application import calculate as diagnostic
 from tercas.three_girt_report import word as diagnostic_word
 item=diagnostic(ready());text=all_text(diagnostic_word(item))
 assert TEXT in text and ORIGIN in text and 'não conclui atendimento de ELS' in text
 item.pop('model_domain_evidence');frozen=copy.deepcopy(item)
 assert HISTORICAL in all_text(diagnostic_word(item)) and item==frozen


def start_ui(d):
 a=AppTest.from_file(APP);a.session_state.base=copy.deepcopy(d);a.session_state.last_input=copy.deepcopy(d);a.session_state.revision=0
 a.run(timeout=30);assert not a.exception
 return a


def test_ui_fixed_text_no_selector_no_mandatory_origin_and_no_silent_input_change():
 d=base();a=start_ui(d)
 assert not [w for w in a.selectbox if 'painel' in w.label.casefold()]
 assert not [w for w in a.text_input if 'painel' in w.label.casefold()]
 assert TEXT in [v.value for v in a.caption]
 assert 'model_domain' not in a.session_state.last_input
 assert 'u_panel_condition' not in a.session_state.last_input
 next(b for b in a.button if b.label=='Calcular verificações disponíveis').click().run(timeout=30)
 assert not a.exception and a.session_state.result['NBR_branches']['distortional']['status']=='not_applicable'


def test_ui_export_reimport_preserves_numbers_and_rejects_wrong_token_without_clearing(monkeypatch):
 a=start_ui(base());before=copy.deepcopy(a.session_state.last_input)
 payload=json.dumps(export_inputs(before)).encode();upload=SimpleNamespace(size=len(payload),getvalue=lambda:payload)
 monkeypatch.setattr(st,'file_uploader',lambda *args,**kwargs:upload)
 a.run(timeout=30);next(v for v in a.button if v.label=='Aplicar entradas do arquivo').click().run(timeout=30)
 assert not a.exception and a.session_state.last_input==export_inputs(before)
 next(v for v in a.button if v.label=='Calcular verificações disponíveis').click().run(timeout=30)
 original_result=copy.deepcopy(a.session_state.result);current=copy.deepcopy(a.session_state.last_input)
 invalid=copy.deepcopy(current);invalid['model_domain']='other';payload=json.dumps(invalid).encode()
 upload.size=len(payload)
 a.run(timeout=30);next(v for v in a.button if v.label=='Aplicar entradas do arquivo').click().run(timeout=30)
 assert not a.exception and any('model_domain incompatível' in v.value for v in a.error)
 assert a.session_state.last_input==current and a.session_state.result==original_result


def test_ui_profile_application_reload_and_3d_retain_exported_scope():
 a=start_ui(export_inputs(base()));before=copy.deepcopy(a.session_state.last_input)
 a.selectbox(key='member_application_0').set_value('wall_girt').run(timeout=30)
 assert not a.exception and a.session_state.last_input['model_domain']==VERSION
 a.checkbox(key='three_enabled_0').set_value(True).run(timeout=30)
 assert not a.exception and a.session_state.last_input['model_domain']==VERSION
 a.checkbox(key='three_enabled_0').set_value(False).run(timeout=30)
 a.selectbox(key='catalog_0').set_value(0).run(timeout=30)
 assert not a.exception and a.session_state.last_input['model_domain']==VERSION
 a.run(timeout=30);assert a.session_state.last_input['model_domain']==VERSION


def test_removed_rows_stay_removed():
 names={r['Verificação'] for r in rows(calculate(base()))}
 assert not {'Cortante paralelo','Carga concentrada','Shear lag','Casos condicionais'} & names


def historical_conflict():
 return json.loads((Path(__file__).parent/'fixtures/historical_panel_conflict_v044.json').read_text())


def test_real_historical_conflict_is_pending_without_recalculating_or_mutating():
 from tercas.report import word
 r=historical_conflict();frozen=copy.deepcopy(r)
 assert r['inclination_evidence']['ELU']['biaxial']['governing']['index']==pytest.approx(.17084024261786895)
 checks=[v for v in rows(r) if v['Verificação'] in ('Distorcional','Flexão biaxial')]
 assert len(checks)==2
 for row in checks:
  assert 'Fora do domínio' in row['Situação'] and 'histórico' in row['Situação']
  assert row['Índice'] is None and 'Situação histórica:' in row['Observação']
 doc=Document(BytesIO(word(r)));text='\n'.join(p.text for p in doc.paragraphs)
 assert HISTORICAL in text and 'Fora do domínio adotado' in text and TEXT not in text
 assert 'Conclusão resistente histórica pendente' in text
 assert 'Interação concomitante §9.9, N=0:' not in text
 assert '0.17084024261786895' not in text and 'índice histórico: 0,17' in text
 selected=[row for t in doc.tables for row in t.rows if row.cells[0].text in ('Distorcional','Flexão biaxial')]
 assert len(selected)==2 and all('Fora do domínio' in row.cells[1].text for row in selected)
 assert r==frozen
 # A historical file without a contradictory physical declaration is NOT blocked.
 r['input_data'].pop('u_panel_condition');normal=rows(r)
 assert next(v for v in normal if v['Verificação']=='Distorcional')['Situação']=='Não aplicável'
 assert next(v for v in normal if v['Verificação']=='Flexão biaxial')['Índice']==pytest.approx(.17084024261786895)


def test_historical_conflict_batch_summary_and_rows_are_pending():
 from tercas.report import batch_word
 d=base();d.update(load_mode='area',selected_types=['ELU normal']);r=calculate_batch(d)
 r.pop('model_domain_evidence');r['input_data']['u_panel_condition']={'condition':'top_panel_other_free'}
 frozen=copy.deepcopy(r);doc=Document(BytesIO(batch_word(r)))
 selected=[row for t in doc.tables for row in t.rows if row.cells[0].text=='Distorcional']
 assert selected and all('Fora do domínio' in row.cells[3].text for row in selected)
 texts='\n'.join(p.text for p in doc.paragraphs)
 assert 'Distorcional: Fora do domínio' in texts and HISTORICAL in texts
 assert 'Cada combinação é recalculada.' not in texts and r==frozen


def test_ui_retains_historical_object_but_not_current_conclusions_for_conflict():
 r=historical_conflict();a=start_ui(r['input_data'])
 r['input_fingerprint']=fingerprint(a.session_state.last_input)
 a.session_state.result=copy.deepcopy(r);a.run(timeout=30)
 # The manual-input inspection boundary runs before result rendering. It is
 # stricter than the ordinary historical row view and must retain the source.
 assert not a.exception and 'result' not in a.session_state
 assert a.session_state.manual_result_history==r
 assert a.session_state.last_input==r['input_data']
 assert any('modo de inspeção' in v.value for v in a.warning)
 tables=[v.value for v in a.dataframe if 'Verificação' in v.value.columns]
 assert not tables
 assert next(b for b in a.button if b.label=='Calcular verificações disponíveis').disabled
 assert not [v for v in a.dataframe if 'MRd fraco [kN·m]' in v.value.columns]


def test_historical_inclination_presentation_preserves_original_and_normal_legacy():
 from tercas.model_domain import historical_inclination
 r=historical_conflict();before=copy.deepcopy(r);ev=r['inclination_evidence']
 shown=historical_inclination(r,ev)
 assert shown is not ev and r==before
 assert not shown['ELU'].get('weak_axis_capacities')
 assert not shown['ELU'].get('biaxial')
 assert shown['ELU']['states']==ev['ELU']['states']
 assert 'Conclusão resistente histórica pendente' in shown['ELU']['resistance_status']
 r['input_data'].pop('u_panel_condition')
 assert historical_inclination(r,ev) is ev


@pytest.mark.parametrize('conflict,current',[(True,False),(False,False),(True,True)])
def test_historical_catalog_cache_reuse_is_safe_and_preserves_original(monkeypatch,conflict,current):
 state=json.loads((Path(__file__).parent/'fixtures/historical_conflicting_scan_v044.json').read_text())
 if not conflict:state['inputs'].pop('u_panel_condition')
 if current:state['model_domain_version']=VERSION
 a=start_ui(state['inputs']);state['fingerprint']=fingerprint(a.session_state.last_input)
 original_inputs=copy.deepcopy(a.session_state.last_input)
 captured={}
 def download(label,data,*args,**kwargs):captured[label]=data;return False
 monkeypatch.setattr(st,'download_button',download)
 a.session_state.catalog_scan_state=copy.deepcopy(state);a.run(timeout=30)
 assert not a.exception and a.session_state.last_input==original_inputs
 if conflict and not current:
  assert 'catalog_scan_state' not in a.session_state
  assert a.session_state.catalog_scan_history==state
  assert not [v for v in a.dataframe if 'Perfil' in v.value.columns]
  historical=json.loads(captured['Baixar comparação histórica (JSON)'])
  assert historical['historical_not_revalidated'] and historical['original_state']==state
  assert any('Comparação histórica retirada' in v.value for v in a.warning)
 else:
  assert a.session_state.catalog_scan_state==state
  assert 'catalog_scan_history' not in a.session_state
  assert [v for v in a.dataframe if 'Perfil' in v.value.columns]


def test_new_catalog_cache_records_domain_version():
 a=start_ui(base(.001))
 next(v for v in a.button if v.label=='Calcular todas as seções do catálogo').click().run(timeout=30)
 assert not a.exception and a.session_state.catalog_scan_state['model_domain_version']==VERSION


def test_pending_biaxial_report_does_not_print_incomplete_governing_index():
 from tercas.report import word
 d=historical_conflict()['input_data'];r=calculate(d);before=copy.deepcopy(r)
 assert r['inclination_evidence']['ELU']['biaxial']['status']=='not_evaluated'
 assert r['inclination_evidence']['ELU']['biaxial']['governing']['index']==0
 doc=Document(BytesIO(word(r)))
 lines=[p.text for p in doc.paragraphs if p.text.startswith('Interação concomitante §9.9')]
 assert lines and any('not_evaluated' in line and 'missing' in line for line in lines)
 assert all('governing' not in line and 'index:' not in line for line in lines)
 assert r==before
