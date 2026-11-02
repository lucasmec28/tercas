from .presentation import fmt, display, display_records, measurement_text, DISPLAY_NOTE
from io import BytesIO
from datetime import datetime,timezone
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .application import rows

def inclination_report(doc,evidence):
 if not isinstance(evidence,dict):return
 if 'states' not in evidence:
  for label,item in evidence.items():
   if isinstance(item,dict):
    doc.add_heading(display(label)+' — esforços locais',2);inclination_report(doc,item)
  return
 angle=evidence.get('angle',{})
 doc.add_paragraph('Inclinação: '+fmt(angle['degrees'])+' graus; '+fmt(angle['percent'])+' %. Valores exibidos arredondados; cálculo usa precisão completa.')
 doc.add_paragraph(evidence.get('convention','Esforços simultâneos na mesma seção e combinação.'))
 doc.add_paragraph(evidence.get('resistance_status','Resistência biaxial não avaliada.'))
 if evidence.get('weak_axis_capacities'):
  doc.add_heading('Resistências do eixo fraco por sentido',3)
  for sign,cap in evidence['weak_axis_capacities'].items():
   doc.add_paragraph(('My positivo' if sign=='positive' else 'My negativo')+': '+display(cap))
  doc.add_paragraph('Interação concomitante §9.9, N=0: '+display(evidence.get('biaxial')))
  doc.add_paragraph('MxRd conservador adotado [Nmm]: '+display(evidence.get('strong_capacity_Nmm')))
 doc.add_paragraph('Cargas locais: q [N/mm]='+display(evidence.get('q_vector'))+'; P [N]='+display(evidence.get('P_vector'))+'.')
 for state in evidence.get('states',[]):
  doc.add_paragraph(state.get('position_limit','Posição fixa')+' — seção x='+display(state.get('x_mm'))+' mm; lado '+{'left':'esquerda','right':'direita'}.get(state.get('side'),'—')+' (momentos concomitantes, não soma de máximos independentes):')
  for axis,label in [('normal','Normal / eixo forte'),('parallel','Paralelo / eixo fraco')]:
   v=state.get(axis,{})
   doc.add_paragraph(label+': '+ '; '.join(title+'='+fmt(v[k]/scale) for k,title,scale in [('M_Nmm','M [kN·m]',1e6),('V_N','V [kN]',1000),('Rleft_N','Reação esquerda [kN]',1000),('Rright_N','Reação direita [kN]',1000)] if k in v))
 doc.add_paragraph('A tabela de seções ilustra solicitações locais. Quando disponível, o resultado §9.9 acima identifica o máximo concomitante para P fixa, calculado separadamente. No modo por área, P é avaliada nas duas posições prescritas, sem varredura intermediária; no modo direto, na posição informada. Não há conclusão biaxial sem resistência aplicável por eixo e sentido; os críticos fortes não são reutilizados no eixo fraco.')

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
 doc.add_paragraph('Eixos locais da seção: X horizontal (maior inércia), Y vertical (menor inércia). Flecha paralela à cobertura fora do escopo desta emissão: não avaliada e não incluída na lista de verificações.')
 ic=data.get('inclination',{'value':0.,'unit':'degrees','spacing_basis':'roof','permanent_basis':'roof','live_basis':'horizontal','wind_basis':'roof'})
 if ic:
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
 doc.add_paragraph('Ly superior/inferior: comprimento lateral associado à menor inércia para FLT da flexão forte. Lz: comprimento torsional; não representa a maior inércia nem cria apoio no diagrama de cargas.')

