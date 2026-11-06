"""Optional saved sidecar, never evaluated implicitly during export."""
from .presentation import label,STATES
from .application import saved_assessment


def append(doc,result,assessment):
    if assessment is None:return
    a=saved_assessment(result,assessment)
    doc.add_page_break();doc.add_heading('Panorama do modelo e critérios salvos',1)
    doc.add_paragraph(a['display_summary'])
    doc.add_paragraph(a.get('interpretation','Integridade do resultado requer revisão.'))
    for group in a['groups']:
        count=group['counts'];doc.add_heading(group['title'],2)
        doc.add_paragraph(group['scope'])
        doc.add_paragraph(f"Critérios atendidos: {count['meets']}; não atendidos: {count['fails']}; pendentes: {count['pending']}; não aplicáveis: {count['not_applicable']}.")
    doc.add_heading('Critérios não atendidos e pendências no escopo selecionado',2)
    for r in a['checks']:
        if r['status'] not in ('fails','pending'):continue
        index='' if r['index'] is None else ' | índice '+format(r['index'],'.6g')
        doc.add_paragraph(label(r)+' | '+STATES[r['status']]+index+'. '+r['reason']+' Fonte: '+r['source'])
    doc.add_heading('Dispensas fundamentadas e escopo excluído',2)
    for r in a['checks']:
        if r['status']=='not_applicable':doc.add_paragraph(label(r)+': '+r['reason']+' Fonte: '+r['source'])
    for text in a['excluded_scope']:doc.add_paragraph(text)
    doc.add_paragraph('SHA256 do resultado completo de origem: '+a['source_result_sha256'])
