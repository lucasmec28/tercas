"""Serialize the independent uniaxial snapshot without solving or source reads."""
from ..three_girt_scope import view, central, NOTICE
from .application import saved_component,ERROR,SCOPE
from .ui import LEVELS,COMPARISONS
from ..three_girt_report import _table


def append(doc,demand):
    c=view(saved_component(demand),demand)
    if c is None:
        if demand.get(ERROR):doc.add_paragraph('Alternativa uniaxial não calculada: '+demand[ERROR])
        return
    doc.add_page_break();doc.add_heading('Alternativa uniaxial com Ix efetivo variável',1)
    doc.add_paragraph(SCOPE)
    doc.add_paragraph('Hipótese declarada: '+c['configuration']['model_origin'])
    p=c['properties'];k=c['criterion']
    doc.add_paragraph(f"Vão físico L={p['L_mm']:.3f} mm; E={p['E_MPa']:.3f} MPa; Ig={p['Ig_mm4']:.6f} mm4; Ml={p['Ml_Nmm']:.6f} Nmm. Origem do crítico local forte: {p['critical_origin']}")
    doc.add_paragraph('NBR 14762:2010 §9.8.5, MSE: lambda=sqrt(|M|/Ml); Ief=Ig até lambda=0,673 e Ief=Ig(1−0,22/lambda)/lambda acima. O pequeno excesso arredondado é limitado a Ig, como na rota escalar existente. Integra-se M(x)m(x)/(E Ief(x)) com separação nas transições. Ml provém da mesma seção própria, não de outra linha nominal de Pierin.')
    doc.add_paragraph(f"Critério da componente isolada: {k['reference_mm']:.3f}/{k['denominator']:.3f}={k['limit_mm']:.6f} mm. Origem: {k['origin']} A referência do critério não encurta o vão da análise.")
    rows=[]
    for case in c['cases']:
        for name,r in case['members'].items():
            rows.append([case['combination']['id'],LEVELS[name],
                '—' if r['deflection_mm'] is None else f"{abs(r['deflection_mm']):.5f}",
                f"{r['Ief_min_over_Ig']:.5f}",
                '—' if r['isolated_component_index'] is None else f"{r['isolated_component_index']:.5f}",
                COMPARISONS[r['comparison']]])
    _table(doc,['Combinação','Travessa','|flecha| mm','Ief min/Ig','Índice próprio','Componente isolada'],rows,[1.3,.8,.8,.8,.8,1.4])
    guards=[[case['combination']['id'],LEVELS[name],f"{r['q_Z_N_mm']:.6f}",f"{r['sigma_gross_max_MPa']:.5f}",f"{c['properties']['fy_MPa']:.3f}"] for case in c['cases'] for name,r in case['members'].items() if not r['gross_elastic_guard']]
    if guards:
        doc.add_heading('Casos fora da guarda elástica bruta',2)
        _table(doc,['Combinação','Travessa','qZ N/mm','Tensão bruta MPa','fy MPa'],guards,[1.4,1.,1.,1.3,1.2])
    doc.add_heading('Limites do modelo reduzido',2)
    doc.add_paragraph('Cada qZ vem da distribuição já salva para aquela travessa e combinação. As vigas são calculadas separadamente: com redução de Ief, a flecha sob metade da carga não é necessariamente metade da flecha central. Não são utilizados esforços, reações, ações nodais ou rigidez dos tirantes da solução 3D. Não se somam a flecha efetiva e uma rotação torsional obtida com rigidez bruta.')
    doc.add_paragraph('O valor matemático é mantido como diagnóstico se a tensão de flexão da própria seção bruta já exceder fy, mas o índice conclusivo é retirado. Esta é uma guarda de validade elástica, não um novo limite atribuído ao §9.8.5. O inverso não prova tensões da seção efetiva; Ief escalar não determina Wef nem deslocamento do centroide.')
    doc.add_paragraph('A alternativa é uma componente de flexão, não a flecha total real nem um limite superior ou inferior garantido da rede. Não resolve interação com N, flexão fraca ou B, rigidez torsional efetiva, estabilidade ou ELS físico completo. Os resultados e as ações da rede permanecem inalterados.')
    doc.add_paragraph('SHA256 do registro uniaxial: '+c['content_sha256'])
