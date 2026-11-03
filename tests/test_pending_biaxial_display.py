"""Missing resistance must not turn a placeholder into a zero-demand result."""
import copy
from io import BytesIO
import pytest
from docx import Document
from tercas.weak_axis import rows


@pytest.mark.parametrize('index',[0.,.5,1.])
def test_incomplete_governing_is_not_reported_as_the_demand(index):
 ev={'biaxial':{'status':'not_evaluated','missing':['negative'],
      'governing':{'index':index,'x_mm':0.,'Mx_Nmm':0.,'My_Nmm':0.}},
     'resistance_status':'Resistência por sentido pendente.'}
 before=copy.deepcopy(ev);row=rows(ev)
 assert row['Índice'] is None
 assert 'Máximo combinado não determinado' in row['Demanda / valor']
 assert 'Seção x=0' not in row['Demanda / valor']
 assert ev==before


@pytest.mark.parametrize('status,index',[('not_evaluated',1.2),('computed_fixed_position',0.),('computed_fixed_position',.5)])
def test_known_partial_failure_and_complete_results_retain_their_section(status,index):
 ev={'biaxial':{'status':status,'governing':{'index':index,'x_mm':1500.,'Mx_Nmm':100000.,'My_Nmm':50000.}},
     'resistance_status':'Estado de controle declarado.'}
 row=rows(ev)
 assert row['Índice']==index
 assert row['Demanda / valor']=='Seção x=1500.0 mm; Mx=100000.0 Nmm; My=50000.0 Nmm'


def test_real_conflict_preserves_nonzero_actions_without_zero_demand_claim():
 from test_model_domain import base,weak
 from tercas.application import calculate,rows as application_rows
 from tercas.report import word
 d=base(.12);d['q_parallel_uls']=.1
 d['weak_axis']={s:weak() for s in ('positive','negative')}
 d['u_panel_condition']={'condition':'top_panel_other_free'}
 result=calculate(d);before=copy.deepcopy(result)
 ev=result['inclination_evidence']['ELU']
 assert any(abs(s['normal']['M_Nmm'])>0 and abs(s['parallel']['M_Nmm'])>0 for s in ev['states'])
 row=next(x for x in application_rows(result) if x['Verificação']=='Flexão biaxial')
 assert row['Índice'] is None and 'Máximo combinado não determinado' in row['Demanda / valor']
 doc=Document(BytesIO(word(result)))
 detail=[p.text for p in doc.paragraphs if p.text.startswith('Flexão biaxial | Valor:')]
 assert len(detail)==1 and 'Máximo combinado não determinado' in detail[0]
 assert 'Seção x=0' not in detail[0]
 assert result==before
