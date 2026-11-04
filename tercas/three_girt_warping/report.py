"""Word memory consumes the saved snapshot only; never calls a solver."""
from io import BytesIO
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml.ns import qn
from ..three_girt_report import _table
from .ui import result_rows,LABELS


def word(result,selected=0):
    d=Document();sec=d.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    sec.top_margin=sec.bottom_margin=Inches(.65);sec.left_margin=sec.right_margin=Inches(.7)
    for name in ('Normal','Title','Heading 1','Heading 2'):
        style=d.styles[name];style.font.name='Calibri';style.font.color.rgb=RGBColor(0,0,0)
    d.styles['Normal'].font.size=Pt(10);d.styles['Normal'].paragraph_format.space_after=Pt(5)
    for node in list(d.styles.element.iter(qn('w:pBdr'))):node.getparent().remove(node)
    d.add_heading('Três travessas com empenamento G81 e referência NBR',0)
    d.add_paragraph('Memória parcial de demanda Vlasov, componente G8.1 de bimomento e referência NBR de compressão e flexão para Lucas. N, My, Mz, B e T são concomitantes por combinação e lado. G8.1 não encerra a interação N+M+B, estabilidade, ELS, tirantes ou ligações; não há aprovação global.')
    d.add_paragraph('As combinações da matriz atual são preservadas, sem recombinação LRFD AISI. G8.1 é comparação complementar condicionada; a compatibilidade global das ações e resistências não é declarada por este índice isolado.')
    d.add_paragraph('Estudo: '+result['input_data']['project'])
    if result['input_data'].get('synthetic'):d.add_paragraph('CASO DE QA SINTÉTICO. Não é um projeto físico validado.')
    cfg=result['configuration'];data=result['input_data'];g=cfg['three_girt']
    d.add_heading('Entradas e hipóteses salvas',1)
    d.add_paragraph(f"L = {data['L_mm']:.2f} mm; distância entre eixos = {data['area_inputs']['spacing_m']*1000:.2f} mm; linhas interiores = {g['tie_count']}. Mesma seção atual nas três travessas. Continuidade preservada; barras bilaterais, primeira ordem.")
    d.add_paragraph('Empenamento: '+str(cfg['warping_end_condition'])+'. '+cfg['warping_condition_origin'])
    d.add_paragraph('Eixos: X longitudinal, Y vertical para cima e Z normal. Boca para baixo: Y = −x_R01 e Z = −y_R01; omega preservado. '+result['stress_axis_mapping'])
    d.add_paragraph('Ações externas nas travessas superior, central e inferior: 0,5 / 1 / 0,5. PP do perfil integral no CG de cada travessa; PP das barras integral e ponderado uma vez. Linha externa Y = '+str(g['load_y_from_CG_mm'])+' mm, Z = '+str(g['load_z_from_CG_mm'])+' mm em relação ao CG.')
    types=sorted({end['model'] for pair in cfg['connections'].values() for end in pair})
    d.add_paragraph('Ligações: '+', '.join(types)+'. Pontos materiais usam omega do contorno atual. Resultantes usam Qpsi = 0 explicitamente; não representam omega no centroide. Todos os pontos e origens permanecem no JSON.')
    d.add_heading('Componente G81 por travessa',1)
    rows=result_rows(result)
    summary=[]
    for name in LABELS.values():
        entries=[x for x in rows if x['Travessa']==name]
        if entries:
            a=max(entries,key=lambda x:x['G81']);summary.append([name,a['Combinação'],f"{a['B_Nmm2']:.2f}",f"{a['G81']:.4f}",a['Componente'],f"{a['N_max_abs_N']:.2f}"])
    if summary:
        _table(d,['Travessa','Combinação','B Nmm²','G8.1','Componente','|N|max N'],summary,[.8,1.25,1.5,.8,1.55,1.2])
        cap=next(row['G81_component']['capacity'] for row in result['cases'] if row.get('G81_component'))
        d.add_paragraph(f"AISI S100-2024 G8.1, opção primeiro escoamento: Bn = By = Fy Cw / max|omega|; Ba = 0,90 By = {cap['Ba_Nmm2']:.2f} Nmm². Sem análise adicional de Bcr ou Bp nessa opção. Fonte: https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf")
    else:d.add_paragraph('Nenhuma combinação ELU com componente G8.1 salva. Não há conclusão resistente em ELS.')
    d.add_page_break()
    d.add_heading('Combinação detalhada com esforços concomitantes',1)
    row=result['cases'][selected];d.add_paragraph(row['combination']['id']+' — '+row['combination']['limit_state']+'. Estado de maior |B| de cada travessa; não soma de máximos distintos.')
    values=[]
    for member,env in row['model']['girt_envelopes'].items():
        a=env['B_equilibrium_Nmm2']['max_abs'];values.append([LABELS[member],f"{a['x_mm']:.2f}",f"{a['N_N']:.2f}",f"{a['My_strong_Nmm']/1e6:.4f}",f"{a['Mz_weak_Nmm']/1e6:.4f}",f"{a['B_equilibrium_Nmm2']:.2f}",f"{a['T_equilibrium_SC_Nmm']/1e6:.4g}"])
    _table(d,['Travessa','x mm','N N','My kNm','Mz kNm','B Nmm²','T SC kNm'],values,[.8,.7,.7,.9,.9,1.6,1.1])
    d.add_paragraph('A central conserva o esforço normal real. H4 reduzido a N=0 não foi aplicado. Os esforços completos N/M/B/T, ambos os lados, reações e forças dos tirantes estão no JSON salvo.')
    d.add_heading('Componentes por combinação ELU',1)
    _table(d,['Combinação','Travessa','G8.1','Componente'],[[x['Combinação'],x['Travessa'],f"{x['G81']:.4f}",x['Componente']] for x in rows],[1.6,1.3,1.1,2.1])
    d.add_heading('Controle e rastreabilidade',1)
    q=row['model']['diagnostics'];d.add_paragraph('Corpo livre máximo escalado: '+format(q['physical_left_free_body_max_scaled'],'.3e')+'; erro relativo de trabalho: '+format(q['energy']['relative_error'],'.3e')+'. Vínculos, balanço de bimomento e trabalho do ponto foram verificados no cálculo salvo.')
    d.add_paragraph('SHA256 das entradas e hipóteses: '+result['input_fingerprint'])
    for text in result['limitations']:d.add_paragraph(text)
    from ..three_girt_axial.report import append as append_nbr
    append_nbr(d,result,selected)
    from ..three_girt_en_normal.report import append as append_en_normal
    append_en_normal(d,result)
    out=BytesIO();d.save(out);return out.getvalue()