def word(result):
 doc=Document()
 for name in ['Normal','Title','Heading 1','Heading 2']:
  style=doc.styles[name];style.font.name='Arial';style.font.color.rgb=RGBColor(0,0,0)
 for style in doc.styles:
  for border in style.element.xpath('.//w:pBdr'):
   border.getparent().remove(border)
 doc.styles['Normal'].font.size=Pt(10)
 doc.styles['Normal'].paragraph_format.space_after=Pt(5)
 doc.sections[0].top_margin=Inches(.7);doc.sections[0].bottom_margin=Inches(.7)
 doc.add_heading('LRO Engenharia Estudo de terça',0)
 doc.add_paragraph(DISPLAY_NOTE)
 doc.add_paragraph('Emissão parcial — NBR 14762:2010 — sem crédito de travamento da telha')
 doc.add_paragraph('NÃO É APROVAÇÃO GLOBAL DO ELEMENTO OU DAS LIGAÇÕES. Confira os dados, a aplicação física, as verificações não avaliadas e o domínio de cada resultado.')
 if result['synthetic']:doc.add_paragraph('EXEMPLO DIDÁTICO COM DADOS SINTÉTICOS. NÃO UTILIZAR COMO PROJETO.')
 doc.add_paragraph('Projeto: '+result['project']);doc.add_paragraph('Versão: '+result['version']);doc.add_paragraph('Gerado em UTC: '+datetime.now(timezone.utc).isoformat())
 doc.add_heading('Premissas e limites',1)
 for text in ['Um vão isostático. Flexão forte e rota restrita de flexão fraca/Anexo E; interação biaxial §9.9 para N=0 quando há resistências rastreadas por eixo e sentido. Para posição fixa de P, o máximo concomitante é calculado ao longo do vão. Sem dimensionamento de torção primária, axial, continuidade ou balanços nesta emissão.', 'Ações ELU e ELS já combinadas, informadas separadamente. Não há geração automática de todas as combinações.', 'Ly e Lz são comprimentos efetivos informados; coordenada de tirante não comprova vínculo torsional.', 'A flecha é componente Euler–Bernoulli com Ief por seção. Limite de flecha é informado com origem; não equivale a aprovação do sistema.', 'Propriedades e críticos fornecidos não são certificados pelo aplicativo. A convenção geométrica das propriedades do catálogo precisa ser conferida para o caso.', 'Ligações e apoios não são dimensionados ou aprovados pelo aplicativo.']:
  doc.add_paragraph(text,style='List Bullet')
 for warning in result.get('coverage_warnings',[])+result.get('critical_warnings',[]):doc.add_paragraph(warning)
 if result.get('numerical_warnings'):doc.add_paragraph('Aviso numérico na integração da flecha: critério ELS não concluído.')
 inclination_inputs(doc,result['input_data'],result.get('weak_critical_reference'))
 strong_reference_report(doc,result.get('strong_critical_reference'))
 if result.get('inclination_evidence'):
  doc.add_heading('Solicitações locais simultâneas',1);inclination_report(doc,result['inclination_evidence'])
 doc.add_heading('Resultados por verificação',1)
 tab=doc.add_table(rows=1, cols=4);tab.style='Table Grid'
 trPr=tab.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');trPr.append(repeat)
 for cell in tab.rows[0].cells:
  shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'E8EEF3');cell._tc.get_or_add_tcPr().append(shd)
 for c,s in zip(tab.rows[0].cells,['Verificação','Situação','Índice','Referência']):c.text=s
 for r in display_records(rows(result)):
  cells=tab.add_row().cells
  for c,s in zip(cells,[r['Verificação'],r['Situação'],'—' if r['Índice'] is None else f"{fmt(r['Índice'])}",r['Referência']]):c.text=display(s)
  doc.add_paragraph(r['Verificação']+' | Valor: '+r['Demanda / valor']+' | Resistência/limite: '+r['Resistência / limite'])
  if r['Observação']:doc.add_paragraph(r['Verificação']+': '+r['Observação'])
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
 for c,t in zip(prop.rows[0].cells,['Campo e unidade','Valor','Origem']):c.text=t
 for k,v in fields.items():
  cells=prop.add_row().cells
  for c,t in zip(cells,[k,display(v['value']) if v['value'] is not None else 'Não informado',str(sources.index(v['origin'])+1)]):c.text=t
 d=result['input_data']
 labels={'L_mm':'Vão [mm]','q_uls':'q ELU [N/mm]','P_uls':'P ELU [N]','x_uls':'Posição P ELU [mm]','q_sls':'q ELS [N/mm]','P_sls':'P ELS [N]','x_sls':'Posição P ELS [mm]','actions_origin':'Origem das combinações','Ml_Nmm':'Ml [N·mm]','Mdist_Nmm':'Mdist [N·mm]','critical_origin':'Origem dos críticos','ELS_limit_mm':'Limite de flecha [mm]','ELS_origin':'Origem do limite de flecha'}
 for k,label in labels.items():
  value=d.get(k)
  doc.add_paragraph(f'{label}: '+('Não informado' if value is None else (f'{fmt(value)}' if isinstance(value,(int,float)) else display(value))))
 for i,seg in enumerate(d['segments'],1):
  cb={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}.get(seg.get('Cb_mode'),seg.get('Cb_mode'))
  if 'Ly_top_effective_mm' in seg:
   lateral=f"mesa superior {fmt(seg.get('Ly_top_effective_mm'))} mm; mesa inferior {fmt(seg.get('Ly_bottom_effective_mm'))} mm"
  else:lateral=f"mesa comprimida (entrada anterior) {fmt(seg.get('Ly_effective_mm'))} mm"
  doc.add_paragraph(f"Trecho {i}: {fmt(seg.get('start_mm'))} a {fmt(seg.get('end_mm'))} mm; comprimentos efetivos: {lateral}; Lz torsional {fmt(seg.get('Lz_effective_mm'))} mm; {cb}. Origem: {seg.get('restraint_provenance')}")
 doc.add_paragraph('Identificação das entradas: '+result['input_fingerprint'])
 out=BytesIO();doc.save(out);return out.getvalue()


