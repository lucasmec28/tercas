from .presentation import fmt, display, display_records, measurement_text, DISPLAY_NOTE
from io import BytesIO
from datetime import datetime,timezone
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .application import rows
from .homogeneous_reference import report as homogeneous_reference_report
from .ue_reference import report as ue_reference_report
from .ue_family_reference import report as ue_family_reference_report
from .model_domain import report as domain_report,historical_rows,historical_inclination
from .member_application import is_girt,wall_els_config,wall_convention
from .deflection_scope import report as deflection_scope_report
from .flexural_components import presentation_rows as gross_component_rows,is_girt_result
from .roof_top_nbr_ui import presentation_rows as roof_nbr_rows, presentation_inclination as roof_nbr_inclination
from .biaxial_component_ui import report as gross_component_report
from .aa_component_ui import report as aa_component_report
from .aa_component import claims_result as aa_claims_result
from .report_audit import (TECHNICAL_NOTE,technical_value,report_mv_trace,report_els_trace,report_fingerprint,component_record_is_readable)

def wall_input_report(doc,data):
 cfg=wall_els_config(data)
 doc.add_heading('Travessa lateral — eixos, ações e critérios declarados',2)
 doc.add_paragraph(wall_convention())
 doc.add_paragraph('Sem SC usual e sem P de manutenção de cobertura automáticos no modo por área. Isso é premissa deste cenário, não dispensa universal de ações. Cargas especiais exigem avaliação e componentes combinadas informadas; a convenção de PP direto consta no registro das ações.')
 doc.add_paragraph('Vão do modelo: '+fmt(data['L_mm'])+' mm. Lref horizontal: '+fmt(cfg['normal_reference_mm'])+' mm / '+fmt(cfg['normal_denominator'])+'; Lref vertical: '+fmt(cfg['vertical_reference_mm'])+' mm / '+fmt(cfg['vertical_denominator'])+'. Origem: '+cfg['origin'])
 doc.add_paragraph('Esses Lref definem apenas critérios declarados de deslocamento; não encurtam o vão do modelo nem comprimentos de FLT. Referências L/180 e L/120 da literatura histórica não comprovam condições físicas dos tirantes ou prescrição normativa atual para qualquer caso.')
 doc.add_paragraph('Inclinação de cobertura armazenada, inativa nesta aplicação: '+display(data.get('inclination',{}))+'.')

def wall_vertical_report(doc,container):
 if 'elastic_vertical' not in container:return
 doc.add_heading('Flecha vertical — diagnóstico elástico do eixo fraco',2)
 for key,label in [('elastic_vertical','Vão livre, sem crédito dos tirantes'),('elastic_tie_study','Estudo condicional com tirantes')]:
  if key not in container:continue
  item=container[key];doc.add_paragraph(label+': '+item['status']+'. '+item['scope'])
  if item.get('reason'):doc.add_paragraph(item['reason'])
  doc.add_paragraph('L do modelo='+fmt(item['L_model_mm'])+' mm; Lref do critério='+fmt(item['L_reference_mm'])+' mm; limite declarado='+fmt(item['declared_limit_mm'])+' mm. Sem índice ELS: Iy bruto não substitui Ief qualificado.')
  if item.get('hypothesis'):doc.add_paragraph('Hipóteses declaradas, não comprovadas automaticamente: '+display(item['hypothesis']))
  model=item.get('model')
  if model:
   maximum=model['deflection_max_abs'];doc.add_paragraph('Flecha bruta extrema='+fmt(maximum['value_mm'])+' mm em x='+fmt(maximum['x_mm'])+' mm. My mínimo='+fmt(model['My_min']['value_Nmm']/1e6)+' kN·m; My máximo='+fmt(model['My_max']['value_Nmm']/1e6)+' kN·m.')
   if model['springs']:
    table=doc.add_table(rows=1,cols=4);table.style='Table Grid';table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    for cell,title in zip(table.rows[0].cells,['x [mm]','k [N/mm]','Força para cima [N]','Estado']):cell.text=title
    for spring in model['springs']:
     row=table.add_row();row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
     for cell,value in zip(row.cells,[fmt(spring['x']),fmt(spring['k']),fmt(spring['reaction_up_N']),'Ativo em tração' if spring['active'] else 'Frouxo']):cell.text=value
   reactions=model['end_reactions_up_N'];doc.add_paragraph('Reações verticais dos apoios, positivas para cima: esquerda='+fmt(reactions[0])+' N; direita='+fmt(reactions[1])+' N. Reação negativa exige retenção contra levantamento; os apoios bilaterais são hipótese do modelo, não ligação verificada.')
   warning_pt={
    'Conditional constant-Ig Euler–Bernoulli diagnostic; not Ief or approval.':'Diagnóstico Euler–Bernoulli condicional, com inércia bruta constante; não Ief nem aprovação.',
    'Fixed spring anchors and stated stiffness are assumptions, not qualified physical data.':'Ancoragem fixa e rigidezes declaradas são hipóteses, não dados físicos qualificados.',
    'No change to FLT, strength, interaction, or regulatory ELS reference length.':'Sem alteração de FLT, resistência, interação ou comprimento de referência ELS.',
    'End supports are bilateral; no gap, prestress, torsion, shear or connection deformation.':'Modelo com apoios bilaterais; sem folga, pré-tensão, torção, deformação de cisalhamento ou de ligação.',
    'Negative My occurs: compression side can reverse; resistance is not assessed.':'Há My negativo: o lado comprimido pode inverter; essa resistência não está avaliada.',
    'End uplift reaction: bilateral support assumption requires physical verification.':'Há reação de levantamento na extremidade: a hipótese de apoio bilateral requer verificação física.',
    'Spring-law residual exceeds numerical diagnostic threshold; very stiff springs may be ill-conditioned. Do not silently accept.':'Resíduo da lei da mola excede tolerância diagnóstica; mola muito rígida pode causar mau condicionamento. Não aceitar silenciosamente.'}
   for warning in model.get('warnings',[]):doc.add_paragraph('Alerta do diagnóstico: '+warning_pt.get(warning,warning))
   doc.add_paragraph('Resíduos numéricos do diagnóstico: '+display(model['residuals']))
  if item.get('warning'):doc.add_paragraph(item['warning'])
 doc.add_paragraph('Molas verticais são hipóteses de rigidez e ancoragem fixa, tração apenas, sem folga/pré-tensão. A viga permanece contínua: não se substitui L por L/n. Momento negativo pode inverter a compressão; esta redistribuição não foi incorporada à resistência do modelo de vão livre. Não conclui atendimento de ELS, tirantes, ligações ou elemento.')

