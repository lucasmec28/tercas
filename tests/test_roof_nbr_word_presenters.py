"""Reconstructed saved-synthetic Word checks; no structural solver."""
import copy
import json
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import pytest
from docx import Document
from tercas import roof_top_nbr as nbr,roof_top_nbr_ui as ui,roof_top_load as roof
from tercas import report as report_module,application

@pytest.fixture(scope='module')
def historical():
    return json.loads((Path(__file__).parent/'fixtures/ue125_roof_nbr_v1_reader.json').read_text())

@pytest.fixture(scope='module')
def current(historical):
    return nbr.attach(copy.deepcopy(historical))

def raw_rows():
    return [dict(Verificação='FLT — trecho 1',Situação='Não avaliado',Índice=None,
        **{'Demanda / valor':'—','Resistência / limite':'—','Referência':'Synthetic saved row',
           'Observação':'Synthetic presentation harness','Combinação':'DIRECT_ELU'})]

def legacy(result):
    return SimpleNamespace(rows=lambda rows,cid=None:ui.presentation_rows(result,rows,cid),
        inclination=lambda evidence,cid=None:ui.presentation_inclination(result,evidence,cid),
        report=lambda doc:ui.report(doc,result),validate_global=lambda current:nbr.validate_saved_global(current))

def xml(blob):
    with ZipFile(BytesIO(blob)) as z:return {k:z.read(k) for k in z.namelist()}

@pytest.mark.parametrize('kind',['current','historical'])
def test_every_formatter_matches_public_api(kind,request):
    result=request.getfixturevalue(kind);before=copy.deepcopy(result);p=ui._word_presenters(result)
    for cid in (None,'DIRECT_ELU','DIRECT_ELS','UNRECORDED'):
        assert p.rows(raw_rows(),cid)==ui.presentation_rows(result,raw_rows(),cid)
        evidence={'ELU':{'states':[]}} if cid is None else {'states':[]}
        assert p.inclination(evidence,cid)==ui.presentation_inclination(result,evidence,cid)
    a=Document();b=Document();p.report(a);ui.report(b,result)
    assert a._element.xml==b._element.xml
    assert result==before

def test_no_mutable_aliases_and_new_emission_revalidates(current):
    result=copy.deepcopy(current);p=ui._word_presenters(result)
    expected=p.rows(raw_rows(),'DIRECT_ELU');shown=p.rows(raw_rows(),'DIRECT_ELU')
    shown[0]['Índice']=999
    inclination=p.inclination({'states':[]},'DIRECT_ELU')
    if 'strong_capacity_Nmm' in inclination:inclination['strong_capacity_Nmm']=999
    assert p.rows(raw_rows(),'DIRECT_ELU')==expected
    result[nbr.FIELD]['records'][0]['index']=999
    with pytest.raises(ValueError,match='outro resultado'):p.validate_global(result)
    fresh=ui._word_presenters(result)
    assert 'inválida' in fresh.rows(raw_rows(),'DIRECT_ELU')[0]['Observação']
    assert p.rows(raw_rows(),'DIRECT_ELU')==expected

def test_context_cannot_validate_another_result(current):
    from tercas.study_completion import _report_global
    a=copy.deepcopy(current);a['global_verification']=dict(display_summary='DO NOT DISPLAY',status='inconclusivo',checks=[])
    p=ui._word_presenters(a);b=copy.deepcopy(a);b['input_data']['L_mm']+=1
    doc=Document();_report_global(doc,b,roof_nbr_presentation=p)
    text='\n'.join(x.text for x in doc.paragraphs)
    assert 'Panorama não exibido' in text and 'DO NOT DISPLAY' not in text

@pytest.mark.parametrize('change',['absent','index','rehash','nan'])
def test_absent_corrupt_and_rehashed_lots_keep_existing_output(current,change):
    r=copy.deepcopy(current)
    if change=='absent':r.pop(nbr.FIELD)
    else:
        r[nbr.FIELD]['records'][0]['index']=float('nan') if change=='nan' else 999.
        if change=='rehash':r[nbr.FIELD]['snapshot_sha256']=roof.digest({k:v for k,v in r[nbr.FIELD].items() if k!='snapshot_sha256'})
    p=ui._word_presenters(r)
    assert p.rows(raw_rows(),'DIRECT_ELU')==ui.presentation_rows(r,raw_rows(),'DIRECT_ELU')
    assert p.inclination({'states':[]},'DIRECT_ELU')==ui.presentation_inclination(r,{'states':[]},'DIRECT_ELU')
    a=Document();b=Document();p.report(a);ui.report(b,r)
    assert a._element.xml==b._element.xml

def test_absent_historical_optional_none_containers():
    r=dict(roof_top_load_evidence=None,load_bundle=None)
    p=ui._word_presenters(r)
    assert p.rows(raw_rows())==raw_rows() and p.inclination({'states':[]})=={'states':[]}
    p.validate_global(r);doc=Document();p.report(doc);assert not doc.paragraphs

def harness(current):
    """Formatting workload, not a newly calculated area batch or new proof."""
    r=copy.deepcopy(current);combos=roof.combination_inventory(r)
    r.update(project='Synthetic presentation harness, not a calculated batch',version='QA',synthetic=True,
        global_verification=dict(display_summary='Synthetic saved panorama',status='inconclusivo',checks=[]),
        NBR_branches={'local':{}},FLT_segments=[],section_checks={},
        input_snapshot={'selected_section':{'fields':{}}},summary=raw_rows())
    r['load_bundle']=dict(inputs={},case_q_N_mm={},combinations=combos)
    r['cases']=[]
    for c in combos:
        c=copy.deepcopy(c);c.setdefault('expression','Synthetic saved combination');c.setdefault('q_kN_m',c['q_N_mm'])
        r['cases'].append(dict(combination=c,rows=raw_rows(),evidence={'inclination':{'states':[],'angle':{'degrees':0.,'percent':0.}}},warnings=[]))
    return r

@pytest.mark.parametrize('kind',['direct','batch'])
def test_word_one_nbr_validation_and_identical_xml(current,monkeypatch,kind):
    r=harness(current);before=json.dumps(r,sort_keys=True)
    def saved_rows(result,roof_formatter=None):
        return roof_formatter(raw_rows()) if roof_formatter is not None else ui.presentation_rows(result,raw_rows())
    monkeypatch.setattr(application,'_rows',saved_rows)
    monkeypatch.setattr(report_module,'datetime',SimpleNamespace(now=lambda tz:datetime(2026,11,6,tzinfo=timezone.utc)))
    original=nbr.preserved;calls=[]
    def counted(result):calls.append(1);return original(result)
    monkeypatch.setattr(ui,'preserved',counted);monkeypatch.setattr(nbr,'preserved',counted)
    fn=report_module.word if kind=='direct' else report_module.batch_word
    optimized=fn(r);assert len(calls)==1
    calls.clear();monkeypatch.setattr(ui,'_word_presenters',legacy)
    baseline=fn(r);assert len(calls)>1
    assert xml(optimized)==xml(baseline)
    assert json.dumps(r,sort_keys=True)==before
