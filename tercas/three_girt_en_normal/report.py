"""Append the saved EN normal snapshot. No geometry or solver recalculation."""
from .application import saved_component
from .ui import LEVELS
from ..three_girt_report import _table


def append(document,demand):
    c=saved_component(demand)
    if c is None:
        if demand.get('EN_normal_N_M_B_error'):
            document.add_paragraph('Componente normal EN não calculada: '+demand['EN_normal_N_M_B_error'])
        return
    d=document;d.add_page_break();d.add_heading('Componente normal N Mx My B pela EN',1)
    d.add_paragraph('Verificação complementar EN1993-1-3:2006 §6.1.6 da tensão normal, nas faces do modelo de parede fina facetada. Não é aprovação integral EN ou NBR. A cobertura dos ramos efetivos é indicada abaixo; estabilidade, validade da primeira ordem, ruptura líquida e ELS continuam separados.')
    d.add_paragraph('Modelo declarado: '+c['configuration']['section_model_origin']+'. Seção nominal intacta, sem furos/recortes nas regiões representadas. Esta declaração não dimensiona ligações nem comprova a geometria/material real.')
    mat=c['component_sections']['material']
    d.add_paragraph(f"Seção: {c['component_sections']['profile_id']}. fyb = fya = {mat['fyb_MPa']:.2f} MPa; E para a prova seccional EN = {mat['E_MPa']:.0f} MPa; nu = {mat['nu']}; gammaM0 = {mat['gamma_M0']:.2f}. Sem aumento por conformação. E da demanda preservada = {c['demand_material_E_MPa']:.0f} MPa e combinações NBR mantidas, não renomeadas como combinações EN.")
    d.add_paragraph('sigma = N/A − My_frame·y/Istrong + Mz_frame·x/Iweak + B·omega/Cw. Apenas componentes puras integralmente efetivas no ELU recebem coeficientes. Nenhuma resistência NBR/AISI é importada. O limite normal é 250 MPa neste domínio fixo.')
    values=[]
    for member,item in c['per_member'].items():
        w=item['complete_envelope'] or item['partial_maximum']
        values.append([LEVELS[member],f"{item['complete_segments']}/{item['ELU_segments']}",
            '—' if w is None else f"{w['normal_index']:.5f}",
            'Completo' if item['complete'] else 'PARCIAL',
            '—' if w is None else w['combination_id']])
    _table(d,['Travessa','Trechos ELU','Índice normal','Envelope','Combinação'],values,[1.0,1.05,1.2,1.2,1.6])
    d.add_paragraph('Máximos parciais excluem ramos bloqueados e não representam atendimento da travessa. Falha de elegibilidade não é reprovação resistente. Só o envelope completo dentro do limite pode demonstrar atendimento da componente normal no modelo declarado.')
    for member,item in c['per_member'].items():
        d.add_heading('Travessa '+LEVELS[member].lower()+' cobertura e testemunha',2)
        d.add_paragraph('Ramos pendentes: '+(', '.join(item['blocking_components']) or 'nenhum')+f". Intervalos de sinal elegíveis: {item['complete_sign_pieces']}/{item['total_sign_pieces']}.")
        w=item['complete_envelope'] or item['partial_maximum']
        if w:
            if item['observed_normal_exceedance'] and not item['complete']:
                d.add_paragraph('A testemunha abaixo já excede o limite normal em um estado elegível. O máximo permanece PARCIAL: não é envelope completo, nem conclusão global de segurança da barra.')
            s=w['concomitant_7DOF_state'];p=w['section_fiber'];v=w['stress_contributions_MPa']
            d.add_paragraph(f"{w['combination_id']}; trecho {w['segment_id']}; x = {w['x_mm']:.4f} mm, lado {w['side']}; segmento de parede {p['segment_index']}, extremo {p['endpoint']}, face {p['thickness_face_sign']:+d}. sigma = {w['sigma_MPa']:.6f} MPa; índice = {w['normal_index']:.6f}.")
            d.add_paragraph(f"Contribuições concomitantes [MPa]: N {v['N']:.6f}; Mx físico {v['Mx']:.6f}; My físico {v['My']:.6f}; B {v['B']:.6f}. N = {s['N_N']:.6f} N; My_frame = {s['My_strong_Nmm']:.6f} Nmm; Mz_frame = {s['Mz_weak_Nmm']:.6f} Nmm; B = {s['B_equilibrium_Nmm2']:.6f} Nmm².")
    d.add_heading('Domínio da prova e limites restantes',2)
    d.add_paragraph('EN §5.5: larguras locais e rigidez do enrijecedor conferidas no ELU, exigindo larguras integrais e As,red = As pela Eq. 5.17 no campo puro de ELU. Não se promove resultado de serviço a capacidade. O sentido fraco com lábios tracionados/mesa mista permanece não qualificado. A prova de cada componente e seus motivos exatos constam do JSON.')
    d.add_paragraph('As quatro fibras extremas de cada segmento de parede são examinadas, com N/M nas coordenadas exteriores e omega da linha média correspondente, constante na espessura. Extremos longitudinais vêm das raízes de derivadas do campo quadrático/hiperbólico, não de uma malha nem da soma de máximos isolados. Não representa um sólido curvo exato.')
    if any('shear_interaction' in row for row in c['per_member'].values()):
        _append_shear(d,c)
    else:
        d.add_paragraph('Snapshot histórico: cisalhamento e interação sigma–tau não foram calculados. Não se requalifica o resultado durante a exportação.')
    d.add_paragraph('SHA256 do resultado normal salvo: '+c['content_sha256'])


