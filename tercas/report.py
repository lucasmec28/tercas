from io import BytesIO
from datetime import datetime,timezone
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .application import rows

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
 for text in ['Um vão isostático, flexão no eixo de simetria forte. Sem dimensionamento de torção primária, flexão biaxial, axial, continuidade ou balanços nesta emissão.', 'Ações ELU e ELS já combinadas, informadas separadamente. Não há geração automática de todas as combinações.', 'Ly e Lz são comprimentos efetivos informados; coordenada de tirante não comprova vínculo torsional.', 'A flecha é componente Euler–Bernoulli com Ief por seção. Limite de flecha é informado com origem; não equivale a aprovação do sistema.', 'Propriedades e críticos fornecidos não são certificados pelo aplicativo. A convenção geométrica das propriedades do catálogo precisa ser conferida para o caso.', 'Apoio com alma ligada: exceção de enrijecedor do §9.5.1 não dimensiona a ligação.']:
  doc.add_paragraph(text,style='List Bullet')
 for warning in result.get('coverage_warnings',[]):doc.add_paragraph(warning)
 if result.get('numerical_warnings'):doc.add_paragraph('Aviso numérico na integração da flecha: critério ELS não concluído.')
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
 labels={'L_mm':'Vão [mm]','q_uls':'q ELU [N/mm]','P_uls':'P ELU [N]','x_uls':'Posição P ELU [mm]','q_sls':'q ELS [N/mm]','P_sls':'P ELS [N]','x_sls':'Posição P ELS [mm]','actions_origin':'Origem das combinações','Ml_Nmm':'Ml [N·mm]','Mdist_Nmm':'Mdist [N·mm]','critical_origin':'Origem dos críticos','support_origin':'Origem dos apoios','patch_mm':'Contato longitudinal [mm]','patch_origin':'Origem do contato','ELS_limit_mm':'Limite de flecha [mm]','ELS_origin':'Origem do limite de flecha'}
 for k,label in labels.items():
  value=d.get(k)
  doc.add_paragraph(f'{label}: '+('Não informado' if value is None else (f'{value:.6g}' if isinstance(value,(int,float)) else str(value))))
 for i,seg in enumerate(d['segments'],1):doc.add_paragraph(f"Trecho {i}: {seg.get('start_mm')} a {seg.get('end_mm')} mm; Ly efetivo {seg.get('Ly_effective_mm')} mm; Lz efetivo {seg.get('Lz_effective_mm')} mm; Cb {seg.get('Cb_mode')}. Origem: {seg.get('restraint_provenance')}")
 doc.add_paragraph('Identificação das entradas: '+result['input_fingerprint'])
 out=BytesIO();doc.save(out);return out.getvalue()