def inclination_report(doc,evidence):
 if not isinstance(evidence,dict):return
 if 'states' not in evidence:
  for label,item in evidence.items():
   if isinstance(item,dict):
    doc.add_heading(display(label)+' — esforços locais',2);inclination_report(doc,item)
  return
 angle=evidence.get('angle',{})
 wall=evidence.get('member_application')=='wall_girt'
 doc.add_paragraph('Orientação da travessa: boca para baixo; eixos locais girados 90 graus.' if wall else 'Inclinação: '+fmt(angle['degrees'])+' graus; '+fmt(angle['percent'])+' %. Valores exibidos arredondados; cálculo usa precisão completa.')
 doc.add_paragraph(evidence.get('convention','Esforços simultâneos na mesma seção e combinação.'))
 doc.add_paragraph(evidence.get('resistance_status','Resistência biaxial não avaliada.'))
 if evidence.get('weak_axis_capacities'):
  doc.add_heading('Resistências do eixo fraco por sentido',3)
  for sign,cap in evidence['weak_axis_capacities'].items():
   doc.add_paragraph(('My positivo' if sign=='positive' else 'My negativo')+': '+display(cap))
  biax=evidence.get('biaxial')
  # An unfinished candidate is not a calculated interaction index.
  if isinstance(biax,dict) and biax.get('status')=='not_evaluated':
   biax={k:v for k,v in biax.items() if k!='governing'}
  doc.add_paragraph('Interação concomitante §9.9, N=0: '+display(biax))
  doc.add_paragraph('MxRd conservador adotado [Nmm]: '+display(evidence.get('strong_capacity_Nmm')))
 doc.add_paragraph('Cargas locais: q [N/mm]='+display(evidence.get('q_vector'))+'; P [N]='+display(evidence.get('P_vector'))+'.')
 for state in evidence.get('states',[]):
  p=doc.add_paragraph(state.get('position_limit','Posição fixa')+' — seção x='+display(state.get('x_mm'))+' mm; lado '+{'left':'esquerda','right':'direita'}.get(state.get('side'),'—')+' (momentos concomitantes, não soma de máximos independentes):');p.paragraph_format.keep_with_next=True
  for axis,label in ([('normal','Horizontal normal ao fechamento / eixo forte'),('parallel','Vertical paralelo ao fechamento / eixo fraco')] if wall else [('normal','Normal / eixo forte'),('parallel','Paralelo / eixo fraco')]):
   v=state.get(axis,{})
   p=doc.add_paragraph(label+': '+ '; '.join(title+'='+fmt(v[k]/scale) for k,title,scale in [('M_Nmm','M [kN·m]',1e6),('V_N','V [kN]',1000),('Rleft_N','Reação esquerda [kN]',1000),('Rright_N','Reação direita [kN]',1000)] if k in v));p.paragraph_format.keep_together=True;p.paragraph_format.keep_with_next=(axis=='normal')
 doc.add_paragraph('Travessa por área: não há P de cobertura automática. No modo direto, P permanece na posição declarada. Esforços resistentes são do vão livre; estudo elástico de tirantes é separado. Não há conclusão biaxial sem resistência aplicável por eixo e sentido.' if wall else 'A tabela de seções ilustra solicitações locais. Quando disponível, o resultado §9.9 acima identifica o máximo concomitante para P fixa, calculado separadamente. No modo por área, P é avaliada nas duas posições prescritas, sem varredura intermediária; no modo direto, na posição informada. Não há conclusão biaxial sem resistência aplicável por eixo e sentido; os críticos fortes não são reutilizados no eixo fraco.')