def batch_word(result):
 """One report for selected families, retaining all per-case checks."""
 doc=Document();doc.styles['Normal'].font.name='Arial';doc.styles['Normal'].font.size=Pt(10)
 for name in ['Normal','Title','Heading 1','Heading 2']:
  doc.styles[name].font.color.rgb=RGBColor(0,0,0)
 for style in doc.styles:
  for border in style.element.xpath('.//w:pBdr'):border.getparent().remove(border)
 doc.styles['Normal'].paragraph_format.space_after=Pt(5)
 doc.add_heading('LRO Engenharia Terças por combinações',0)
 doc.add_paragraph(DISPLAY_NOTE)
 doc.add_paragraph('NBR 14762:2010 · estudo parcial · sem travamento da telha. NÃO É APROVAÇÃO GLOBAL. Ligações e apoios fora do escopo.')
 doc.add_paragraph('Projeto: '+result['project']+' | versão: '+result['version'])
 if result['synthetic']:doc.add_paragraph('EXEMPLO DIDÁTICO — DADOS SINTÉTICOS.')
 doc.add_heading('Entradas e premissas',1)
 d=result['input_data'];from .catalogs import catalog_labels
 doc.add_paragraph('Perfil: '+catalog_labels()[d['catalog_index']]+'; aço: '+d['steel_name'])
 doc.add_paragraph('Origem das propriedades: '+d['property_origin'])
 doc.add_paragraph('Críticos: '+d['critical_origin'])
 doc.add_paragraph('Vão [mm]: '+display(d['L_mm']))
 inclination_inputs(doc,d,result.get('weak_critical_reference'))
 strong_reference_report(doc,result.get('strong_critical_reference'))
 labels={'mass_kg_m':'Massa linear [kg/m]','spacing_m':'Distância entre terças [m]','permanent_kgf_m2':'Permanente [kgf/m²]','live_kgf_m2':'Sobrecarga [kgf/m²]','wind_up_kgf_m2':'Vento para cima [kgf/m²]','wind_down_kgf_m2':'Vento para baixo [kgf/m²]'}
 for k,v in result['load_bundle']['inputs'].items():doc.add_paragraph(f'{labels.get(k,k)}: {display(v)}')
 doc.add_paragraph('Área → linha pela distância entre terças; PP uma única vez pela massa linear. Vento para cima negativo. As 48 combinações de origem são as fornecidas por Lucas em 31/10/2026, filtradas pelos tipos selecionados. Adicionam-se quatro ELU G+1,5P e uma ELS rara G+P, conforme seleção, com P=1 kN isolada de outras variáveis. Cada combinação com P é calculada em duas posições: centro e limite junto ao apoio (x→0+). Não há varredura intermediária.')
 doc.add_paragraph('Tipos selecionados: '+', '.join(d['selected_types']))
 doc.add_paragraph(f"Limites de flecha: L/{fmt(d['ELS_down_denominator'])} descendente; L/{fmt(d['ELS_up_denominator'])} ascendente. Critérios informados, aplicados a cada combinação ELS.")
 doc.add_paragraph('Cada combinação é recalculada. Não se somam índices resistentes ou flechas calculadas com diferentes inércias efetivas. A interação biaxial §9.9 (N=0) usa resistências rastreadas por eixo e sentido. O envelope ao longo do vão é calculado para uma posição fixa de P; nas combinações com P, os resultados cobrem as duas posições prescritas, não o máximo contínuo da interação ou FLT. Sem dimensionamento de torção primária, axial, continuidade ou balanços.')
 for s in d['segments']:
  cb={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}.get(s.get('Cb_mode'),s.get('Cb_mode'))
  doc.add_paragraph(f"Trecho {fmt(s['start_mm'])} a {fmt(s['end_mm'])} mm. Ly superior: {fmt(s.get('Ly_top_effective_mm',s.get('Ly_effective_mm')))} mm; Ly inferior: {fmt(s.get('Ly_bottom_effective_mm',s.get('Ly_effective_mm')))} mm; Lz: {fmt(s.get('Lz_effective_mm'))} mm. {cb}. {s.get('restraint_provenance','')}")
 doc.add_heading('Casos característicos — componentes normais à cobertura',1)
 for k,v in result['load_bundle']['case_q_N_mm'].items():doc.add_paragraph(f'{k}: {fmt(v)} kN/m')
 doc.add_heading('Resumo dos casos governantes',1)
 t=doc.add_table(rows=1,cols=4);t.style='Table Grid'
 t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 for c,v in zip(t.rows[0].cells,['Critério','Combinação','Índice','Situação']):c.text=v
 for r in display_records(result['summary']):
  for c,v in zip(t.add_row().cells,[r['Verificação'],r['Combinação'],'—' if r['Índice'] is None else f"{fmt(r['Índice'])}",r['Situação']]):c.text=display(v)
 doc.add_heading('Todas as combinações selecionadas',1)
 for item in result['cases']:
  c=item['combination'];doc.add_heading(f"{c['id']} — {c['type']}",2)
  doc.add_paragraph(f"{measurement_text(c['expression'])} → q normal={fmt(c['q_kN_m'])} kN/m. P normal={fmt(c.get('P_N',0)/1000)} kN. Forças/efeitos superpostos antes das verificações.")
  if item.get('evidence',{}).get('inclination'):inclination_report(doc,item['evidence']['inclination'])
  for row in display_records(item['rows']):
   index='—' if row['Índice'] is None else f"{fmt(row['Índice'])}"
   doc.add_paragraph(f"{row['Verificação']}: {row['Situação']}; índice {index}; {row['Demanda / valor']}; limite/resistência {row['Resistência / limite']}. {row['Referência']}. {row['Observação']}")
  for warning in item['warnings']:doc.add_paragraph('Aviso: '+warning)
 doc.add_paragraph('Identificação das entradas: '+result['input_fingerprint'])
 out=BytesIO();doc.save(out);return out.getvalue()