def _append_shear(d,c):
    d.add_heading('Cisalhamento e interação normal–cisalhamento EN',2)
    d.add_paragraph('EN1993-1-3:2006 §6.1.6(3)–(5): cisalhamento transversal, Saint-Venant e empenamento usam a seção bruta coerente; N/M mantêm as seções efetivas por componente. Limites independentes: |tau| ≤ 250/√3 MPa e √(sigma² + 3tau²) ≤ 275 MPa. O limite normal de 250 MPa também continua obrigatório.')
    rows=[]
    for level,item in c['per_member'].items():
        values=item['shear_interaction']
        for key,label in (('shear','Cisalhamento'),('interaction','sigma–tau')):
            row=values[key];upper=None if row is None else row['index_upper_bound'] if values['complete'] else row['partial_index_upper_bound']
            rows.append([LEVELS[level],label,'—' if row is None else f"{row['index_lower_witness']:.5f}",
                '—' if upper is None else f'{upper:.5f}','Completa' if values['complete'] else 'PARCIAL'])
    _table(d,['Travessa','Critério','Testemunha','Limite superior','Cobertura'],rows,[.95,1.0,1.1,1.2,1.0])
    d.add_paragraph('A testemunha é um estado físico concomitante do modelo. O limite superior é um majorante numérico de todo o intervalo e de todas as faces, não uma combinação física de máximos. Só cobertura completa com limite superior ≤ 1 demonstra atendimento do critério no modelo. Uma testemunha > 1 comprova excesso mesmo com cobertura parcial; limite não decidido não vira atendimento.')
    d.add_paragraph('As tensões são recuperadas em ambas as faces e no interior das paredes, não só nas fibras extremas da tensão normal. Envoltória de Bernstein quadrática na parede, com faixas analíticas dos campos hiperbólicos ao longo do vão. Subdivisão apenas quando necessária à decisão. Majorante numérico em binary64 com margem de arredondamento proporcional às magnitudes, não certificado formal de aritmética intervalar. O modelo de parede fina facetada não é um sólido curvo exato.')
    for level,item in c['per_member'].items():
        row=item['shear_interaction']['interaction']
        if row is None:continue
        w=row['witness'];v=w['shear_contributions_MPa']
        d.add_paragraph(f"Travessa {LEVELS[level].lower()}, testemunha sigma–tau: {w['combination_id']}, trecho {w['segment_id']}, x = {w['x_mm']:.4f} mm ({w['side']}), parede {w['segment_index']}, u = {w['u']:.6f}, face {w['thickness_face_sign']:+d}. sigma = {w['sigma_MPa']:.6f} MPa; tau = {w['tau_MPa']:.6f} MPa; equivalente = {w['equivalent_MPa']:.6f} MPa; índice = {w['index']:.6f}.")
        d.add_paragraph(f"Parcelas de tau [MPa]: Vx {v['Vx']:.6f}; Vy {v['Vy']:.6f}; empenamento {v['warping']:.6f}; Saint-Venant {v['Saint_Venant']:.6f}. Sinal na face com normal n = (−dy,dx)/comprimento: tauSV = −face·Tsv·t/J.")
    d.add_paragraph('Os ramos de seção efetiva não implementados continuam pendentes. O critério de tensões §6.1.6 não substitui a resistência/flambagem por cisalhamento §6.1.5 nem interação N–M–V §6.1.10. A estabilidade global, efeitos de segunda ordem, aplicabilidade dos giros e verificações locais/ligações não foram liberados por este complemento.')
