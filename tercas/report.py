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
    doc.add_heading(str(label)+' — esforços locais',2);inclination_report(doc,item)
  return
 angle=evidence.get('angle',{})
 doc.add_paragraph('Inclinação: '+format(angle['degrees'],'.6f')+' graus; '+format(angle['percent'],'.6f')+' %. Valores exibidos arredondados; cálculo usa precisão completa.')
 doc.add_paragraph(evidence.get('convention','Esforços simultâneos na mesma seção e combinação.'))
 doc.add_paragraph(evidence.get('resistance_status','Resistência biaxial não avaliada.'))
 doc.add_paragraph('Cargas locais: q [N/mm]='+str(evidence.get('q_vector'))+'; P [N]='+str(evidence.get('P_vector'))+'.')
 for state in evidence.get('states',[]):
  doc.add_paragraph('Seção x='+str(state.get('x_mm'))+' mm; lado '+{'left':'esquerda','right':'direita'}.get(state.get('side'),'—')+' (momentos concomitantes, não soma de máximos independentes):')
  for axis,label in [('normal','Normal / eixo forte'),('parallel','Paralelo / eixo fraco')]:
   v=state.get(axis,{})
   doc.add_paragraph(label+': '+ '; '.join(title+'='+format(v[k]/scale,'.6g') for k,title,scale in [('M_Nmm','M [kN·m]',1e6),('V_N','V [kN]',1000),('Rleft_N','Reação esquerda [kN]',1000),('Rright_N','Reação direita [kN]',1000)] if k in v))
 doc.add_paragraph('Seções apresentadas não constituem envelope biaxial. Não há aprovação biaxial sem resistência aplicável por eixo e sentido; os críticos fortes não são reutilizados no eixo fraco.')

