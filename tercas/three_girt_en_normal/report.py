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
    d.add_paragraph('Verificação complementar EN1993-1-3:2006 §6.1.6 da tensão normal, nas faces do modelo de parede fina facetada. Não é aprovação integral EN ou NBR. Cisalhamento, interação sigma–tau, estabilidade, validade da primeira ordem, ruptura líquida e ELS continuam separados.')
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
    d.add_paragraph('A mesma cláusula EN exige tau_total ≤ fya/(sqrt(3)·gammaM0) e sqrt(sigma_total² + 3·tau_total²) ≤ 1,1·fya/gammaM0. Essas condições NÃO foram verificadas por esta componente. A estabilidade global, efeitos de segunda ordem e validade dos giros não foram liberados.')
    d.add_paragraph('SHA256 do resultado normal salvo: '+c['content_sha256'])
