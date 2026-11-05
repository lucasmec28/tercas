"""Portuguese display labels; stable machine identifiers remain in the JSON."""
STATES={'meets':'Atendido','fails':'Não atendido','pending':'Pendente','not_applicable':'Não aplicável'}
MEMBERS={'upper':'superior','middle':'central','lower':'inferior'}
CRITERIA={'normal':'Tensão normal EN','shear':'Cisalhamento EN','interaction':'Interação de tensões EN'}
LABELS={
 'saved_demand_integrity':'Integridade da demanda salva',
 'saved_linear_demand':'Demanda linear e cobertura salvas',
 'declared_model_domain':'Domínio do modelo declarado',
 'member_stability_and_analysis':'Estabilidade e aplicabilidade da análise ELU/ELS',
 'transverse_shear_resistance':'Resistência e flambagem por cortante transversal',
 'N_M_V_shear_reduction':'Redução por cortante na interação N–M–V',
 'support_force_introduction':'Introdução local das reações de apoio no perfil',
 'interior_force_introduction':'Introdução local das forças interiores no perfil',
 'tensile_section_scope':'Resistência da seção à tração',
 'EN:section_stresses':'Verificações seccionais EN não disponíveis',
 'EN:inventory':'Integridade do inventário EN',
 'ELS:horizontal_model':'Comparação horizontal de serviço não disponível',
 'ELS:horizontal_reader':'Integridade da componente horizontal de serviço',
 'applicability_reader':'Integridade dos critérios de aplicabilidade'}


def label(record):
    key=record['id'];parts=key.split(':')
    if key in LABELS:return LABELS[key]
    if len(parts)==3 and parts[0]=='EN' and parts[1] in MEMBERS and parts[2] in CRITERIA:
        return CRITERIA[parts[2]]+' da travessa '+MEMBERS[parts[1]]
    if len(parts)==4 and parts[0]=='ELS' and parts[2] in MEMBERS:
        return 'Flecha horizontal da travessa '+MEMBERS[parts[2]]+' | '+parts[1]
    if len(parts)==2 and parts[0]=='missing_limit_state':return 'Cobertura de combinações '+parts[1]
    return 'Critério '+key