def inclination_inputs(doc,data):
 ic=data.get('inclination',{'value':0.,'unit':'degrees','spacing_basis':'roof','permanent_basis':'roof','live_basis':'horizontal','wind_basis':'roof'})
 if ic:
  doc.add_paragraph('Inclinação e bases declaradas: '+str(ic))
  doc.add_paragraph('Bases roof = plano da cobertura; horizontal = projeção horizontal. Vento normal à cobertura; gravidade decomposta no modo por área. No modo direto, componentes já locais não são giradas novamente. Alma perpendicular à cobertura; telha sem crédito de travamento.')
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
 doc.add_paragraph('Emissão parcial — NBR 14762:2010 — sem crédito de travamento da telha')
 doc.add_paragraph('NÃO É APROVAÇÃO GLOBAL DO ELEMENTO OU DAS LIGAÇÕES. Confira os dados, a aplicação física, as verificações não avaliadas e o domínio de cada resultado.')
 if result['synthetic']:doc.add_paragraph('EXEMPLO DIDÁTICO COM DADOS SINTÉTICOS. NÃO UTILIZAR COMO PROJETO.')
 doc.add_paragraph('Projeto: '+result['project']);doc.add_paragraph('Versão: '+result['version']);doc.add_paragraph('Gerado em UTC: '+datetime.now(timezone.utc).isoformat())
 doc.add_heading('Premissas e limites',1)
 for text in ['Um vão isostático, flexão no eixo de simetria forte. Sem dimensionamento de torção primária, flexão biaxial, axial, continuidade ou balanços nesta emissão.', 'Ações ELU e ELS já combinadas, informadas separadamente. Não há geração automática de todas as combinações.', 'Ly e Lz são comprimentos efetivos informados; coordenada de tirante não comprova vínculo torsional.', 'A flecha é componente Euler–Bernoulli com Ief por seção. Limite de flecha é informado com origem; não equivale a aprovação do sistema.', 'Propriedades e críticos fornecidos não são certificados pelo aplicativo. A convenção geométrica das propriedades do catálogo precisa ser conferida para o caso.', 'Ligações e apoios não são dimensionados ou aprovados pelo aplicativo. O usuário deve definir detalhes de introdução de força compatíveis com o modelo.']:
  doc.add_paragraph(text,style='List Bullet')
 for warning in result.get('coverage_warnings',[]):doc.add_paragraph(warning)
 if result.get('numerical_warnings'):doc.add_paragraph('Aviso numérico na integração da flecha: critério ELS não concluído.')
 inclination_inputs(doc,result['input_data'])
 if result.get('inclination_evidence'):
  doc.add_heading('Solicitações locais simultâneas',1);inclination_report(doc,result['inclination_evidence'])
 doc.add_heading('Resultados por verificação',1)
 tab=doc.add_table(rows=1, cols=4);tab.style='Table Grid'
 trPr=tab.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');trPr.append(repeat)
 for cell in tab.rows[0].cells:
  shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'E8EEF3');cell._tc.get_or_add_tcPr().append(shd)
 for c,s in zip(tab.rows[0].cells,['Verificação','Situação','Índice','Referência']):c.text=s
 for r in rows(result):
  cells=tab.add_row().cells
  for c,s in zip(cells,[r['Verificação'],r['Situação'],'—' if r['Índice'] is None else f"{r['Índice']:.6f}",r['Referência']]):c.text=str(s)
  doc.add_paragraph(r['Verificação']+' | Valor: '+r['Demanda / valor']+' | Resistência/limite: '+r['Resistência / limite'])
  if r['Observação']:doc.add_paragraph(r['Verificação']+': '+r['Observação'])
 doc.add_heading('Parâmetros das verificações',1)
 local=result['NBR_branches']['local']
 if local.get('MRd_Nmm'):
  doc.add_paragraph('Flexão local MSE: MRd = Wef × fy / 1,1. Wef obtido do crítico local Ml informado para a mesma seção.')
 for i,flt in enumerate(result['FLT_segments'],1):
  if flt.get('FLT'):
   if flt.get('compressed_flange'):doc.add_paragraph(f"Mesa comprimida governante: {flt['compressed_flange']}; comprimento lateral efetivo usado: {flt.get('Ly_used_mm')} mm; Lz torsional: {flt.get('Lz_used_mm')} mm.")
   f=flt['FLT'];doc.add_paragraph(f"FLT trecho {i}: Me = {flt['Me_Nmm']/1e6:.6f} kN·m; Cb = {flt['Cb_used']:.6f}; λ0 = {f['lambda0']:.6f}; χFLT = {f['chi_flt']:.6f}; λp na tensão reduzida = {f['lambda_p_reduced_stress']:.6f}; Wef = {f['Wceff_mm3']:.6f} mm³; γ = {f['gamma']}.")
 shear=result['section_checks'].get('shear',{})
 if shear.get('VRd_N'):doc.add_paragraph(f"Cortante: h plano = {shear['flat_web_mm']:.6f} mm; h/t = {shear['h_over_t']:.6f}; kv = {shear['kv']}; γ = {shear['gamma']}.")
 doc.add_heading('Dados e origem',1)
 fields=result['input_snapshot']['selected_section']['fields']
 sources=list(dict.fromkeys(v['origin'] for v in fields.values()))
 for i,source in enumerate(sources,1):doc.add_paragraph(f'Origem {i}: {source}')
 prop=doc.add_table(rows=1,cols=3);prop.style='Table Grid'
 for c,t in zip(prop.rows[0].cells,['Campo e unidade','Valor','Origem']):c.text=t
 for k,v in fields.items():
  cells=prop.add_row().cells
  for c,t in zip(cells,[k,str(v['value']) if v['value'] is not None else 'Não informado',str(sources.index(v['origin'])+1)]):c.text=t
 d=result['input_data']
 labels={'L_mm':'Vão [mm]','q_uls':'q ELU [N/mm]','P_uls':'P ELU [N]','x_uls':'Posição P ELU [mm]','q_sls':'q ELS [N/mm]','P_sls':'P ELS [N]','x_sls':'Posição P ELS [mm]','actions_origin':'Origem das combinações','Ml_Nmm':'Ml [N·mm]','Mdist_Nmm':'Mdist [N·mm]','critical_origin':'Origem dos críticos','patch_mm':'Contato longitudinal [mm]','patch_origin':'Origem do contato','ELS_limit_mm':'Limite de flecha [mm]','ELS_origin':'Origem do limite de flecha'}
 for k,label in labels.items():
  value=d.get(k)
  doc.add_paragraph(f'{label}: '+('Não informado' if value is None else (f'{value:.6g}' if isinstance(value,(int,float)) else str(value))))
 for i,seg in enumerate(d['segments'],1):
  cb={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}.get(seg.get('Cb_mode'),seg.get('Cb_mode'))
  if 'Ly_top_effective_mm' in seg:
   lateral=f"mesa superior {seg.get('Ly_top_effective_mm')} mm; mesa inferior {seg.get('Ly_bottom_effective_mm')} mm"
  else:lateral=f"mesa comprimida (entrada anterior) {seg.get('Ly_effective_mm')} mm"
  doc.add_paragraph(f"Trecho {i}: {seg.get('start_mm')} a {seg.get('end_mm')} mm; comprimentos efetivos: {lateral}; Lz torsional {seg.get('Lz_effective_mm')} mm; {cb}. Origem: {seg.get('restraint_provenance')}")
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
 doc.add_paragraph('NBR 14762:2010 · estudo parcial · sem travamento da telha. NÃO É APROVAÇÃO GLOBAL. Ligações e apoios fora do escopo.')
 doc.add_paragraph('Projeto: '+result['project']+' | versão: '+result['version'])
 if result['synthetic']:doc.add_paragraph('EXEMPLO DIDÁTICO — DADOS SINTÉTICOS.')
 doc.add_heading('Entradas e premissas',1)
 d=result['input_data'];from .catalogs import catalog_labels
 doc.add_paragraph('Perfil: '+catalog_labels()[d['catalog_index']]+'; aço: '+d['steel_name'])
 doc.add_paragraph('Origem das propriedades: '+d['property_origin'])
 doc.add_paragraph('Críticos: '+d['critical_origin'])
 doc.add_paragraph('Vão [mm]: '+str(d['L_mm']))
 inclination_inputs(doc,d)
 labels={'mass_kg_m':'Massa linear [kg/m]','spacing_m':'Distância entre terças [m]','permanent_kgf_m2':'Permanente [kgf/m²]','live_kgf_m2':'Sobrecarga [kgf/m²]','wind_up_kgf_m2':'Vento para cima [kgf/m²]','wind_down_kgf_m2':'Vento para baixo [kgf/m²]'}
 for k,v in result['load_bundle']['inputs'].items():doc.add_paragraph(f'{labels.get(k,k)}: {v}')
 doc.add_paragraph('Área → linha pela distância entre terças; PP uma única vez pela massa linear. Vento para cima negativo. As 48 combinações de origem são as fornecidas por Lucas em 31/10/2026, filtradas pelos tipos selecionados. Adicionam-se quatro ELU G+1,5P e uma ELS rara G+P, conforme seleção, com P=1 kN isolada de outras variáveis. FLT móvel não tem envelope completo qualificado. A flecha normal pode ser concluída por limite superior conservador no domínio declarado; fora dele permanece parcial. Não equivale a flecha exata.')
 doc.add_paragraph('Tipos selecionados: '+', '.join(d['selected_types']))
 doc.add_paragraph(f"Limites de flecha: L/{d['ELS_down_denominator']:g} descendente; L/{d['ELS_up_denominator']:g} ascendente. Critérios informados, aplicados a cada combinação ELS.")
 doc.add_paragraph('Cada combinação é recalculada. Não se somam índices resistentes ou flechas calculadas com diferentes inércias efetivas. Sem dimensionamento de torção primária, flexão biaxial, continuidade ou balanços.')
 for s in d['segments']:
  cb={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}.get(s.get('Cb_mode'),s.get('Cb_mode'))
  doc.add_paragraph(f"Trecho {s['start_mm']:g} a {s['end_mm']:g} mm. Ly superior: {s.get('Ly_top_effective_mm',s.get('Ly_effective_mm'))} mm; Ly inferior: {s.get('Ly_bottom_effective_mm',s.get('Ly_effective_mm'))} mm; Lz: {s.get('Lz_effective_mm')} mm. {cb}. {s.get('restraint_provenance','')}")
 doc.add_heading('Casos característicos — componentes normais à cobertura',1)
 for k,v in result['load_bundle']['case_q_N_mm'].items():doc.add_paragraph(f'{k}: {v:.6f} kN/m')
 doc.add_heading('Resumo dos casos governantes',1)
 t=doc.add_table(rows=1,cols=4);t.style='Table Grid'
 t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
 for c,v in zip(t.rows[0].cells,['Critério','Combinação','Índice','Situação']):c.text=v
 for r in result['summary']:
  for c,v in zip(t.add_row().cells,[r['Verificação'],r['Combinação'],'—' if r['Índice'] is None else f"{r['Índice']:.6f}",r['Situação']]):c.text=str(v)
 doc.add_heading('Todas as combinações selecionadas',1)
 for item in result['cases']:
  c=item['combination'];doc.add_heading(f"{c['id']} — {c['type']}",2)
  doc.add_paragraph(f"{c['expression']} → q normal={c['q_kN_m']:.6f} kN/m. P normal={c.get('P_N',0)/1000:.3f} kN. Forças/efeitos superpostos antes das verificações.")
  if item.get('evidence',{}).get('inclination'):inclination_report(doc,item['evidence']['inclination'])
  for row in item['rows']:
   index='—' if row['Índice'] is None else f"{row['Índice']:.6f}"
   doc.add_paragraph(f"{row['Verificação']}: {row['Situação']}; índice {index}; {row['Demanda / valor']}; limite/resistência {row['Resistência / limite']}. {row['Referência']}. {row['Observação']}")
  for warning in item['warnings']:doc.add_paragraph('Aviso: '+warning)
 doc.add_paragraph('Identificação das entradas: '+result['input_fingerprint'])
 out=BytesIO();doc.save(out);return out.getvalue()
