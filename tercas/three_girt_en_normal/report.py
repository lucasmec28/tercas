"""Append the saved EN normal snapshot. No geometry or solver recalculation."""
from ..three_girt_scope import view, central, NOTICE
from .application import saved_component,SCHEMA
from . import centroid_policy as cp
from . import snapshot_policy as sp
from .ui import LEVELS
from ..three_girt_report import _table

CRITERIA={
    sp.PENDING:"histórico: decisão não autenticada; solicitar novo cálculo",
    'within_1_by_full_interval_upper_bound':'atende pelo limite superior no recorte',
    'above_1_at_concomitant_state':'excesso em estado físico concomitante',
    'above_1_at_checked_state_full_envelope_incomplete':'excesso verificado, com cobertura parcial',
    'unresolved_numerical_bound':'inconclusivo: limite numérico não decidiu',
    cp.PENDING:'pendente: cenário sem deslocamento do centroide não coberto',
    'incomplete_section_branch_coverage':'inconclusivo: falta ramo de seção efetiva'}


def append(document,demand):
    c=view(saved_component(demand),demand)
    if c is None:
        if demand.get('EN_normal_N_M_B_error'):
            document.add_paragraph('Componente normal EN não calculada: '+demand['EN_normal_N_M_B_error'])
        return
    d=document;d.add_page_break();d.add_heading('Componente normal N Mx My B pela EN',1)
    if not sp.certified(c):d.add_paragraph(sp.NOTICE)
    d.add_paragraph('Verificação complementar EN1993-1-3:2006 §6.1.6 da tensão normal, nas faces do modelo de parede fina facetada. Não é aprovação integral EN ou NBR. A cobertura dos ramos efetivos é indicada abaixo; estabilidade, validade da primeira ordem, ruptura líquida e ELS continuam separados.')
    d.add_paragraph('Modelo declarado: '+c['configuration']['section_model_origin']+'. Seção nominal intacta, sem furos/recortes nas regiões representadas. Esta declaração não dimensiona ligações nem comprova a geometria/material real.')
    mat=c['component_sections']['material']
    d.add_paragraph(f"Seção: {c['component_sections']['profile_id']}. fyb = fya = {mat['fyb_MPa']:.2f} MPa; E para a prova seccional EN = {mat['E_MPa']:.0f} MPa; nu = {mat['nu']}; gammaM0 = {mat['gamma_M0']:.2f}. Sem aumento por conformação. E da demanda preservada = {c['demand_material_E_MPa']:.0f} MPa e combinações NBR mantidas, não renomeadas como combinações EN.")
    if any('normal' in item for item in c['per_member'].values()):
        d.add_paragraph('sigma = N/Aeff,N + Mx,corr·gMx(x,y) + My,corr·gMy(x,y) + B·omega/Cw. Cada g é o operador afim da seção efetiva correspondente ao sinal real do momento, com seus coeficientes c0,cx,cy salvos no JSON. Eixos R01 relativos ao centroide bruto; Mx,corr = −My_frame − N·ey e My,corr = −Mz_frame + N·ex. N/Aeff,N é uniforme e Ne entra uma única vez. Limite normal 250 MPa. A troca de operador de flexão não altera a rede original.')
    elif any('normal_action_reference' in row for row in c['rows']):
        d.add_paragraph('sigma = N/Aeff,N + Mx,corr·y/Istrong − My,corr·x/Iweak + B·omega/Cw. Eixos físicos R01; e = Ceff,N − Cg; Mx,corr = −My_frame − N·ey e My,corr = −Mz_frame + N·ex. Os sinais corrigidos escolhem as respectivas seções de flexão. O termo axial é uniforme e não contém uma segunda parcela N·e. Somente ramos efetivos demonstrados recebem coeficientes; nenhum denominador NBR/AISI é importado. Limite normal: 250 MPa.')
    else:
        d.add_paragraph('sigma = N/A − My_frame·y/Istrong + Mz_frame·x/Iweak + B·omega/Cw. Apenas componentes puras integralmente efetivas no ELU recebem coeficientes. Nenhuma resistência NBR/AISI é importada. O limite normal é 250 MPa neste domínio fixo.')
    values=[];has_bounds=any('normal' in item for item in c['per_member'].values())
    for member,item in c['per_member'].items():
        w=item['complete_envelope'] or item['partial_maximum']
        if has_bounds:
            normal=item['normal'];lower=normal['index_lower_witness']
            upper=normal['index_upper_bound'] if item['complete'] else normal['partial_index_upper_bound']
            values.append([LEVELS[member],f"{item['complete_segments']}/{item['ELU_segments']}",
                '—' if lower is None else f"{lower:.5f}",'—' if upper is None else f"{upper:.5f}",
                'Completa' if item['complete'] else 'PARCIAL'])
        else:
            values.append([LEVELS[member],f"{item['complete_segments']}/{item['ELU_segments']}",
                '—' if w is None else f"{w['normal_index']:.5f}",
                'Completo' if item['complete'] else 'PARCIAL',
                '—' if w is None else w['combination_id']])
    if has_bounds:
        _table(d,['Travessa','Trechos ELU','Testemunha normal','Limite superior','Cobertura'],values,[1.0,1.05,1.25,1.25,1.5])
        d.add_paragraph('Normal: a testemunha é um estado físico concomitante e não é apresentada como máximo exato. O limite superior cobre todos os operadores possíveis nos intervalos de troca de sinal. Só cobertura completa com limite superior ≤1 e cobertura de EN6.1.3(3), quando aplicável, demonstra atendimento; limite inferior da testemunha >1 comprova excesso. Se a testemunha não excede 1 e o limite superior excede 1, a decisão é inconclusiva. Não se decide por tolerância em torno de 1. Limite numérico em binary64, não certificado formal intervalar.')
    else:
        _table(d,['Travessa','Trechos ELU','Índice normal','Envelope','Combinação'],values,[1.0,1.05,1.2,1.2,1.6])
    d.add_paragraph('Máximos parciais excluem ramos bloqueados e não representam atendimento da travessa. Falha de elegibilidade não é reprovação resistente. Só o envelope completo dentro do limite pode demonstrar atendimento da componente normal no modelo declarado.')
    for member,item in c['per_member'].items():
        d.add_heading('Travessa '+LEVELS[member].lower()+' cobertura e testemunha',2)
        d.add_paragraph('Ramos pendentes: '+(', '.join(item['blocking_components']) or 'nenhum')+f". Intervalos de sinal elegíveis: {item['complete_sign_pieces']}/{item['total_sign_pieces']}.")
        if has_bounds:d.add_paragraph('Decisão normal com cobertura normativa: '+CRITERIA[cp.decision(c,member,'normal',item['normal']['criterion'])]+'. Os índices apresentados são arredondados; a decisão usa os valores completos salvos.')
        w=item['complete_envelope'] or item['partial_maximum']
        if w:
            if sp.certified(c) and item['observed_normal_exceedance'] and not item['complete']:
                d.add_paragraph('A testemunha abaixo já excede o limite normal em um estado elegível. O máximo permanece PARCIAL: não é envelope completo, nem conclusão global de segurança da barra.')
            s=w['concomitant_7DOF_state'];p=w['section_fiber'];v=w['stress_contributions_MPa']
            d.add_paragraph(f"{w['combination_id']}; trecho {w['segment_id']}; x = {w['x_mm']:.4f} mm, lado {w['side']}; segmento de parede {p['segment_index']}, extremo {p['endpoint']}, face {p['thickness_face_sign']:+d}. sigma = {w['sigma_MPa']:.6f} MPa; índice = {w['normal_index']:.6f}.")
            moment_label='corrigido' if w.get('normal_action_reference') else 'físico'
            d.add_paragraph(f"Contribuições concomitantes [MPa]: N {v['N']:.6f}; Mx {moment_label} {v['Mx']:.6f}; My {moment_label} {v['My']:.6f}; B {v['B']:.6f}. Ações originais: N = {s['N_N']:.6f} N; My_frame = {s['My_strong_Nmm']:.6f} Nmm; Mz_frame = {s['Mz_weak_Nmm']:.6f} Nmm; B = {s['B_equilibrium_Nmm2']:.6f} Nmm².")
            reference=w.get('normal_action_reference')
            if reference:
                add=reference['additional_moments_R01'];corr=reference['corrected_actions_R01']
                d.add_paragraph(f"Transporte R01 nesta testemunha: DeltaMx = {add['Mx']:.6f} Nmm; DeltaMy = {add['My']:.6f} Nmm; Mx,corr = {corr['Mx']:.6f} Nmm; My,corr = {corr['My']:.6f} Nmm.")
    axial=c['component_sections']['components']['N_compression']
    if axial.get('moment_transport_required'):
        distorted=axial.get('section_status')=='effective_local_distortional_reduced_uniform_compression_ULS'
        d.add_heading('Compressão uniforme com seção efetiva reduzida' if distorted else 'Compressão uniforme com alma reduzida',2)
        e=axial['centroid_shift_from_gross_mm'];ep=axial['effective_properties']
        d.add_paragraph(f"EN §6.1.3 e §6.1.6: Aeff,N = {ep['A_mm2']:.6f} mm², ex = {e[0]:.9f} mm e ey = {e[1]:.9f} mm.")
        if distorted:
            d.add_paragraph('EN §5.5.3.2, passos 1–2: larguras efetivas locais em compressão uniforme ELU, seguidas da redução distorcional exclusivamente nos dois enrijecedores físicos As. t_red = t·chi_d em seus intervalos retidos; o restante da seção local mantém t. O refinamento iterativo do passo 3 é opcional e não foi usado. A área não recebe uma segunda redução global.')
            for item in axial['stiffeners']:
                d.add_paragraph(f"Enrijecedor: As = {item['As_mm2']:.6f} mm²; lambda_d = {item['lambda_d']:.9f}; chi_d = {item['chi_d']:.9f}; t_red = {c['component_sections']['thickness_mm']*item['chi_d']:.9f} mm.")
            d.add_paragraph('O ramo axial qualificado não libera os ramos de flexão pendentes. Os ramos seccionais efetivamente pendentes são listados por travessa acima; N qualificado não substitui nenhum deles. O transporte N·e e os sinais corrigidos podem exigir esses ramos, mantendo o envelope parcial. Intervalos e fatores de espessura constam do JSON.')
        else:
            d.add_paragraph('Somente a faixa central da alma é retirada pelas larguras efetivas em compressão uniforme ELU. Mesas e lábios permanecem integrais, com chi_d = 1 nos dois enrijecedores físicos. Faixas, propriedades e auditorias constam do JSON.')
        d.add_paragraph('O transporte dos momentos por N·e ocorre uma única vez no cenário corrigido. Não é substituição da seção efetiva pela bruta nem solução de tensão de serviço. As ações, reações e rigidezes da rede original permanecem inalteradas; B, omega/Cw e cisalhamento mantêm a seção bruta coerente prevista em §6.1.6. Estabilidade global e primeira ordem continuam sem aprovação por este complemento.')
        d.add_paragraph(cp.NOTICE+' Os números e testemunhas nas tabelas anteriores pertencem ao cenário corrigido salvo. Históricos sem prova adicional conservam esses números, mas não recebem crédito favorável.')
        coverage=[]
        for member in c['per_member']:
            for key,label in (('normal','Normal'),('interaction','sigma–tau')):
                policy=cp.qualification(c,member,key)
                if not policy['required_segments']:continue
                upper=policy['original_index_upper_bound']
                coverage.append([LEVELS[member],label,f"{policy['covered_segments']}/{policy['required_segments']}",
                    '—' if upper is None else f'{upper:.5f}','Coberto' if policy['qualified'] else 'PENDENTE'])
        if coverage:
            _table(d,['Travessa','Critério','Trechos cobertos','Teto sem deslocamento','EN 6.1.3(3)'],coverage,[.9,.9,1.1,1.5,1.2])
            d.add_paragraph('Prova suficiente: D ≥ max|sigma_original − sigma_corrigida|. O teto original é Ucorr + D/250 para normal e Ucorr + D/275 para sigma–tau. D cobre os operadores dos sinais de ambos os cenários e toda a parede/trecho; B e tau não mudam. O teto não recebe posição, fibra, estado concomitante ou testemunha física.')
    flexures=[(name,c['component_sections']['components'][name]) for name in ('Mx_positive','Mx_negative') if c['component_sections']['components'][name].get('section_status')=='effective_local_flange_reduced_pure_Mx_ULS']
    if flexures:
        d.add_heading('Flexão forte com mesa localmente reduzida',2)
        d.add_paragraph('Mx positivo e negativo em 1,20 mm: largura efetiva da mesa comprimida pelo campo uniforme fyb conservador; alma e lábios rechecados no campo final. O As físico comprimido satisfaz Eq5.17 com As_red/As = 1 no puro ELU normalizado nas faces. Não há segunda redução da área nem transporte N·e associado a momento puro.')
        for name,record in flexures:
            props=record['effective_properties'];coef=record['sigma_coefficients_c0_cx_cy'];stiff=record['stiffeners'][0]
            d.add_paragraph(f"{name}: Aeff = {props['A_mm2']:.6f} mm²; Ixy = {props['Ixy_mm4']:.6f} mm4; gMx(x,y) = {coef[0]:.12g} + ({coef[1]:.12g})·x + ({coef[2]:.12g})·y. sigmaAs = {stiff['sigma_com_Ed_MPa']:.6f} MPa; chi_d·fyb = {stiff['chi_d']*mat['fyb_MPa']:.6f} MPa. O operador preserva N=0 e My=0 no momento puro; c0 é a referência da seção efetiva, não outra parcela Ne.")
    d.add_heading('Domínio da prova e limites restantes',2)
    d.add_paragraph('EN §5.5: larguras locais conferidas no ELU. Nos ramos integrais com enrijecedor comprimido, demonstra-se As,red = As pela Eq. 5.17. Na compressão fina explicitamente qualificada, aplica-se a redução de As pela mesma equação no campo uniforme ELU. Não se promove resultado de serviço a capacidade. A prova de cada componente e seus motivos exatos constam do JSON.')
    inverse=c['component_sections']['components']['My_negative']
    if inverse.get('outstand_flange_bounds'):
        if inverse.get('section_status')=='effective_web_reduced_negative_My_ULS':
            web=next(row for row in inverse['local_panels'] if row['panel']=='web')
            bound=inverse['outstand_flange_bounds'][0];amplitude,end=bound['bound_stress_ends_MPa'];kind='triangular' if bound['bound_psi']==0 else 'misto';end_text=f'{end:.0f}'.replace('-','−')
            d.add_paragraph(f"My negativo {c['component_sections']['thickness_mm']:.2f} mm: alma efetiva com rho = {web['rho']:.12f}, obtida por ponto fixo EN1993-1-5 §4.4(4), Nota 1, no estado puro ELU normalizado nas faces. Mesas integrais por majorante {kind} {amplitude:.0f}→{end_text} MPa, psi = {bound['bound_psi']:.2f} e k = {bound['k_sigma']:.5f}, com Eq4.4 e dominância em todas as faces. Lábios tracionados; não se usa Eq5.17 negativa. O operador afim de My preserva N=0 na seção efetiva; não é uma segunda correção Ne. Iteração, resíduos e propriedades constam do JSON.")
            if bound['bound_psi']<0:d.add_paragraph('O majorante misto aproveita apenas a tração da própria mesa admitida pela Tabela4.2, menor que a tração real demonstrada. Não acrescenta apoio, mola ou rigidez do lábio.')
            d.add_paragraph('Apoio translacional convencional na junção dos painéis e rotação livre na mesa em balanço. Não cobre modos acoplados com translação das junções.')
        else:
            d.add_paragraph('Ramo de alma comprimida/lábios tracionados: prova adicional de mesa em balanço sem crédito ao lábio, EN1993-1-5 Tabela 4.2. Campo majorante triangular de compressão 250→0 MPa, psi = 0 e k = 1,70; compara todas as fibras da mesa e confirma lábios não comprimidos. Rotação livre na junção, mantendo o apoio translacional convencional do modelo de painéis. Não cobre modos acoplados com translação das junções. Não se afirma que o conjunto As da mesa mista é todo tracionado nem se usa Eq. 5.17 com tensão negativa.')
        d.add_paragraph('A prova está completa no domínio seccional indicado.' if inverse['eligible'] else 'A prova ainda requer redução local não implementada; este ramo continua pendente, sem coeficientes brutos de substituição.')
        web=next(row for row in inverse['local_panels'] if row['panel']=='web')
        trial=web.get('Eq4_4_ULS_integral_trial')
        if trial:
            d.add_paragraph(f"Tentativa integral da alma pela EN1993-1-5 Eq.4.4 no estado puro ELU: compressão máxima incluindo faces = {trial['sigma_com_Ed_MPa']:.6f} MPa; lambda reduzida = {trial['lambda_p_reduced']:.9f}, limite integral = {web['lambda_p_integral_limit']:.9f}. Só é aceita com todas as placas e majorantes integrais, mantendo o campo ELU e a geometria invariáveis. Não é redução por tensão de serviço nem dispensa de estabilidade global.")

    else:
        d.add_paragraph('Neste snapshot histórico, o sentido fraco com lábios tracionados/mesa mista permanece não qualificado; o arquivo não é reavaliado durante a exportação.')
    d.add_paragraph('As quatro fibras extremas de cada segmento de parede são examinadas, com N/M nas coordenadas exteriores e omega da linha média correspondente, constante na espessura. Candidatos longitudinais incluem raízes de derivadas do campo quadrático/hiperbólico; intervalos microscópicos podem usar um majorante pela derivada. Os limites superiores cobrem todo o domínio, não dependem de uma malha nem da soma de máximos isolados. Não representa um sólido curvo exato.' if has_bounds else 'As quatro fibras extremas de cada segmento de parede são examinadas, com N/M nas coordenadas exteriores e omega da linha média correspondente, constante na espessura. Extremos longitudinais vêm das raízes de derivadas do campo quadrático/hiperbólico, não de uma malha nem da soma de máximos isolados. Não representa um sólido curvo exato.')
    if any('shear_interaction' in row for row in c['per_member'].values()):
        _append_shear(d,c)
    else:
        d.add_paragraph('Snapshot histórico: cisalhamento e interação sigma–tau não foram calculados. Não se requalifica o resultado durante a exportação.')
    from ..three_girt_en_mv import append_report as append_mv
    append_mv(d,c)
    d.add_paragraph('SHA256 do resultado normal salvo: '+c['content_sha256'])


