"""Reviewed approximate elastic Mdist, followed only by the NBR strength curve.

This is an exact-scope certificate for one own nominal Ue contour/material, not
a general section solver. The AISI general elastic formula includes 90-degree
lips. Its preliminary commentary formula and AISI resistance factors are not
used. Saved evidence is replayed arithmetically without reopening sources.
"""
import copy
import math

from . import ue_catalog_reference as own

SCHEMA = 'ue_catalog_nbr_distortional_v1'
SOURCE = ('Mdist aproximado: ANSI/SDI/AISI S100-2024 Apêndice 2, método geral; '
          'adoção por NBR 14762:2010 §9.3; resistência exclusivamente §9.8.2.3.')
SHORT_MEMBER_REASON = (
    'Mdist aproximado não qualificado para vão físico menor que Lcrd=377,736435 mm. '
    'Esta qualificação usa Ld=Lcrd irrestrito; a escolha não é extrapolada ao membro curto. '
    'Ml local permanece disponível. Ly/Lz não definem contenção distorcional e não foram usados.')
SOURCE_DOCUMENTS = [
    dict(title='ABNT NBR 14762:2010', clauses=['9.3', '9.8.2.3', '4.6'],
         role='Admissão de formulação aproximada correlacionada, curva resistente e limites do modelo.'),
    dict(title='ANSI/SDI/AISI S100-2024 and Commentary',
         url='https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf',
         sha256='6ec32742f056d08a0823557d9ce58b69d84312e64a6e656b8ba4b3b10cf4b4ca',
         pages_PDF_one_based=[217, 218, 219, 220],
         clauses=['Table 2.3.3-1', '2.3.3.1-3', '2.3.3.2-1/2/4/5/6/7'],
         role='Somente formulação elástica geral atual e propriedades mesa-enrijecedor.'),
    dict(title='Glauz (2018), Distortional Buckling of Cold-Formed Steel Flanges Under Stress Gradient',
         url='https://scholarsmine.mst.edu/isccss/24iccfss/session1/3/',
         sha256='8d930e71fbc9255b4f29d12565a0d8f74d2143e524a01e82d2fa5d995b80bead',
         pages_printed=[49, 51, 52],
         role='Tabela 4, conjunto 4: correlação da formulação atual em 60 canais; não garante piso.'),
    dict(title='AISI RP07-2 (2007), worked example 600S162-54',
         url='https://www.cfsei.org/assets/docs/research_report/RP07-2.pdf',
         sha256='9298d4efe7cbf93ae51e55cee95a2842cb06f8a6ab3fd73e257412224c9e3917',
         pages_PDF_one_based=[111, 112, 113, 114],
         role='Benchmark externo histórico; os termos atualizados de 2024 são documentados separadamente.'),
    dict(title='Errata to AISI S100-07 (2009)',
         url='https://buildusingsteel.org/wp-content/uploads/2020/12/CFSD-Pub-Errata-to-S100-v1-Amended-6-4-09-High-FINAL.pdf',
         role='Corrige definições históricas de hx/xo/yo; a notação atual de 2024 rege o cálculo.'),
]


