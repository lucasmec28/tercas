"""Diagnostic-only MC for the explicit three-girt branch; no design approval."""
from io import BytesIO
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from .presentation import fmt
from .catalogs import catalog_labels

LEVELS={'upper':'Superior','middle':'Central','lower':'Inferior'}


def _table(doc,headers,rows,widths):
 t=doc.add_table(rows=1,cols=len(headers));t.autofit=False
 pr=t._tbl.tblPr;borders=OxmlElement('w:tblBorders')
 for side in ('top','left','bottom','right','insideH','insideV'):
  b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'D9D9D9');borders.append(b)
 pr.append(borders)
 for col,w in zip(t.columns,widths):col.width=Inches(w)
 for i,rowvalues in enumerate([headers]+list(rows)):
  row=t.rows[0] if i==0 else t.add_row();rp=row._tr.get_or_add_trPr();rp.append(OxmlElement('w:cantSplit'))
  if i==0:rp.append(OxmlElement('w:tblHeader'))
  for j,(cell,value,w) in enumerate(zip(row.cells,rowvalues,widths)):
   cell.width=Inches(w);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;cell.text=str(value)
   cp=cell._tc.get_or_add_tcPr();sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E8EEF4' if i==0 else 'FFFFFF' if i%2 else 'F8F9FA');cp.append(sh)
   margins=OxmlElement('w:tcMar')
   for side in ('top','bottom','left','right'):
    m=OxmlElement('w:'+side);m.set(qn('w:w'),'70');m.set(qn('w:type'),'dxa');margins.append(m)
   cp.append(margins)
   for p in cell.paragraphs:
    p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(2)
    p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 else WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:run.font.size=Pt(9);run.font.bold=i==0;run.font.color.rgb=RGBColor(0,0,0)
 doc.add_paragraph('')
 return t