def _append_shear(d,c):
    d.add_heading('Cisalhamento e interação normal–cisalhamento EN',2)
    d.add_paragraph('EN1993-1-3:2006 §6.1.6(3)–(5): cisalhamento transversal, Saint-Venant e empenamento usam a seção bruta coerente; N/M mantêm as seções efetivas por componente. Limites independentes: |tau| ≤ 250/√3 MPa e √(sigma² + 3tau²) ≤ 275 MPa. O limite normal de 250 MPa também continua obrigatório.')
    rows=[]
    for level,item in c['per_member'].items():
        values=item['shear_interaction']
        for key,label in (('shear','Cisalhamento'),('interaction','sigma–tau')):
            row=values[key];upper=None if row is None else row['index_upper_bound'] if values['complete'] else row['partial_index_upper_bound']
            rows.append([LEVELS[level],label,'—' if row is None else ('—' if row['index_lower_witness'] is None else f"{row['index_lower_witness']:.5f}"),
                '—' if upper is None else f'{upper:.5f}','Completa' if values['complete'] else 'PARCIAL'])
    _table(d,['Travessa','Critério','Testemunha','Limite superior','Cobertura'],rows,[.95,1.0,1.1,1.2,1.0])
    for level,item in c['per_member'].items():
        values=item['shear_interaction']
        decisions=[name+': '+('sem ramo elegível' if values[key] is None else CRITERIA[cp.decision(c,level,key,values[key]['criterion'])]) for key,name in (('shear','cisalhamento'),('interaction','interação'))]
        d.add_paragraph(LEVELS[level]+'; '+'; '.join(decisions)+'.')
    d.add_paragraph(('No registro histórico, os valores abaixo são observações salvas, sem autenticação atual. ' if not sp.certified(c) else '')+'A testemunha é um estado físico concomitante do modelo. A coluna Testemunha usa seu limite inferior conservador quando disponível. O limite superior é um majorante numérico de todo o intervalo e de todas as faces, não uma combinação física de máximos. Só cobertura completa com limite superior ≤ 1 e cobertura de EN6.1.3(3), quando aplicável, demonstra atendimento do critério no modelo. O limite inferior de uma testemunha > 1 comprova excesso mesmo com cobertura parcial; limite não decidido não vira atendimento.')
    d.add_paragraph('As tensões são recuperadas em ambas as faces e no interior das paredes, não só nas fibras extremas da tensão normal. Envoltória de Bernstein quadrática na parede, com faixas analíticas dos campos hiperbólicos ao longo do vão. Subdivisão apenas quando necessária à decisão. Majorante numérico em binary64 com margem de arredondamento proporcional às magnitudes, não certificado formal de aritmética intervalar. O modelo de parede fina facetada não é um sólido curvo exato.')
    for level,item in c['per_member'].items():
        row=item['shear_interaction']['interaction']
        if row is None:continue
        w=row['witness']
        if w is None:
            d.add_paragraph('Travessa '+LEVELS[level].lower()+': sem testemunha física válida para este critério; decisão preservada pelos limites e cobertura salvos.')
            continue
        v=w['shear_contributions_MPa']
        d.add_paragraph(f"Travessa {LEVELS[level].lower()}, testemunha sigma–tau: {w['combination_id']}, trecho {w['segment_id']}, x = {w['x_mm']:.4f} mm ({w['side']}), parede {w['segment_index']}, u = {w['u']:.6f}, face {w['thickness_face_sign']:+d}. sigma = {w['sigma_MPa']:.6f} MPa; tau = {w['tau_MPa']:.6f} MPa; equivalente = {w['equivalent_MPa']:.6f} MPa; índice = {w['index']:.6f}.")
        d.add_paragraph(f"Parcelas de tau [MPa]: Vx {v['Vx']:.6f}; Vy {v['Vy']:.6f}; empenamento {v['warping']:.6f}; Saint-Venant {v['Saint_Venant']:.6f}. Sinal na face com normal n = (−dy,dx)/comprimento: tauSV = −face·Tsv·t/J.")
    d.add_paragraph('Os ramos de seção efetiva não implementados continuam pendentes. O critério de tensões §6.1.6 não substitui a resistência/flambagem por cisalhamento §6.1.5 nem interação N–M–V §6.1.10. A estabilidade global, efeitos de segunda ordem, aplicabilidade dos giros e verificações locais/ligações não foram liberados por este complemento.')