def weak_reference_report(doc,reference):
 if not reference:return
 doc.add_heading('Ml,y — referência oficial adotada: Pierin2013',2)
 if reference.get('status')=='not_tabulated':
  doc.add_paragraph(reference['reason']);return
 doc.add_paragraph('Ml,y tabelado = '+fmt(reference['Mly_Nmm']/1e6)+' kN·m; Tabela '+str(reference['table'])+', p'+str(reference['printed_page'])+'/PDF'+str(reference['PDF_page'])+'. Geometria nominal: '+display(reference['dimensions_mm'])+'.')
 doc.add_paragraph(reference['title']+'; '+reference['url'])
 doc.add_paragraph('Fonte: E=200000 MPa, apoios simples e cantos retos. G e ν não explicitados; conversão exata do modelo INSTAB para linha média não demonstrada. O G original do app é detector de alteração, não dado atribuído à fonte.')
 doc.add_paragraph('Valor oficial da referência adotada não é resistência nem qualificação de sentido. A tabela não explicita o lado comprimido; Ue conserva somente a hipótese previamente autorizada para alma comprimida. Novos valores U não são atribuídos automaticamente. Sem importação bilateral ou Mdist,y presumido.')
 for reason in reference.get('compatibility_reasons',[]):doc.add_paragraph('Incompatibilidade da configuração atual: '+reason)
 doc.add_paragraph('Identidade do PDF fonte SHA256: '+reference['source_pdf_sha256'])

def strong_reference_report(doc,reference):
 from .strong_pierin import use_label
 if not reference or reference.get('status')=='outside_U_scope':return
 doc.add_heading('Mlx / Nl U — referência oficial adotada: Pierin2013',2)
 if reference.get('status')=='not_tabulated':
  doc.add_paragraph(reference['reason']);return
 doc.add_paragraph('Mlx tabelado = '+fmt(reference['Mlx_Nmm']/1e6)+' kN·m; Nl tabelado = '+fmt(reference['Nl_N']/1000)+' kN; Tabela 1, p'+str(reference['printed_page'])+'/PDF'+str(reference['PDF_page'])+'. Linha nominal: '+display(reference['dimensions_mm'])+'.')
 doc.add_paragraph(reference['title']+'; '+reference['url'])
 doc.add_paragraph('Críticos locais elásticos, não resistências. Nl apenas documental; não há verificação axial implementada. Mlx é do eixo x de simetria da seção U; não transposto ao eixo fraco.')
 doc.add_paragraph('Fonte: E=200000 MPa, apoio simples e cantos retos. G e ν da fonte não explicitados. G77000 MPa é detector de alteração do app. A equivalência exata da linha nominal/propriedades do catálogo com a discretização INSTAB não foi demonstrada; conversão da fonte para linha média permanece pendente.')
 doc.add_paragraph('Uso atual: '+use_label(reference)+'. Novas seleções adotam Pierin; entradas legadas/manuais preservam valor e origem. Sem escala, interpolação ou fallback automático. Fonte informada: '+reference.get('source_input_origin',''))
 if reference.get('reason'):doc.add_paragraph(reference['reason'])
 for reason in reference.get('compatibility_reasons',[]):doc.add_paragraph(reason)
 doc.add_paragraph('Identidade do PDF fonte SHA256: '+reference['source_pdf_sha256'])

def inclination_inputs(doc,data,reference=None):
 weak_reference_report(doc,reference)
 from .weak_u_assumption import evidence as u_evidence
 inference=u_evidence(data)
 if inference:
  doc.add_heading('Opção exploratória — hipótese U/alma inferida',2)
  doc.add_paragraph(inference['warning'])
  doc.add_paragraph('Registro explícito e limites: '+display(inference))
 wall=is_girt(data)
 if wall:wall_input_report(doc,data)
 else:doc.add_paragraph('Eixos locais da seção: X horizontal (maior inércia), Y vertical (menor inércia). Flecha paralela à cobertura fora do escopo desta emissão: não avaliada e não incluída na lista de verificações.')
 ic=data.get('inclination',{'value':0.,'unit':'degrees','spacing_basis':'roof','permanent_basis':'roof','live_basis':'horizontal','wind_basis':'roof'})
 if ic and not wall:
  doc.add_paragraph('Inclinação e bases declaradas: '+display(ic))
  doc.add_paragraph('Bases roof = plano da cobertura; horizontal = projeção horizontal. Vento normal à cobertura; gravidade decomposta no modo por área. No modo direto, componentes já locais não são giradas novamente. Alma perpendicular à cobertura; telha sem crédito de travamento.')
 if data.get('weak_catalog') is not None:
  doc.add_paragraph('Automação de propriedades do catálogo / linha média explícita: '+display(data['weak_catalog']))
  doc.add_paragraph('Nex e Nez calculados dos comprimentos e propriedades; Cs por sentido local; Cm=1. Consistência de propriedades editadas não é verificação resistente; diferenças entre linha média idealizada e catálogo com cantos são informativas, sem limite normativo de3%. A conversão automática am/bm/cm segue Figura E.1 e Ex08 CBCA.')
 if data.get('weak_axis'):
  doc.add_heading('Dados rastreados — eixo fraco / Anexo E',2)
  doc.add_paragraph('W é da primeira fibra a escoar; Wc da fibra comprimida. Nex/Nez em N, r0/j em mm, W/Wc em mm³, Ml/Mdist em Nmm. Cs/Cm conforme Anexo E. Dados independentes por sentido; nenhuma transposição automática bilateral da tabela.')
  for sign,item in data['weak_axis'].items():
   doc.add_paragraph(('My positivo' if sign=='positive' else 'My negativo')+': '+display(item))
 doc.add_paragraph('Ly superior/inferior refere-se às mesas na seção de referência (na travessa girada: direita/esquerda). Comprimentos para FLT não criam apoio vertical nem torsional por simples existência de tirantes.' if wall else 'Ly superior/inferior: comprimento lateral associado à menor inércia para FLT da flexão forte. Lz: comprimento torsional; não representa a maior inércia nem cria apoio no diagrama de cargas.')

