"""Append saved NBR reference arithmetic to the existing calculation memory."""
from .application import saved_component
from .ui import LEVELS
from ..three_girt_report import _table


def append(doc,demand,selected=0):
    component=saved_component(demand)
    if component is None:
        if demand.get('NBR_axial_bending_error'):
            doc.add_heading('Compressão e flexão NBR pendentes',1)
            doc.add_paragraph('A demanda Vlasov está preservada, mas a referência NBR não foi calculada: '+demand['NBR_axial_bending_error'])
        return
    doc.add_page_break();doc.add_heading('Compressão e flexão das travessas pela NBR',1)
    doc.add_paragraph('Componente aritmética NBR 14762:2010 §9.9 com esforço normal da rede e momentos da mesma seção. Os denominadores são referências escalares de vão inteiro, com K = Cb = Cm = 1. Não constituem aprovação da estabilidade do conjunto tridimensional, interação N+M+B ou ELS.')
    doc.add_paragraph('O envelope da soma é procurado por zeros e pontos estacionários em cada trecho. Combinações e lados das juntas ficam separados. N positivo seleciona tração; N negativo seleciona compressão, sem reduzir a soma. Mz do frame positivo comprime a alma; o negativo comprime os lábios.')
    values=[]
    for level,p in component['per_member'].items():
        full=p['complete_reference_envelope'];w=full or p['partial_reference_maximum']
        values.append([LEVELS[level],f"{p['arithmetic_complete_segments']}/{p['ELU_segments']}",
            'Pendente' if w is None else f"{w['state']['numeric_index']:.6f}",
            'Completo da referência' if full else 'Parcial',
            '—' if w is None else w['combination_id'],', '.join(p['missing_capacity_keys']) or 'Nenhum'])
    _table(doc,['Travessa','Trechos ELU','Índice ref','Envelope','Combinação','Denominador faltante'],values,[.8,.75,.9,1.4,1.4,1.85])
    comp=component['capacities']['compression'];c=comp['capacity'];e=comp['elastic'];t=component['capacities']['tension'];b=component['capacities']['bending']
    nc='pendente' if c['Nc_Rd_N'] is None else f"{c['Nc_Rd_N']/1000:.6f} kN"
    nt='pendente' if t['Nt_Rd_N'] is None else f"{t['Nt_Rd_N']/1000:.6f} kN"
    aef='pendente' if comp['local']['Aef_mm2'] is None else f"{comp['local']['Aef_mm2']:.6f}"
    doc.add_paragraph(f"Nc,Rd = {nc}; Nt,Rd = {nt}. Compressão: Ne = {e['Ne_N']:.6f} N, chi = {e['chi']:.8f}, tensão para Aef = {e['sigma_effective_MPa']:.6f} MPa. Aef = {aef} mm²; gamma de compressão = 1,20. A dispensa distorcional compressiva, quando atendida pela Tabela 11, não foi transportada à flexão.")
    from .tension_detail_ui import append_report as append_tension_detail
    append_tension_detail(doc,t)
    doc.add_paragraph('Momentos resistentes da referência em kNm: forte positivo '+f"{b['strong_positive']['MRd_Nmm']/1e6:.6f}"+', forte negativo '+f"{b['strong_negative']['MRd_Nmm']/1e6:.6f}"+', fraco com alma comprimida '+f"{b['weak_web_compressed']['MRd_Nmm']/1e6:.6f}"+' e fraco com lábios comprimidos '+f"{b['weak_lips_compressed']['MRd_Nmm']/1e6:.6f}"+'. Fontes próprias e sentido da fibra comprimida preservados; não são novas capacidades de N+M+B.')
    sl=e['compression_slenderness'];maxsl=max(sl['symmetry_axis'],sl['orthogonal_axis'])
    ll=component['configuration']['effective_lengths_mm']
    doc.add_paragraph(f"Comprimentos efetivos da referência: eixo de simetria {ll['symmetry']:.2f} mm, eixo ortogonal {ll['orthogonal']:.2f} mm e torção {ll['torsion']:.2f} mm. KL/r máximo = {maxsl:.6f}; limite compressivo de §9.7.4 = 200. "+('LIMITE EXCEDIDO na referência de vão inteiro.' if not sl['satisfied'] else 'Limite escalar atendido nesta referência.')+' Cada nó de tirante permanece região de introdução de força, não novo apoio de flambagem. A regra de tração L/r <= 300 é uma recomendação distinta.')
    if t['Nt_Rd_N'] is None:
        doc.add_paragraph('Tração incompleta: faltam An0 fora da ligação, An dos caminhos pertinentes na ligação e Ct aplicável com origem. Fy e Fu já vêm das entradas. Ag não foi adotada como área líquida implícita; os trechos tracionados ficam sem índice completo.')
    doc.add_paragraph(f"Maior magnitude de giro nas estações exportadas: {component['maximum_observed_abs_twist_at_exported_stations_rad']:.6f} rad. A aplicabilidade da análise linear em pequenas rotações não está qualificada. Os resultados são referência computacional condicionada, especialmente quando os giros são grandes.")
    doc.add_page_break();doc.add_heading('Estado governante da referência por travessa',1)
    for level,p in component['per_member'].items():
        w=p['complete_reference_envelope'] or p['partial_reference_maximum']
        if not w:
            doc.add_paragraph(LEVELS[level]+': nenhum trecho com todos os denominadores disponíveis.');continue
        s=w['state'];terms=s['contributions'];v=s['concomitant_7DOF_state'];partial=p['complete_reference_envelope'] is None
        doc.add_heading(LEVELS[level]+(' com cobertura parcial' if partial else ''),2)
        doc.add_paragraph(f"Combinação {w['combination_id']}, trecho {w['segment_id']}, x = {s['x_mm']:.6f} mm, lado {s['side']}. N = {s['N_tension_positive_N']:.6f} N; Mforte = {s['Mstrong_Nmm']/1e6:.6f} kNm; Mfraco = {s['Mweak_Nmm']/1e6:.6f} kNm.")
        doc.add_paragraph(f"Parcela axial {terms['axial']:.8f} + forte {terms['strong']:.8f} + fraca {terms['weak']:.8f} = {s['numeric_index']:.8f}. "+('É o máximo dos trechos disponíveis, não envelope completo da central.' if partial else 'É o envelope aritmético completo dos trechos desta referência.'))
        if v is not None:doc.add_paragraph(f"No mesmo ponto: B = {v['B_equilibrium_Nmm2']:.6f} Nmm², T no centro de cisalhamento = {v['T_equilibrium_SC_Nmm']:.6g} Nmm, Vy = {v['Vy_N']:.6g} N e Vz = {v['Vz_N']:.6g} N. Esses valores não receberam parcelas inventadas na soma §9.9.")
    doc.add_heading('Escopos que permanecem separados',1)
    doc.add_paragraph('A análise física e seus limites lineares, vínculos reais, instabilidade do sistema com torque/empenamento, interação com T/B/cisalhamento, efeitos locais, ligações e ELS não foram encerrados por esta componente. H4 não foi usado para omitir N. A resistência dos tirantes e cantoneiras continua fora do escopo. Nenhuma aprovação global é emitida.')
    doc.add_paragraph('Referência normativa: ABNT NBR 14762:2010, exemplar fornecido, §§9.2, 9.6, 9.7, 9.8.2 e 9.9. A validação desta componente reutiliza os cálculos e fontes já auditados; não constitui confirmação de vigência de todas as normas referenciadas.')
    doc.add_paragraph('SHA256 da demanda consumida: '+component['source_demand_sha256'])
    doc.add_paragraph('SHA256 da componente NBR salva: '+component['content_sha256'])