def word(result,selected=0):
 d=Document();sec=d.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11)
 sec.top_margin=sec.bottom_margin=Inches(.65);sec.left_margin=sec.right_margin=Inches(.7)
 for name in ('Normal','Title','Heading 1','Heading 2','Heading 3'):
  style=d.styles[name];style.font.name='Calibri';style.font.color.rgb=RGBColor(0,0,0)
 d.styles['Normal'].font.size=Pt(10);d.styles['Normal'].paragraph_format.space_after=Pt(6)
 d.styles['Title'].font.size=Pt(22)
 # Remove inherited Word template title rules; title remains plain black.
 for node in list(d.styles.element.iter(qn('w:pBdr'))):node.getparent().remove(node)
 d.add_heading('Diagnóstico elástico de três travessas',0)
 from .study_completion import report_global
 report_global(d,result)
 d.add_paragraph('Memória parcial de solicitações e deslocamentos para Lucas. Este documento não verifica resistência das travessas, tirantes, cantoneiras ou ligações e não conclui atendimento de ELS. Não há aprovação global.',style='Normal')
 d.add_paragraph('Projeto: '+str(result['project'])+'\nPerfil das três travessas: '+catalog_labels()[result['input_data']['catalog_index']])
 if result.get('synthetic'):d.add_paragraph('CASO SINTÉTICO OU DIDÁTICO. Não é projeto ou produto validado.').runs[0].bold=True
 d.add_paragraph('Exibição com duas casas decimais; valores não nulos menores que a resolução aparecem como <0,01 ou −<0,01. JSON mantém precisão integral. Resíduos e tolerâncias numéricas usam notação científica.')
 d.add_paragraph('Estado: '+('Diagnóstico elástico condicional' if result['status']=='conditional_elastic_diagnostic' else 'NÃO RESOLVIDO integralmente')+'. Versão: '+result['version']+'.')
 if result.get('reason'):d.add_paragraph(result['reason'])
 for case in result['cases']:
  if case['model']['status']!='conditional_elastic_diagnostic':d.add_paragraph('COMBINAÇÃO NÃO RESOLVIDA: '+case['combination']['id']+'. '+case['model'].get('reason','Gate numérico não satisfeito.')+' Sem resposta liberada para esse caso.')
 from .model_domain import report as domain_report
 domain_report(d,result)
 d.add_heading('Modelo e entradas declaradas',1)
 c=result['configuration'];data=result['input_data'];p=data['properties']
 d.add_paragraph('Vão '+fmt(data['L_mm'])+' mm; distância igual entre eixos '+fmt(data['area_inputs']['spacing_m']*1000)+' mm; '+str(c['tie_count'])+' linhas de tirantes. Posições a partir de A: '+', '.join(fmt(x) for x in c['resolved_positions_mm'])+' mm.')
 d.add_paragraph(result['support_convention']);d.add_paragraph(result['axis_convention']);d.add_paragraph(result['topology_note'])
 d.add_paragraph('Origem/hipótese: '+c['origin']+'. As declarações não comprovam condições físicas, rigidez da ligação ou ancoragem.')
 _table(d,['Propriedade da travessa','Valor','Unidade'],[[k,fmt(p[k]),unit] for k,unit in [('A_cm2','cm²'),('Ix_cm4','cm⁴'),('Iy_cm4','cm⁴'),('J_mm4','mm⁴'),('Cw_mm6','mm⁶ não usado'),('E_MPa','MPa'),('G_MPa','MPa'),('mass_kg_m','kg/m')]], [3.7,1.6,1.8])
 d.add_paragraph('Origem das propriedades: '+data['property_origin'])
 d.add_paragraph('Vetor CG→SC: Y='+fmt(c['sc_y_mm'])+' mm, Z='+fmt(c['sc_z_mm'])+' mm. Origem: '+c['sc_origin']+'. Linha externa: Y='+fmt(c['load_y_from_CG_mm'])+' mm, Z='+fmt(c['load_z_from_CG_mm'])+' mm a partir do CG. PP das travessas no CG.')
 d.add_paragraph('Ligações: '+c['connection_mode']+'. Braços individuais em mm: '+str(c['resolved_offsets'])+'. Empenamento não modelado.')
 for color in ('blue','green'):
  m=c[color];d.add_paragraph(m['label']+': A='+fmt(m['A_mm2'])+' mm²; E='+fmt(m['E_MPa'])+' MPa; massa='+fmt(m['mass_kg_m'])+' kg/m. '+m['origin'])
 d.add_paragraph(result['load_distribution']+' PP barras '+('incluído.' if c['brace_self_weight'] else 'EXCLUÍDO nesta hipótese; não é dispensa normativa.'))
 if data['load_mode']=='area' and result.get('load_bundle'):
  d.add_heading('Ações características por área de influência',2)
  d.add_paragraph('CP é o valor total informado por área para o peso da telha/revestimento e demais permanentes externos. O produto CP × distância entre travessas dá a carga linear central; superior/inferior recebem metade. PP do perfil não está em CP: cada travessa conserva a massa linear inteira. Sentidos da tabela seguem Y para cima e Z para a direita.')
  raw=data['area_inputs'];vectors=result['load_bundle']['case_vectors_N_mm'];rows=[]
  labels={'PP':'PP do perfil','CP':'CP telha e permanentes','V_Cima':'Vento sucção','V_Baixo':'Vento pressão'}
  area_values={'PP':None,'CP':raw['permanent_kgf_m2'],'V_Cima':raw['wind_up_kgf_m2'],'V_Baixo':raw['wind_down_kgf_m2']}
  for key in labels:
   q=vectors[key];factor=1. if key=='PP' else .5
   rows.append([labels[key],fmt(area_values[key]),fmt(-q['parallel']),fmt(-q['normal']),fmt(-factor*q['parallel']),fmt(-factor*q['normal'])])
  _table(d,['Ação','Área\nkgf/m²','qY central\nkN/m','qZ central\nkN/m','qY extrema\nkN/m','qZ extrema\nkN/m'],rows,[1.8,1.,1.075,1.075,1.075,1.075])
  d.add_paragraph('Extrema significa cada travessa superior ou inferior, não a soma das duas. Combinações abaixo ponderam PP e CP pelos coeficientes da matriz do usuário; PP das barras é adicional, sem duplicar o perfil ou a telha.')
 elif data['load_mode']=='direct':
  from .direct_self_weight import active as pp_active,evidence as pp_evidence
  if pp_active(data):
   pe=pp_evidence(data);d.add_paragraph(pe['scope'])
   d.add_paragraph('PP integral por perfil: ELU='+fmt(pe['states']['uls']['profile_PP_q_N_mm']['parallel'])+' N/mm; ELS='+fmt(pe['states']['sls']['profile_PP_q_N_mm']['parallel'])+' N/mm. Externos recebem 0,5/1/0,5 e o PP não é reduzido.')
  else:
   d.add_paragraph('PP da travessa já contido no q vertical central declarado: ELU='+fmt(c['direct_pp_uls_N_mm'])+' kN/m; ELS='+fmt(c['direct_pp_sls_N_mm'])+' kN/m. A parcela restante inclui telha/revestimento e demais ações verticais externas da combinação; só essa parcela é reduzida à metade nas extremas.')
 if not result['cases']:
  d.add_heading('Pendências que impediram o cálculo',1)
  for text in result.get('missing',[]):d.add_paragraph(text)
 else:
  d.add_heading('Combinações executadas',1)
  _table(d,['Combinação','Estado limite','Gate do modelo','qY central\nN/mm','qZ central\nN/mm','Fator PP barras'],[[x['combination']['id'],x['combination']['limit_state'],'Condicional' if x['model']['status']=='conditional_elastic_diagnostic' else 'NÃO RESOLVIDO',fmt(x['loads'][1]['q_y_N_mm']),fmt(x['loads'][1]['q_z_N_mm']),fmt(x['brace_weight_factor'])] for x in result['cases']],[1.65,.6,1.25,1.15,1.15,1.3])
  case=result['cases'][selected];m=case['model'];d.add_heading('Detalhamento da combinação selecionada',1)
  d.add_paragraph(case['combination']['id']+' — '+case['combination']['limit_state']+'. '+str(case['combination']['expression']))
  d.add_paragraph('As tabelas seguintes detalham SOMENTE esta combinação. Os demais resultados completos por combinação/seção/lado permanecem no JSON; não se combina máximo de ELU com ELS.')
  _table(d,['Travessa','qY N/mm','qZ N/mm','Torque distribuído CG N'],[[LEVELS[k],fmt(q['q_y_N_mm']),fmt(q['q_z_N_mm']),fmt(q['distributed_torque_CG_N'])] for k,q in zip(LEVELS,case['loads'])],[1.5,1.5,1.5,2.6])
  if m['status']!='conditional_elastic_diagnostic':d.add_paragraph('NÃO RESOLVIDO: '+m.get('reason','Gate numérico não satisfeito.'))
  else:
   d.add_heading('Extremos individuais sem interação resistente',2)
   d.add_paragraph('Extremos de componentes diferentes não constituem um estado concomitante. N é tração positiva. Momentos negativos e compressão permanecem na saída. Flechas são brutas e absolutas do CG, sem confronto com limite ELS.')
   rows=[]
   for name,e in m['girt_envelopes'].items():
    for key,label,scale in [('N_N','N kN',1000),('My_strong_Nmm','My forte kN·m',1e6),('Mz_weak_Nmm','Mz fraco kN·m',1e6),('T_CG_Nmm','T CG kN·m',1e6),('uy_CG_mm','uY CG mm',1),('uz_CG_mm','uZ CG mm',1),('rx_rad','Torção rad',1)]:
     ma=e[key]['max_abs'];rows.append([LEVELS[name],label,fmt(e[key]['min'][key]/scale),fmt(e[key]['max'][key]/scale),fmt(ma['x_mm'])])
   _table(d,['Travessa','Componente','Mínimo','Máximo','x de maior |valor| mm'],rows,[1.05,1.65,1.35,1.35,1.7])
   d.add_heading('Reações e barras axiais',2)
   columns=len(m['inputs']['attachment_x_mm'])+2;rows=[]
   for node in m['nodes']:
    if node['id']%columns not in (0,columns-1):continue
    r=node['support_reactions'];rows.append([node['id']]+[fmt(x/1000) for x in r[:3]]+[fmt(x/1e6) for x in r[3:]])
   _table(d,['Nó','Fx kN','Fy kN','Fz kN','Tx kN·m','My kN·m','Mz kN·m'],rows,[.5,1.1,1.1,1.1,1.1,1.1,1.1])
   _table(d,['Barra','N tração positiva kN','Estado sem resistência','PP ponderado N'],[[b['id'],fmt(b['axial_tension_N']/1000),'Tração' if b['axial_state']=='tension' else 'Compressão' if b['axial_state']=='compression' else 'Nulo',fmt(b['self_weight_N'])] for b in m['bars']],[2.3,1.5,1.8,1.5])
   d.add_paragraph('Qualquer força compressiva de barra permanece SEM verificação de flambagem/resistência. Modelo bilateral não demonstra que tirante real suporte compressão. Momentos nos apoios podem incluir r×F de ligação excêntrica; ry/rz de apoio seguem livres.')
   d.add_heading('Estados concomitantes de referência',2)
   d.add_paragraph('Para cada travessa, apresenta-se o estado de maior |Mz fraco| desta combinação, não um máximo de interação. Componentes são do mesmo x e lado. Saltos das juntas e demais estados estão preservados no JSON.')
   for name,e in m['girt_envelopes'].items():
    z=e['Mz_weak_Nmm']['max_abs'];d.add_paragraph(LEVELS[name]+': x='+fmt(z['x_mm'])+' mm, lado '+z['side']+'. N='+fmt(z['N_N']/1000)+' kN; Vy='+fmt(z['Vy_N']/1000)+' kN; Vz='+fmt(z['Vz_N']/1000)+' kN; My forte='+fmt(z['My_strong_Nmm']/1e6)+' kN·m; Mz fraco='+fmt(z['Mz_weak_Nmm']/1e6)+' kN·m; T CG='+fmt(z['T_CG_Nmm']/1e6)+' kN·m; T SC='+fmt(z['T_SC_Nmm']/1e6)+' kN·m.')
   d.add_heading('Controles numéricos',2)
   r=m['residuals'];d.add_paragraph('Máximo resíduo livre: força '+format(r['free_force_max_N'],'.3e')+' N; momento '+format(r['free_moment_max_Nmm'],'.3e')+' N·mm. Balanço global de forças N: '+', '.join(format(x,'.3e') for x in r['global_force_N'])+'. Momentos N·mm: '+', '.join(format(x,'.3e') for x in r['global_moment_Nmm'])+'.')
   d.add_paragraph('Razão de autovalores da matriz escalada='+format(m['stability_diagnostic']['ratio'],'.3e')+'. Gate de condicionamento='+format(m['stability_diagnostic']['threshold'],'.3e')+'. Não é autovalor de flambagem nem resistência. Não se adicionou apoio artificial ou pseudoinversa.')
 d.add_heading('Limites que permanecem abertos',1)
 for text in result['limitations']:d.add_paragraph(text)
 d.add_heading('Fontes e rastreabilidade',1)
 for src in result['sources']:d.add_paragraph(src['title']+'. '+src['use']+'\n'+src['url'])
 d.add_paragraph('SHA256 das entradas: '+result['input_fingerprint']+'. O JSON contém entradas integrais, casos, polinômios, estados concomitantes e resíduos. Esta MC não substitui a qualificação de geometria, empenamento ou resistência.')
 footer=sec.footer.paragraphs[0];footer.text='Diagnóstico parcial sem aprovação resistente ou ELS';footer.runs[0].font.size=Pt(8)
 out=BytesIO();d.save(out);return out.getvalue()
