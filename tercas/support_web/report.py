"""Word export of a saved support-web sidecar, without resistance calculation."""
from io import BytesIO
from .application import saved_assessment

STATUS={'computed':'Calculado: somente critério local','not_evaluated':'Pendente',
        'exempt':'Exceção §9.5.1','stiffener_exception_9_5_1':'Exceção §9.5.1',
        'not_applicable':'Não aplicável: parcela normal nula'}


def display_rows(assessment):
    rows=[]
    for row in assessment['rows']:
        src=row['source_record'];local=row['local']
        rows.append({'Combinação':src['combination_id'],'Apoio':src.get('label',src['support_id']),
            'Força normal sobre a barra [N]':src.get('normal_N'),
            'Força paralela [N]':src.get('parallel_N'),'M forte concomitante [Nmm]':src.get('moment_strong_Nmm'),'FRd local [N]':local.get('FRd_N'),
            'Índice local':local.get('index'),'Situação':STATUS.get(local.get('status'),local.get('status')),
            'Decisão':{'meets':'Atende no recorte','fails':'Não atende no recorte'}.get(local.get('criterion_status'),''),
            'Motivo':local.get('reason','')})
    return rows


def _shown(value):
    if value is None:return 'não informado'
    if type(value) is bool:return 'sim' if value else 'não'
    return str(value)

def _support_label(sid):
    names={'upper':'Superior','middle':'Central','lower':'Inferior','left':'esquerdo','right':'direito'}
    return ' '.join(names.get(v,v) for v in sid.split('_'))

def append(doc,result,assessment):
    saved=saved_assessment(result,assessment)
    doc.add_heading('Alma nas reações de apoio',1)
    from ..three_girt_scope import central, NOTICE
    if central(result):doc.add_paragraph(NOTICE)
    doc.add_paragraph('NBR 14762:2010 §9.5.1 e Anexo D. Critério local separado, inclusive quando P externa é zero. '
                      'Não dimensiona soldas, ligações ou apoios completos e não aprova a barra.')
    doc.add_paragraph('Fonte de demanda: '+str(saved['source_schema'])+'. Resultado vinculado: '+saved['source_fingerprint']+'.')
    doc.add_paragraph('Seção e material salvos: '+str(saved['section']['family'])+'; H='+_shown(saved['section']['H'])+' mm; t='+_shown(saved['section']['t'])+' mm; ri='+_shown(saved['section']['ri'])+' mm; fy='+_shown(saved['section']['fy'])+' MPa. Nenhuma geometria de contato foi inferida da reação.')
    for sid,d in saved['configuration']['details'].items():
        doc.add_heading('Detalhe '+_support_label(sid),2)
        doc.add_paragraph('Rota: '+{'web_connection':'Alma ligada a viga ou pilar','flange_contact':'Contato pela mesa'}.get(d.get('route'),'não informada')+'. Origem: '+str(d.get('origin') or 'não informada')+'.')
        if d.get('route')=='flange_contact':
            doc.add_paragraph('Contato c='+_shown(d.get('c_mm'))+' mm; distância livre ao extremo físico='+_shown(d.get('end_distance_mm'))+
                ' mm; sem força concentrada na mesa oposta='+_shown(d.get('no_opposite_force'))+
                '; distância livre à força oposta='+_shown(d.get('opposite_clear_distance_mm'))+
                ' mm; mesa conectada='+_shown(d.get('connected'))+'; sinal normal compressivo='+_shown(d.get('normal_compressive_sign'))+'.')
            doc.add_paragraph('Orientação declarada: '+str(d.get('loaded_flange_orientation') or 'não descrita')+'.')
    doc.add_heading('Resultados locais salvos por combinação',2)
    table=doc.add_table(rows=1, cols=8);table.style='Light Shading Accent 1'
    labels=['Comb.','Apoio','F normal [N]','F paralelo [N]','M forte [Nmm]','FRd [N]','Índice','Decisão']
    for cell,label in zip(table.rows[0].cells,labels):cell.text=label
    def fmt(v):return '—' if v is None else f'{v:.6g}'
    for row in saved['rows']:
        src=row['source_record'];local=row['local'];cells=table.add_row().cells
        verdict=local.get('criterion_status')
        label={'meets':'Atende local','fails':'Não atende local'}.get(verdict,STATUS.get(local.get('status'),local.get('status')))
        values=[src['combination_id'],_support_label(src['support_id']),fmt(src.get('normal_N')),fmt(src.get('parallel_N')),fmt(src.get('moment_strong_Nmm')),
                fmt(local.get('FRd_N')),fmt(local.get('index')),label]
        for cell,value in zip(cells,values):cell.text=str(value)
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:run.font.size=Pt(9)
    reasons=sorted({row['local'].get('reason','') for row in saved['rows'] if row['local'].get('reason')})
    for reason in reasons:doc.add_paragraph(reason)
    doc.add_heading('Alcance da conclusão',2)
    for text in saved['limits']:doc.add_paragraph(text)
    doc.add_paragraph('Índices exibidos são arredondados; decisões usam os valores completos salvos. '
                      'Cobertura local não é aprovação global. Consulta/exportação não executou solver nem recalculou FRd.')
    doc.add_paragraph('SHA256 da componente salva: '+saved['content_sha256'])
    return doc


def word(result,assessment):
    from docx import Document
    from docx.shared import Cm
    from docx.enum.section import WD_ORIENT
    doc=Document();section=doc.sections[0];section.orientation=WD_ORIENT.LANDSCAPE
    section.page_width=Cm(29.7);section.page_height=Cm(21.0)
    section.left_margin=section.right_margin=Cm(1.5)
    section.top_margin=section.bottom_margin=Cm(1.5)
    append(doc,result,assessment);out=BytesIO();doc.save(out);return out.getvalue()