def _elastic():
    """General equations evaluated only for the reviewed nominal geometry.

    Table 2.3.3-1: b=bf-t and d=D-t/2 are sharp midline dimensions,
    NOT the straight flats between rounded corners. Its t^3 contribution to
    Ixf is retained. Substructure axes pass through the flange-lip centroid,
    x toward the lip and y downward. They are not the global section axes.
    """
    from .ue_catalog_nbr_bending import GEOMETRY, MATERIAL, FORMULA_NU
    p = GEOMETRY
    E, G, nu = MATERIAL['E_MPa'], MATERIAL['G_MPa'], FORMULA_NU
    ho, t, b, d = float(p['h']), float(p['t']), p['bf']-p['t'], p['lip']-p['t']/2.
    A = (b+d)*t
    J = (b+d)*t**3/3.
    Ix = t*(t*t*b*b+4*b*d**3+t*t*b*d+d**4)/(12*(b+d))
    Iy = t*(b**4+4*d*b**3)/(12*(b+d))
    Ixy = t*b*b*d*d/(4*(b+d))
    Cw, xo, xh, yo = 0., b*b/(2*(b+d)), -(b*b+2*d*b)/(2*(b+d)), -d*d/(2*(b+d))
    H = Cw+Ix*(xo-xh)**2*(1-Ixy*Ixy/(Ix*Iy))
    # Eq. 2.3.3.2-2; unrestricted half-wave, no roof/screw spring credit.
    Lcr = math.pi*ho*(4*(1-nu*nu)*H/(t**3*ho**3)+1/720)**.25
    q, u = math.pi/Lcr, math.pi/Lcr*ho
    # Eq. 2.3.3.1-3, then 2.3.3.2-5/6/7, with pure strong-axis xi_web=2.
    kfe = q**4*E*H+q*q*G*J
    kwe = E*t**3/(12*(1-nu*nu))*(3/ho)*(1+2*u*u/15+u**4/720)
    kfg = q*q*(Ix+Iy+A*(xh*xh+yo*yo-2*yo*(xo-xh)*Ixy/Iy))
    kwg = q*q*(t*ho**3/240)*(300+8*u*u+u**4)/(420+28*u*u+u**4)
    Fcrd = (kfe+kwe)/(kfg+kwg)
    Sfc = p['Ix_cm4']*1e4/(ho/2.)
    return dict(Mdist_Nmm=Sfc*Fcrd, Fcrd_MPa=Fcrd, Lcrd_mm=Lcr, Ld_mm=Lcr,
        k_phi_fe_N=kfe, k_phi_we_N=kwe, k_phi_fg_mm2=kfg, k_phi_wg_mm2=kwg,
        ho_mm=ho, t_mm=t, Sfc_mm3=Sfc, exterior_fibre_distance_mm=ho/2.,
        global_Ix_mm4=p['Ix_cm4']*1e4, global_inner_radius_mm=p['ri_mm'],
        Sfc_basis='Ix do contorno arredondado / (h externo / 2), na junção mesa-alma comprimida.',
        flange_lip=dict(b_mm=b, d_mm=d, t_mm=t, Af_mm2=A, Jf_mm4=J,
            Ixf_mm4=Ix, Iyf_mm4=Iy, Ixyf_mm4=Ixy, Cwf_mm6=Cw,
            xof_mm=xo, xhf_mm=xh, yof_mm=yo, yhf_mm=yo,
            lip_angle_degrees=90., corner_radius_included=False,
            geometry_basis='Tabela 2.3.3-1, coluna esquerda; linhas médias sem raio, não larguras planas.',
            axes='Origem no CG mesa-enrijecedor; x para o lábio; y para baixo.'),
        E_MPa=E, G_MPa=G, formula_nu=nu,
        formula_nu_origin='Parâmetro explícito da fórmula; não inferido do G arredondado.',
        beta=1., xi_web=2., k_phi_N=0., Lm_mm=None,
        length_policy='Ld=Lcrd irrestrito; sem crédito de vão finito, contenção intermediária ou telha.',
        moment_gradient_credit_used=False, panel_restraint_credit_used=False,
        ho_over_Ld=ho/Lcr, preliminary_commentary_formula_used=False)