def word(result):
 from .roof_top_nbr_ui import _word_presenters
 roof_nbr=_word_presenters(result)
 doc=Document()
 for name in ['Normal','Title','Heading 1','Heading 2']:
  style=doc.styles[name];style.font.name='Arial';style.font.color.rgb=RGBColor(0,0,0)
 for style in doc.styles:
  for border in style.element.xpath('.//w:pBdr'):
   border.getparent().remove(border)
 doc.styles['Normal'].font.size=Pt(10)
 doc.styles['Normal'].paragraph_format.space_after=Pt(5)
 doc.sections[0].top_margin=Inches(.7);doc.sections[0].bottom_margin=Inches(.7)
 doc.add_heading('Estudo de travessa lateral' if is_girt(result['input_data']) else 'Estudo de terça',0)
 doc.add_paragraph(DISPLAY_NOTE)
 doc.add_paragraph(TECHNICAL_NOTE)
 doc.add_paragraph('Emissão parcial — NBR 14762:2010 — sem crédito de travamento da telha')
 doc.add_paragraph('NÃO É APROVAÇÃO GLOBAL DO ELEMENTO OU DAS LIGAÇÕES. Confira os dados, a aplicação física, as verificações não avaliadas e o domínio de cada resultado.')
 if result['synthetic']:doc.add_paragraph('EXEMPLO DIDÁTICO COM DADOS SINTÉTICOS. NÃO UTILIZAR COMO PROJETO.')
 domain_report(doc,result)
 homogeneous_reference_report(doc,result)
 ue_reference_report(doc,result)
 ue_family_reference_report(doc,result)
 from .ue_catalog_ui import report as ue_catalog_report
 ue_catalog_report(doc,result)
 deflection_scope_report(doc,result)
 from .support_scope import report as report_support_scope
 report_support_scope(doc,result)
 gross_component_report(doc,result);aa_component_report(doc,result)
 from .study_completion import _report_global
 _report_global(doc,result,roof_nbr_presentation=roof_nbr)
 from .point_contact import report as report_point_contact
 report_point_contact(doc,result)
 from .torsion_study_ui import report as torsion_report
 torsion_report(doc,result)
 from .aisi_torsion_ui import report as aisi_torsion_report
 aisi_torsion_report(doc,result)
 from .isolated_en_ui import report as isolated_EN_report
 isolated_EN_report(doc,result)
 doc.add_paragraph('Projeto: '+result['project']);doc.add_paragraph('Versão: '+result['version']);doc.add_paragraph('Gerado em UTC: '+datetime.now(timezone.utc).isoformat())
 doc.add_heading('Premissas e limites',1)
 for text in ['Um vão isostático. Flexão forte e rota restrita de flexão fraca/Anexo E; interação biaxial §9.9 para N=0 quando há resistências rastreadas por eixo e sentido. Para posição fixa de P, o máximo concomitante é calculado ao longo do vão. Sem dimensionamento de torção primária, axial, continuidade ou balanços nesta emissão.', 'Ações ELU e ELS já combinadas, informadas separadamente. Não há geração automática de todas as combinações.', 'Ly e Lz são comprimentos efetivos informados; coordenada de tirante não comprova vínculo torsional.', 'A flecha é componente Euler–Bernoulli com Ief por seção. Limite de flecha é informado com origem; não equivale a aprovação do sistema.', 'Propriedades e críticos fornecidos não são certificados pelo aplicativo. A convenção geométrica das propriedades do catálogo precisa ser conferida para o caso.', 'Ligações e apoios não são dimensionados ou aprovados pelo aplicativo.']:
  if aa_claims_result(result) and text.startswith('A flecha é componente'):
   axis='horizontal normal ao fechamento' if is_girt(result['input_data']) else 'normal à cobertura'
   text='Método AA: teto conservador da componente '+axis+' da flexão biaxial, admitindo redução apenas da alma e exigindo demonstração de mesas e lábios integrais. Teto não é flecha exata. Teto dentro do limite comprova somente suficiência desta componente no modelo delimitado; teto acima do limite ou estado sem demonstração permanece inconclusivo. Não é ELS físico completo nem aprovação global.'
  elif 'gross_biaxial_component_evidence' in result and text.startswith('A flecha é componente'):
   text='A componente normal da flexão biaxial utiliza o tensor bruto próprio somente nos estados demonstrados pelo crivo suficiente. O relatório distingue esses estados dos inconclusivos; não é ELS físico completo.'
  if is_girt(result['input_data']) and text.startswith('A flecha é componente'):
   text=('Flecha horizontal: componente uniaxial isolada com Ief por seção. Flecha vertical fora do escopo selecionado. Critério declarado não aprova o sistema.' if result.get('deflection_scope_evidence') else 'Flecha horizontal: componente Euler–Bernoulli com Ief por seção. Vertical: diagnóstico separado com Iy bruto, sem conclusão ELS. Critérios declarados não aprovam o sistema.')
  doc.add_paragraph(text,style='List Bullet')
 for warning in result.get('coverage_warnings',[])+result.get('critical_warnings',[]):doc.add_paragraph(warning)
 if result.get('numerical_warnings'):doc.add_paragraph('Aviso numérico do integrador escalar anterior preservado como diagnóstico. A componente tensorial nova tem estado separado.' if ('gross_biaxial_component_evidence' in result or 'aa_web_component_evidence' in result) else 'Aviso numérico na integração da flecha: critério ELS não concluído.')
 inclination_inputs(doc,result['input_data'],None if (result.get('homogeneous_reference_evidence') or result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence')) else result.get('weak_critical_reference'))
 if not (result.get('homogeneous_reference_evidence') or result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence')):strong_reference_report(doc,result.get('strong_critical_reference'))
 if result.get('inclination_evidence'):
  doc.add_heading('Solicitações locais simultâneas',1);inclination_report(doc,historical_inclination(result,roof_nbr.inclination(result['inclination_evidence'])))
 if not is_girt_result(result):wall_vertical_report(doc,result)
 doc.add_heading('Resultados por verificação',1)
 tab=doc.add_table(rows=1, cols=4);tab.style='Table Grid'
 trPr=tab.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');trPr.append(repeat)
 for cell in tab.rows[0].cells:
  shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'E8EEF3');cell._tc.get_or_add_tcPr().append(shd)
 for c,s in zip(tab.rows[0].cells,['Verificação','Situação','Índice','Referência']):c.text=s
 from .application import _rows
 for r in display_records(_rows(result,roof_formatter=roof_nbr.rows)):
  row=tab.add_row();row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'));cells=row.cells
  for c,s in zip(cells,[r['Verificação'],r['Situação'],'—' if r['Índice'] is None else f"{fmt(r['Índice'])}",r['Referência']]):c.text=display(s)
  doc.add_paragraph(r['Verificação']+' | Valor: '+r['Demanda / valor']+' | Resistência/limite: '+r['Resistência / limite'])
  if r['Observação']:doc.add_paragraph(r['Verificação']+': '+r['Observação'])
 report_mv_trace(doc,result,'DIRECT_ELU',result['input_data'].get('P_uls'),expected_a_mm=result['input_data'].get('x_uls'))
 report_els_trace(doc,result,result,'DIRECT_ELS',reference='§9.8.5; componente no modelo delimitado')
 doc.add_heading('Parâmetros das verificações',1)
 local=result['NBR_branches']['local']
 if local.get('MRd_Nmm'):
  doc.add_paragraph('Flexão local MSE: MRd = Wef × fy / 1,1. Wef obtido do crítico local Ml informado para a mesma seção.')
 for i,flt in enumerate(result['FLT_segments'],1):
  if flt.get('FLT'):
   if flt.get('compressed_flange'):doc.add_paragraph(f"Mesa comprimida governante: {flt['compressed_flange']}; comprimento lateral efetivo usado: {fmt(flt.get('Ly_used_mm'))} mm; Lz torsional: {fmt(flt.get('Lz_used_mm'))} mm.")
   f=flt['FLT'];doc.add_paragraph(f"FLT trecho {i}: Me = {fmt(flt['Me_Nmm']/1e6)} kN·m; Cb = {fmt(flt['Cb_used'])}; λ0 = {fmt(f['lambda0'])}; χFLT = {fmt(f['chi_flt'])}; λp na tensão reduzida = {fmt(f['lambda_p_reduced_stress'])}; Wef = {fmt(f['Wceff_mm3'])} mm³; γ = {fmt(f['gamma'])}.")
 shear=result['section_checks'].get('shear',{})
 if shear.get('VRd_N'):doc.add_paragraph(f"Cortante: h plano = {fmt(shear['flat_web_mm'])} mm; h/t = {fmt(shear['h_over_t'])}; kv = {fmt(shear['kv'])}; γ = {fmt(shear['gamma'])}.")
 doc.add_heading('Dados e origem',1)
 fields=result['input_snapshot']['selected_section']['fields']
 sources=list(dict.fromkeys(v['origin'] for v in fields.values()))
 for i,source in enumerate(sources,1):doc.add_paragraph(f'Origem {i}: {source}')
 prop=doc.add_table(rows=1,cols=3);prop.style='Table Grid'
 prop.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 for c,t in zip(prop.rows[0].cells,['Campo e unidade','Valor','Origem']):c.text=t
 for k,v in fields.items():
  row=prop.add_row();row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'));cells=row.cells
  for c,t in zip(cells,[k,technical_value(v['value']) if v['value'] is not None else 'Não informado',str(sources.index(v['origin'])+1)]):c.text=t
 d=result['input_data']
 pp=result.get('direct_self_weight_evidence')
 if pp:
  doc.add_heading('Peso próprio no modo direto',2)
  doc.add_paragraph(pp['scope'])
  doc.add_paragraph('Massa linear adotada [kg/m]: '+technical_value(pp['mass_kg_m']))
  for state,trace in pp['states'].items():
   doc.add_paragraph(state.upper()+': fator PP='+technical_value(trace['factor'])+'; q externo='+display(trace['external_q_N_mm'])+'; PP acrescentado='+display(trace['profile_PP_q_N_mm'])+'; q total calculado='+display(trace['total_q_N_mm'])+' N/mm.')
 labels={'L_mm':'Vão [mm]','q_uls':'q ELU [N/mm]','P_uls':'P ELU [N]','x_uls':'Posição P ELU [mm]','q_sls':'q ELS [N/mm]','P_sls':'P ELS [N]','x_sls':'Posição P ELS [mm]','actions_origin':'Origem das combinações','Ml_Nmm':'Ml [N·mm]','Mdist_Nmm':'Mdist [N·mm]','critical_origin':'Origem dos críticos','ELS_limit_mm':'Limite de flecha [mm]','ELS_origin':'Origem do limite de flecha'}
 for k,label in labels.items():
  if is_girt(d) and k in ('ELS_limit_mm','ELS_origin'):continue
  value=d.get(k)
  doc.add_paragraph(f'{label}: '+('Não informado' if value is None else (f'{fmt(value)}' if isinstance(value,(int,float)) else display(value))))
 for i,seg in enumerate(d['segments'],1):
  cb={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}.get(seg.get('Cb_mode'),seg.get('Cb_mode'))
  if 'Ly_top_effective_mm' in seg:
   lateral=f"mesa superior {fmt(seg.get('Ly_top_effective_mm'))} mm; mesa inferior {fmt(seg.get('Ly_bottom_effective_mm'))} mm"
  else:lateral=f"mesa comprimida (entrada anterior) {fmt(seg.get('Ly_effective_mm'))} mm"
  doc.add_paragraph(f"Trecho {i}: {fmt(seg.get('start_mm'))} a {fmt(seg.get('end_mm'))} mm; comprimentos efetivos: {lateral}; Lz torsional {fmt(seg.get('Lz_effective_mm'))} mm; {cb}. Origem: {seg.get('restraint_provenance')}")
 report_fingerprint(doc,result['input_fingerprint'])
 out=BytesIO();doc.save(out);return out.getvalue()


def batch_common_inputs(doc,result):
 """Serialize frozen calculation inputs, never recalculate or certify them.

 Old retained results may lack this additive snapshot. Their declared numeric
 inputs remain visible, explicitly distinguished from effective calculation data.
 """
 d=result['input_data'];snapshot=result.get('common_input_snapshot')
 doc.add_heading('Propriedades e críticos — dados numéricos adotados',2)
 if snapshot is not None:
  section=snapshot['selected_section'];fields=section['fields']
  if result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence'):
   own_record=result.get('ue_family_reference_evidence') or result['ue_reference_evidence']
   doc.add_paragraph('Snapshot comum às combinações: referência própria '+own_record['reference_id']+'; família '+section['family']+'. Correspondência nominal documental: '+section.get('nominal_documentary_catalog',{}).get('entry_id',section['entry_id'])+'. Os valores consumidos e suas origens são próprios; não são certificação do perfil físico.')
  else:
   doc.add_paragraph('Snapshot comum às combinações: seção '+section['entry_id']+
                     '; família '+section['family']+'. Valores de entrada e origem preservados no cálculo; não são certificação do perfil.')
 else:
  fields={key:{'value':value,'origin':d.get('property_origin','Origem não informada')}
          for key,value in d['properties'].items()}
  doc.add_paragraph('Resultado anterior sem snapshot comum de cálculo: abaixo estão os valores declarados nas entradas, não uma reconstrução dos valores efetivamente utilizados. Nenhum recálculo foi realizado para exportar.')
 sources=list(dict.fromkeys(v['origin'] for v in fields.values()))
 table=doc.add_table(rows=1,cols=3);table.style='Table Grid'
 table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 for cell,label in zip(table.rows[0].cells,['Campo e unidade','Valor','Origem']):cell.text=label
 dimensions={'h':'h [mm]','bf':'bf [mm]','lip':'D [mm]','t':'t [mm]'}
 for key,item in fields.items():
  row=table.add_row();row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
  value='Não informado' if item['value'] is None else technical_value(item['value'])
  for cell,text in zip(row.cells,[dimensions.get(key,key),value,str(sources.index(item['origin'])+1)]):cell.text=text
 for i,source in enumerate(sources,1):doc.add_paragraph(f'Origem das propriedades {i}: {source}')
 doc.add_paragraph('Os valores exibidos seguem o arredondamento da MC; o JSON mantém o snapshot com precisão completa. Valor declarado de crítico não é necessariamente utilizado: bloqueios e ausência de dados permanecem explícitos abaixo.')
 for label,key in [('Ml','Ml_Nmm'),('Mdist','Mdist_Nmm')]:
  value=d.get(key)
  doc.add_paragraph(label+' declarado [N·mm]: '+('Não informado' if value is None else display(value))+'. Origem declarada: '+d.get('critical_origin',''))
  if snapshot is not None:
   effective=snapshot[label];used=effective.get('value')
   doc.add_paragraph(label+' disponibilizado ao cálculo [N·mm]: '+('Não informado / não utilizado' if used is None else display(used))+'. Origem efetiva: '+effective.get('origin',''))
   if effective.get('reason'):doc.add_paragraph('Motivo: '+effective['reason'])
   info=snapshot['strong_critical_qualification']['fields'].get(label,{})
   doc.add_paragraph('Rastreabilidade '+label+': '+display(info)+'. Disponibilidade do dado não implica que todos os ramos o utilizem; conferir resultados/dispensas por combinação.')
  else:doc.add_paragraph(label+': valor efetivamente disponibilizado não registrado neste resultado anterior; conferir as evidências/avisos por combinação.')


def batch_word(result):
 """One report for selected families, retaining all per-case checks."""
 from .roof_top_nbr_ui import _word_presenters
 roof_nbr=_word_presenters(result)
 els_trace_readable=component_record_is_readable(result)
 doc=Document();doc.styles['Normal'].font.name='Arial';doc.styles['Normal'].font.size=Pt(10)
 for name in ['Normal','Title','Heading 1','Heading 2']:
  doc.styles[name].font.color.rgb=RGBColor(0,0,0)
 for style in doc.styles:
  for border in style.element.xpath('.//w:pBdr'):border.getparent().remove(border)
 doc.styles['Normal'].paragraph_format.space_after=Pt(5)
 doc.add_heading('Travessas laterais por combinações' if is_girt(result['input_data']) else 'Terças por combinações',0)
 doc.add_paragraph(DISPLAY_NOTE)
 doc.add_paragraph(TECHNICAL_NOTE)
 doc.add_paragraph('NBR 14762:2010 · estudo parcial · sem travamento da telha. NÃO É APROVAÇÃO GLOBAL. Ligações e apoios fora do escopo.')
 domain_report(doc,result)
 homogeneous_reference_report(doc,result)
 ue_reference_report(doc,result)
 ue_family_reference_report(doc,result)
 from .ue_catalog_ui import report as ue_catalog_report
 ue_catalog_report(doc,result)
 deflection_scope_report(doc,result)
 from .support_scope import report as report_support_scope
 report_support_scope(doc,result)
 gross_component_report(doc,result);aa_component_report(doc,result)
 from .study_completion import _report_global
 _report_global(doc,result,roof_nbr_presentation=roof_nbr)
 from .point_contact import report as report_point_contact
 report_point_contact(doc,result)
 from .torsion_study_ui import report as torsion_report
 torsion_report(doc,result)
 from .aisi_torsion_ui import report as aisi_torsion_report
 aisi_torsion_report(doc,result)
 from .isolated_en_ui import report as isolated_EN_report
 isolated_EN_report(doc,result)
 doc.add_paragraph('Projeto: '+result['project']+' | versão: '+result['version'])
 if result['synthetic']:doc.add_paragraph('EXEMPLO DIDÁTICO — DADOS SINTÉTICOS.')
 doc.add_heading('Entradas e premissas',1)
 d=result['input_data'];from .catalogs import catalog_labels
 doc.add_paragraph('Correspondência nominal (propriedades próprias): '+catalog_labels()[d['catalog_index']]+'; aço declarado: '+d['steel_name'] if (result.get('homogeneous_reference_evidence') or result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence')) else 'Perfil: '+catalog_labels()[d['catalog_index']]+'; aço: '+d['steel_name'])
 doc.add_paragraph('Origem das propriedades: '+d['property_origin'])
 doc.add_paragraph('Críticos: '+d['critical_origin'])
 doc.add_paragraph('Vão [mm]: '+display(d['L_mm']))
 batch_common_inputs(doc,result)
 inclination_inputs(doc,d,None if (result.get('homogeneous_reference_evidence') or result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence')) else result.get('weak_critical_reference'))
 if not (result.get('homogeneous_reference_evidence') or result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence')):strong_reference_report(doc,result.get('strong_critical_reference'))
 labels={'mass_kg_m':'Massa linear [kg/m]','spacing_m':'Distância entre terças [m]','permanent_kgf_m2':'Permanente [kgf/m²]','live_kgf_m2':'Sobrecarga [kgf/m²]','wind_up_kgf_m2':'Vento para cima [kgf/m²]','wind_down_kgf_m2':'Vento para baixo [kgf/m²]'}
 if is_girt(d):labels.update(spacing_m='Distância tributária entre travessas no fechamento [m]',live_kgf_m2='SC de cobertura armazenada e INATIVA [kgf/m²]',wind_up_kgf_m2='Vento normal negativo / sucção [kgf/m²]',wind_down_kgf_m2='Vento normal positivo / pressão [kgf/m²]')
 for k,v in result['load_bundle']['inputs'].items():doc.add_paragraph(f'{labels.get(k,k)}: {display(v)}')
 doc.add_paragraph('Travessa: área no plano da fachada × distância tributária. PP e CP verticais no eixo fraco; vento normal no forte. Usam-se apenas linhas da matriz do usuário sem SC (12 ELU, 3 ELS raras, 3 frequentes e 1 quase permanente antes do filtro de famílias). Não se adiciona P automática de cobertura; não é gerador normativo universal.' if is_girt(d) else 'Área → linha pela distância entre terças; PP uma única vez pela massa linear. Vento para cima negativo. As 48 combinações de origem são as fornecidas por Lucas em 31/10/2026, filtradas pelos tipos selecionados. Adicionam-se quatro ELU G+1,5P e uma ELS rara G+P, conforme seleção, com P=1 kN isolada de outras variáveis. Cada combinação com P é calculada em duas posições: centro e limite junto ao apoio (x→0+). Não há varredura intermediária.')
 doc.add_paragraph('Tipos selecionados: '+', '.join(d['selected_types']))
 if not is_girt(d):doc.add_paragraph(f"Limites de flecha: L/{fmt(d['ELS_down_denominator'])} descendente; L/{fmt(d['ELS_up_denominator'])} ascendente. Critérios informados, aplicados a cada combinação ELS.")
 if is_girt_result(result) and aa_claims_result(result):doc.add_paragraph('Método AA: teto conservador da componente horizontal normal ao fechamento da flexão biaxial, admitindo redução apenas da alma e exigindo demonstração de mesas e lábios integrais. Teto não é flecha exata. Teto dentro do limite comprova somente suficiência desta componente no modelo delimitado; teto acima do limite ou estado sem demonstração permanece inconclusivo. Vetores horizontal/vertical concomitantes preservados; limite wall_els aplicado somente à horizontal. Sem critério vertical novo, crédito de tirantes, ELS físico completo ou aprovação global.')
 elif is_girt_result(result):doc.add_paragraph('Flecha horizontal: componente flexional biaxial com tensor bruto próprio somente quando o crivo suficiente demonstra seção integral. Vetores horizontal/vertical concomitantes preservados; limite wall_els aplicado somente à horizontal. Sem critério vertical novo, crédito de tirantes, ELS físico completo ou aprovação global.')
 else:doc.add_paragraph(('Flecha horizontal: componente uniaxial isolada com Ief; vertical fora do escopo selecionado. Ações e resistência biaxial permanecem presentes. Sem aprovação ELS completa.' if result.get('deflection_scope_evidence') else 'O resultado contém avaliações separadas por combinação; esta exportação não recalcula resultados. A interação biaxial §9.9 (N=0) requer resistências rastreadas por eixo e sentido. Nesta Travessa por área não se adiciona P de cobertura. A flecha horizontal usa a rota de Ief; a vertical é diagnóstico bruto separado, sem conclusão ELS. Não há dimensionamento de torção primária, axial, continuidade ou balanços; o estudo elástico de tirantes não modifica a resistência do vão livre.') if is_girt(d) else 'O resultado contém avaliações separadas por combinação; esta exportação não recalcula resultados. Não se somam índices resistentes ou flechas calculadas com diferentes inércias efetivas. A interação biaxial §9.9 (N=0) usa resistências rastreadas por eixo e sentido. O envelope ao longo do vão é calculado para uma posição fixa de P; nas combinações com P, os resultados cobrem as duas posições prescritas, não o máximo contínuo da interação ou FLT. Sem dimensionamento de torção primária, axial, continuidade ou balanços.')
 for s in d['segments']:
  cb={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}.get(s.get('Cb_mode'),s.get('Cb_mode'))
  doc.add_paragraph(f"Trecho {fmt(s['start_mm'])} a {fmt(s['end_mm'])} mm. Ly superior: {fmt(s.get('Ly_top_effective_mm',s.get('Ly_effective_mm')))} mm; Ly inferior: {fmt(s.get('Ly_bottom_effective_mm',s.get('Ly_effective_mm')))} mm; Lz: {fmt(s.get('Lz_effective_mm'))} mm. {cb}. {s.get('restraint_provenance','')}")
 doc.add_heading('Casos característicos — componentes no fechamento' if is_girt(d) else 'Casos característicos — componentes normais à cobertura',1)
 if is_girt(d):
  for k,v in result['load_bundle']['case_vectors_N_mm'].items():doc.add_paragraph(f"{k}: horizontal normal={fmt(v['normal'])} kN/m; vertical={fmt(v['parallel'])} kN/m"+(' (inativa)' if k=='SC' else ''))
 else:
  for k,v in result['load_bundle']['case_q_N_mm'].items():doc.add_paragraph(f'{k}: {fmt(v)} kN/m')
 doc.add_heading('Resumo dos casos governantes',1)
 t=doc.add_table(rows=1,cols=4);t.style='Table Grid'
 t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 for c,v in zip(t.rows[0].cells,['Critério','Combinação','Índice','Situação']):c.text=v
 for r in display_records(historical_rows(result,roof_nbr.rows(gross_component_rows(result,result['summary'])))):
  summary_row=t.add_row()
  summary_row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
  for c,v in zip(summary_row.cells,[r['Verificação'],r['Combinação'],'—' if r['Índice'] is None else f"{fmt(r['Índice'])}",r['Situação']]):c.text=display(v)
 doc.add_heading('Todas as combinações selecionadas',1)
 for item in result['cases']:
  c=item['combination'];doc.add_heading(f"{c['id']} — {c['type']}",2)
  doc.add_paragraph(f"{measurement_text(c['expression'])} → q normal={fmt(c['q_kN_m'])} kN/m. P normal={fmt(c.get('P_N',0)/1000)} kN. Forças/efeitos superpostos antes das verificações.")
  if item.get('evidence',{}).get('inclination'):inclination_report(doc,historical_inclination(result,roof_nbr.inclination(item['evidence']['inclination'],c['id'])))
  if not is_girt_result(result):wall_vertical_report(doc,item.get('evidence',{}))
  for row in display_records(historical_rows(result,roof_nbr.rows(gross_component_rows(result,item['rows']),c['id']))):
   index='—' if row['Índice'] is None else f"{fmt(row['Índice'])}"
   doc.add_paragraph(f"{row['Verificação']}: {row['Situação']}; índice {index}; {row['Demanda / valor']}; limite/resistência {row['Resistência / limite']}. {row['Referência']}. {row['Observação']}")
  from .point_limit import saved_exclusion
  point=item.get('evidence',{}).get('NBR_branches',{}).get('point',{})
  if saved_exclusion(point,c,d.get('L_mm'),item.get('evidence',{}).get('inclination',{}).get('P_vector')):
   doc.add_paragraph('Escopo de P_APOIO: '+point['reason'])
  if c['limit_state']=='ELU':report_mv_trace(doc,item.get('evidence',{}),c['id'],c.get('P_vector',{}).get('normal',c.get('P_N')),point_position=c.get('point_position'),expected_a_mm=c.get('x_mm'))
  elif c['limit_state']=='ELS':report_els_trace(doc,result,item.get('evidence',{}),c['id'],reference='§9.8.5; componente no modelo delimitado',readable=els_trace_readable)
  for warning in item['warnings']:doc.add_paragraph('Aviso: '+warning)
 report_fingerprint(doc,result['input_fingerprint'])
 out=BytesIO();doc.save(out);return out.getvalue()