def _certificate(binding):
    from .ue_catalog_nbr_bending import PIN, MATERIAL, GAMMA
    if binding != dict(PIN, material=MATERIAL):
        raise ValueError('Mdist aproximado fora do contorno/material explicitamente qualificado.')
    elastic = _elastic()
    W, fy, md = elastic['Sfc_mm3'], MATERIAL['fy_MPa'], elastic['Mdist_Nmm']
    lam = math.sqrt(W*fy/md)
    rho = 1. if lam <= .673 else (1.-.22/lam)/lam
    out = dict(schema=SCHEMA, status='computed_approximate', source=SOURCE,
        source_documents=copy.deepcopy(SOURCE_DOCUMENTS), source_binding=copy.deepcopy(binding),
        elastic=elastic,
        resistance=dict(method='NBR14762:2010 §9.8.2.3', W_mm3=W, fy_MPa=fy,
            lambda_dist=lam, rho_dist=rho, gamma=GAMMA,
            MRd_dist_Nmm=rho*W*fy/GAMMA, branch='gross' if lam <= .673 else 'distortional_reduction',
            AISI_strength_factors_used=False),
        correlation=dict(
            family=dict(source='Glauz2018 Table4 equation set4', channel_count=60,
                prediction_to_FSM_mean=.966, prediction_to_FSM_standard_deviation=.096),
            same_contour=dict(receipt='qa/UE125_DISTORTIONAL_CORRELATION_20261106.json',
                receipt_sha256='d7f44c8bb37569511b264f8e7d03faa699b2e62e21f44e145e309c9e658eafbf',
                nodes_source_sha256=PIN['nodes_sha256'], lengths_mm=[300., elastic['Lcrd_mm'], 480.],
                flat_subdivisions=[4, 12], finite_strip_solves=6,
                E_MPa=200000., nu=.3, implied_G_MPa=200000./2.6,
                central_refined_FSM_Mcr_Nmm=15453308.232180087,
                analytical_matching_G_Mcr_Nmm=13998367.014889456,
                analytic_to_central_refined_FSM=.9058492074686733,
                central_mesh_relative_change=15469726.934271307/15453308.232180087-1.,
                finite_strip_mode='Primeiro modo compatível com distorção por inspeção e ajuste mesa-lábio.',
                pure_mode_classification_complete=False, continuous_minimum_proven=False),
            scope='Correlação de família publicada e contraste limitado do próprio contorno; não é autovalor exato nem piso garantido.'),
        assumptions=dict(model='Seção nominal ideal sem furos; uma alma e mesas enrijecidas para o mesmo lado.',
            reference_stress='Flexão forte pura simétrica; sinais positivo e negativo equivalentes.',
            kinematics='Estabilidade elástica linear e pequenos giros.',
            minimum_member_length_mm=elastic['Lcrd_mm'],
            member_length_basis='L_mm físico declarado deve ser >= Lcrd; Ly/Lz não substituem esse dado.',
            physical_holes_verified=False, physical_restraints_verified=False,
            physical_small_rotation_applicability_verified=False),
        elastic_approximation=True, exact_modal_eigenvalue=False, guaranteed_lower_bound=False,
        signs=['positive', 'negative'], weak_axis_qualified=False,
        biaxial_qualified=False, primary_torsion_assessed=False, whole_member_approved=False)
    out['snapshot_sha256'] = own.digest(out)
    return out


def supports_member_length(data):
    """Scope guard only, not a fabricated distortional restraint or new span."""
    length = data.get('L_mm')
    if (isinstance(length, bool) or not isinstance(length, (int, float))
            or not math.isfinite(length) or length <= 0):
        raise ValueError('Vão físico positivo e finito necessário para qualificar Mdist aproximado.')
    return length >= _elastic()['Lcrd_mm']


def qualify(data):
    """Fresh exact-scope qualification; never mutates model or project inputs."""
    from .ue_catalog_nbr_bending import PIN, MATERIAL, _saved_binding
    if not own.claims_reference(data):
        return None
    binding = own.source_binding(data)
    if any(binding.get(k) != v for k, v in PIN.items()) or binding.get('material') != MATERIAL:
        return None
    if binding != _saved_binding(data):
        raise ValueError('Fonte e marcador do Mdist aproximado divergentes.')
    if not supports_member_length(data):
        return None
    return _certificate(binding)


def validate_saved(evidence, data):
    from .ue_catalog_nbr_bending import _saved_binding
    binding = _saved_binding(data)
    if (not supports_member_length(data) or not isinstance(evidence, dict)
            or evidence != _certificate(binding)):
        raise ValueError('Evidência Mdist aproximado alterada ou incompatível; recalcule explicitamente.')
    return copy.deepcopy(evidence)
