"""Current-input 7DOF supplement, separate from the legacy NBR/6DOF routes.

The source own-Ue snapshot supplies geometry/material/actions, NOT its isolated
member certification. The separate configuration explicitly selects 3D topology,
point coupling and warping boundary conditions. No result is silently migrated.
"""
import copy
import hashlib
import json
import math
import numpy as np
from scipy.optimize import brentq
from . import network
from .element import point_map, DOFS
from ..three_girt_frame import topology
from ..three_girt_application import defaults as old_defaults, configuration, readiness, load_cases
from ..torsion_vlasov.section import finite, verify_section

SCHEMA='three_girt_current_vlasov_demand_v1'
ORIENTATION='mouth_down_Y_minus_x_Z_minus_y'
LEVELS=('upper','middle','lower')
FIELDS=('N_N','My_strong_Nmm','Mz_weak_Nmm','B_equilibrium_Nmm2','T_equilibrium_SC_Nmm','T_equilibrium_CG_Nmm')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def defaults():
    return dict(enabled=False,three_girt=old_defaults(),section_orientation=ORIENTATION,
        warping_end_condition='free_assumed',warping_condition_origin='Hipótese explícita editável do complemento: empenamento livre nos seis garfos; nenhuma restrição adicional declarada, sem comprovação física.',connections={})


def material_point(section,segment_index,parameter,origin):
    """Explicit point on the CURRENT faceted midsurface, no nearest-point search."""
    verify_section(section)
    if type(segment_index) is not int or not 0<=segment_index<len(section['nodes_xy_mm'])-1:
        raise ValueError('Current section segment_index outside contour')
    t=finite(parameter,'point parameter')
    if not 0<=t<=1:raise ValueError('Point parameter must be in [0,1]')
    if not isinstance(origin,str) or not origin.strip():raise ValueError('Physical point/idealization origin required')
    p=np.asarray(section['nodes_xy_mm']);omega=section['omega_nodes_mm2'];cg=np.asarray(section['properties']['centroid_xy_mm'])
    xy=p[segment_index]*(1-t)+p[segment_index+1]*t-cg
    return dict(model='material_point',segment_index=segment_index,parameter=t,
        arm_mm=[0.,-float(xy[0]),-float(xy[1])],omega_mm2=float(omega[segment_index]*(1-t)+omega[segment_index+1]*t),
        sectorial_section_id=section['content_sha256'],origin=origin)


def resultant_point(arm_mm,origin):
    """Explicit idealized resultant, not an evaluation of omega at the centroid."""
    if not isinstance(arm_mm,(list,tuple)) or len(arm_mm)!=3:raise ValueError('Three explicit resultant arm components required')
    if not isinstance(origin,str) or not origin.strip():raise ValueError('Resultant idealization origin required')
    arm=[finite(v,'resultant arm') for v in arm_mm]
    if arm[0]!=0:raise ValueError('Current adapter supports section-plane points only; no longitudinal rigid bracket')
    return dict(model='declared_resultant',arm_mm=arm,omega_mm2=0.,
        zero_bimoment_transmission_declared=True,origin=origin)


def frame_section(data,section):
    verify_section(section);p=data['properties'];s=section['properties']
    for key,val in [('A_mm2',p['A_cm2']*100),('Ix_strong_mm4',p['Ix_cm4']*1e4),
                    ('Iy_weak_mm4',p['Iy_cm4']*1e4),('J_mm4',p['J_mm4']),('Cw_mm6',p['Cw_mm6'])]:
        if not math.isclose(s[key],finite(val,key,True),rel_tol=2e-12,abs_tol=1e-9):
            raise ValueError('Current input and coherent contour differ: '+key)
    cg=np.asarray(s['centroid_xy_mm']);sc=np.asarray(s['shear_center_xy_mm'])
    return dict(A_mm2=s['A_mm2'],I_strong_mm4=s['Ix_strong_mm4'],I_weak_mm4=s['Iy_weak_mm4'],
        J_mm4=s['J_mm4'],Cw_mm6=s['Cw_mm6'],E_MPa=finite(p['E_MPa'],'E',True),G_MPa=finite(p['G_MPa'],'G',True),
        sc_y_mm=-float(sc[0]-cg[0]),sc_z_mm=-float(sc[1]-cg[1]),sectorial_section_id=section['content_sha256'],
        origin='Current coherent R01 source '+section['profile_id']+'; explicit mouth-down coordinate rotation')



def current_configuration(data,three_girt=None):
    """Make an explicit, saved proposal from current arms, without solving it.

    Existing points on the coherent wall receive their interpolated omega.
    Other arms become an explicit zero-bimoment resultant idealization. This
    never treats the geometric centroid as a material point with omega=0.
    """
    from ..torsion_study import section_for
    section=section_for(data);s=frame_section(data,section);cfg=defaults();cfg['enabled']=True
    raw=copy.deepcopy(three_girt if three_girt is not None else data.get('three_girt_model',old_defaults()))
    raw['enabled']=True
    for k in ('sc_y_mm','sc_z_mm'):
        if raw.get(k) is None:raw[k]=s[k]
    if not raw.get('sc_origin'):raw['sc_origin']=s['origin']
    adapted=copy.deepcopy(data);adapted['three_girt_model']=raw;c=configuration(adapted)
    nodes=np.asarray(section['nodes_xy_mm']);cg=np.asarray(section['properties']['centroid_xy_mm'])
    out={}
    for name,arms in c['resolved_offsets'].items():
        out[name]=[]
        for arm in arms:
            if arm[0]!=0:raise ValueError('Current longitudinal rigid-bracket arm unsupported')
            xy=cg+np.array([-arm[1],-arm[2]]);match=None
            for i,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
                d=b-a;t=float((xy-a)@d/(d@d))
                if -1e-12<=t<=1+1e-12 and np.linalg.norm(a+min(1.,max(0.,t))*d-xy)<=1e-9:
                    match=material_point(section,i,min(1.,max(0.,t)),'Ponto informado da ligação atual, localizado no contorno próprio; origem: '+raw.get('origin',''))
                    break
            out[name].append(match if match is not None else resultant_point(arm,
                'Idealização explícita editável: resultante no braço atual com Qpsi=0; não é omega no CG nem ponto material inferido. Origem: '+raw.get('origin','')))
    cfg.update(three_girt=raw,connections=out)
    return cfg


def _connections(raw,section,legacy):
    links=topology(legacy['tie_count'])
    if not isinstance(raw,dict) or set(raw)!={r[0] for r in links}:
        raise ValueError('Every current bar requires two explicit sectorial connection records')
    out={}
    for name,_,_,_ in links:
        ends=raw[name]
        if not isinstance(ends,(list,tuple)) or len(ends)!=2:raise ValueError(name+': two connection ends required')
        out[name]=[]
        for i,c in enumerate(ends):
            if not isinstance(c,dict):raise ValueError('Connection must be an object')
            if c.get('model')=='material_point':
                expected=material_point(section,c.get('segment_index'),c.get('parameter'),c.get('origin'))
            elif c.get('model')=='declared_resultant':
                expected=resultant_point(c.get('arm_mm'),c.get('origin'))
                if c.get('zero_bimoment_transmission_declared') is not True:raise ValueError('Zero bimoment transmission must be explicitly declared')
            else:raise ValueError('Connection needs material_point or declared_resultant')
            if c!=expected:raise ValueError(name+': point coordinates/omega/identity do not match current contour or resultant declaration')
            if not np.allclose(c['arm_mm'],legacy['resolved_offsets'][name][i],rtol=0,atol=1e-10):
                raise ValueError(name+': physical point differs from declared legacy connection arm')
            out[name].append(copy.deepcopy(c))
    return out


def _model(inp):
    xs=[0.]+inp['attachment_x_mm']+[inp['L_mm']];columns=len(xs)
    nodes=[dict(id=i*columns+j,xyz_CG_mm=[x,y,0.]) for i,y in enumerate((inp['upper_gap_mm'],0.,-inp['lower_gap_mm'])) for j,x in enumerate(xs)]
    bars=[dict(id=name,a=a,b=b,connections=inp['connections'][name],material=inp[color]) for name,a,b,color in topology(len(xs)-2)]
    return dict(inputs=inp,mesh_columns=columns,nodes=nodes,bars=bars)


def _critical(run,beam):
    """All extrema of N/M/B/T per interval, not a combined stress envelope."""
    a=beam['x_start_mm'];b=beam['x_end_mm'];s0=network.response(run,beam,a);s1=network.response(run,beam,b)
    xs={a,b,(a+b)/2}
    for key in ('Vy_N','Vz_N','T_w_Nmm'):
        y0=s0[key];y1=s1[key]
        if y0*y1<0:
            xs.add(float(brentq(lambda x:network.response(run,beam,x)[key],a,b,xtol=1e-9,rtol=1e-14)))
    states=[]
    for x in sorted(xs):
        state=dict(network.response(run,beam,x),element=beam['id'],side='right' if x==a else 'left' if x==b else 'interior')
        state['R01_concomitant_mapping']=dict(N_N=state['N_N'],Mx_physical_Nmm=-state['My_strong_Nmm'],
            My_physical_Nmm=-state['Mz_weak_Nmm'],B_Nmm2=state['B_equilibrium_Nmm2'],
            rule='Y=-x_R01; Z=-y_R01; omega unchanged; Mx_R01=-My_frame, My_R01=-Mz_frame, B_R01=B_frame')
        states.append(state)
    return states


def diagnostics(run):
    L=run['inputs']['L_mm'];f=run['f'];r=run['reactions'];u=run['u'];xyz=run['xyz'];columns=run['columns'];nd=len(u)
    Fscale=max(1.,float(np.sum(abs(f.reshape(-1,7)[:,:3]))));scales=np.tile([Fscale]*3+[Fscale*L]*3+[Fscale*L*L],len(xyz))
    equiv=(f+r).reshape(-1,7);globalF=np.sum(equiv[:,:3],axis=0);globalM=np.sum(equiv[:,3:6]+np.cross(xyz,equiv[:,:3]),axis=0)
    point=run['physical_nodal'].copy()+r;maxwork=0.;maxaction=0.;rng=np.random.default_rng(71104)
    for bar in run['bars']:
        for end,node in enumerate((bar['a'],bar['b'])):
            c=bar['connections'][end];arm=np.array(c['arm_mm']);F=(1. if end==0 else -1.)*bar['force_N']*bar['direction']
            action=np.r_[F,np.cross(arm,F),-F[0]*c['omega_mm2']]
            maxaction=max(maxaction,float(np.max(abs(action-bar['physical_girt_actions'][end]))/max(1.,np.max(abs(action)))))
            point[7*node:7*node+7]+=action
            for _ in range(3):
                du=rng.normal(size=7)*[1,1,1,.001,.001,.001,.000001]
                dp=du[:3]+np.cross(du[3:6],arm)+[-c['omega_mm2']*du[6],0,0]
                maxwork=max(maxwork,abs(float(F@dp-action@du))/max(1.,abs(float(F@dp))))
    bodymax=0.;bjump=np.zeros(nd);recovery=0.;ode=0.
    for beam in run['beams']:
        end=beam['k']@u[beam['ids']]-beam['f'];bjump[beam['ids']]+=end
        row=LEVELS.index(beam['girt']);load=beam['load'];q=np.array([0.,load['q_y_N_mm'],load['q_z_N_mm']]);mcg=load['distributed_torque_CG_N']
        for t in (0.,.37,1.):
            x=beam['x_start_mm']+beam['length_mm']*t;s=network.response(run,beam,x)
            F=q*x;M=np.array([mcg*x,0.,0.])-x*x/2*np.cross([1.,0.,0.],q)
            for node in range(row*columns,(row+1)*columns):
                xn=xyz[node,0]
                if xn<x or (xn==x and t==0):
                    v=point[7*node:7*node+7];F+=v[:3];M+=v[3:6]+np.cross([xn-x,0.,0.],v[:3])
            expected=np.r_[-F,-M];actual=np.array([s['N_N'],-s['Vy_N'],-s['Vz_N'],s['T_equilibrium_CG_Nmm'],s['My_strong_Nmm'],s['Mz_weak_Nmm']])
            bodymax=max(bodymax,float(np.max(abs(expected-actual)/np.array([Fscale]*3+[Fscale*L]*3))))
            recovery=max(recovery,abs(s['B_constitutive_Nmm2']-s['B_equilibrium_Nmm2'])/(Fscale*L*L),abs(s['T_constitutive_SC_Nmm']-s['T_equilibrium_SC_Nmm'])/(Fscale*L))
            ode=max(ode,abs(s['torsion_ODE_residual'])/max(1.,abs(mcg)))
    berror=float(np.max(abs((bjump-point)[6::7]))/(Fscale*L*L))
    energy=network.continuum_energy(run)
    symmetry=float(abs(run['K']-run['K'].T).max())/max(1.,float(abs(run['K']).max()))
    checks=dict(global_force_N=globalF.tolist(),global_moment_Nmm=globalM.tolist(),
        maximum_free_residual_scaled=float(np.max(abs(r[run['free']])/scales[run['free']])),
        physical_left_free_body_max_scaled=bodymax,point_virtual_work_max_relative=maxwork,
        physical_point_action_max_relative=maxaction,bimoment_node_balance_scaled=berror,
        constitutive_equilibrium_BT_scaled=recovery,torsion_ODE_scaled=ode,
        fixed_displacement_max=float(np.max(abs(u[run['fixed']]))),stiffness_symmetry_relative=symmetry,energy=energy)
    checks['passed']=bool(np.isfinite(u).all() and max(np.max(abs(globalF))/Fscale,np.max(abs(globalM))/(Fscale*L),
        checks['maximum_free_residual_scaled'],bodymax,maxwork,maxaction,berror,recovery,ode,symmetry,energy['relative_error'])<1e-8)
    return checks


def _export(run,combination,source_fingerprint):
    for i,b in enumerate(run['beams']):b['id']=b['girt']+'_'+str(i%(run['columns']-1)+1)
    checks=diagnostics(run)
    if not checks['passed']:raise ArithmeticError('Current 7DOF solve failed physical/numerical checks')
    beams=[];envelopes={};g81=[]
    for b in run['beams']:
        states=_critical(run,b)
        sampled=[network.response(run,b,b['x_start_mm']+t*b['length_mm']) for t in (0.,.5,1.)]
        coefficients={}
        for key in ('N_N','My_strong_Nmm','Mz_weak_Nmm'):
            a0,am,a1=(a[key] for a in sampled);a2=2*(a1+a0-2*am)
            coefficients[key]=[float(a0)] if key=='N_N' else [float(a0),float(a1-a0-a2),float(a2)]
        sec=run['section'];load=b['load'];mSC=load['distributed_torque_CG_N']-sec['sc_y_mm']*load['q_z_N_mm']+sec['sc_z_mm']*load['q_y_N_mm']
        beams.append(dict(id=b['id'],girt=b['girt'],x_start_mm=b['x_start_mm'],x_end_mm=b['x_end_mm'],length_mm=b['length_mm'],states=states,
            normal_action_polynomials=dict(coordinate='t=(x_mm-x_start_mm)/length_mm in [0,1]; ascending coefficients',**coefficients),
            torsion_state_parameters=dict(L_mm=b['length_mm'],GJ_Nmm2=sec['G_MPa']*sec['J_mm4'],ECw_Nmm4=sec['E_MPa']*sec['Cw_mm6'],m_SC_N=mSC,
                nodal_phi_psi=run['u'][b['ids']][[3,6,10,13]].tolist(),convention='B=-ECw*phi_second; omega unchanged by declared proper rotation')))
    for level in LEVELS:
        states=[a for b in beams if b['girt']==level for a in b['states']]
        envelopes[level]={k:dict(min=min(states,key=lambda a:a[k]),max=max(states,key=lambda a:a[k]),max_abs=max(states,key=lambda a:abs(a[k]))) for k in FIELDS}
        bmax=envelopes[level]['B_equilibrium_Nmm2']['max_abs'];nmax=envelopes[level]['N_N']['max_abs']
        g81.append(dict(member=level,combination_id=combination['id'],limit_state=combination['limit_state'],
            Bsd_abs_Nmm2=abs(bmax['B_equilibrium_Nmm2']),concomitant_governing_state=bmax,
            max_abs_N_N=abs(nmax['N_N']),N_preserved=True,
            G81_demand_ready=True,H4_cannot_close_N_M_B=bool(abs(nmax['N_N'])>0.),
            resistance_qualified=False,whole_member_approved=False))
    record=dict(status='conditional_elastic_vlasov_demand',method='reused_exact_static_7DOF_Vlasov',
        source_input_fingerprint=source_fingerprint,dofs=len(run['u']),physical_force_stations_only=True,
        inputs=copy.deepcopy(run['inputs']),linear_matrix_diagnostic=run['linear_matrix_diagnostic'],nodes=[dict(id=i,xyz_CG_mm=xyz.tolist(),displacements=dict(zip(DOFS,run['u'][7*i:7*i+7].tolist())),support_reactions=run['reactions'][7*i:7*i+7].tolist()) for i,xyz in enumerate(run['xyz'])],
        fixed_dofs=[dict(node=int(i//7),dof=DOFS[i%7]) for i in run['fixed']],beams=beams,girt_envelopes=envelopes,G81_demand_inputs=g81,
        bars=[dict(id=b['id'],axial_tension_N=b['force_N'],axial_state='tension' if b['force_N']>0 else 'compression' if b['force_N']<0 else 'zero',
              resistance_checked=False,self_weight_N=b['self_weight_N'],connections=copy.deepcopy(b['connections'])) for b in run['bars']],diagnostics=checks,
        first_order=True,bilateral_bars=True,tie_strength_checked=False,physical_conditions_verified=False,
        resistance_qualified=False,ELS_qualified=False,whole_member_approved=False,
        extrema_scope='N/M/B/T component extrema, all concomitant fields and both sides retained; not a combined normal-stress or resistance envelope')
    record['demand_content_sha256']=fingerprint(record)
    return record


def calculate(data,config,*,verification_scope=None):
    """Run on current eligible own-Ue wall inputs and a SEPARATE explicit opt-in."""
    from ..torsion_study import section_for
    from ..support_scope import enabled as support_scope_enabled, annotate as annotate_support_scope
    support_scope_enabled(data)
    if not isinstance(config,dict) or set(config)!=set(defaults()):raise ValueError('Exact 3D warping configuration fields required')
    if config['enabled'] is not True:raise ValueError('3D warping supplement requires explicit opt-in')
    if data.get('member_application')!='wall_girt':raise ValueError('Explicit wall_girt application required')
    section=section_for(data);s=frame_section(data,section)
    snapshot=dict(data=copy.deepcopy(data),config=copy.deepcopy(config));digest=fingerprint(snapshot)
    out=dict(schema=SCHEMA,status='pending_model_data',input_fingerprint=digest,input_data=copy.deepcopy(data),
        configuration=copy.deepcopy(config),cases=[],missing=[],source_geometry=dict(profile_id=section['profile_id'],nodes_sha256=section['nodes_sha256'],content_sha256=section['content_sha256']),
        legacy_route_used=False,legacy_results_modified=False,source_isolated_resistance_approval_inherited=False,
        stress_axis_mapping='sigma=N/A-My_frame*y_R01/Istrong+Mz_frame*x_R01/Iweak+B_frame*omega_R01/Cw; Mx_R01=-My_frame, My_R01=-Mz_frame, B_R01=B_frame',
        physical_conditions_verified=False,resistance_qualified=False,ELS_qualified=False,whole_member_approved=False,
        limitations=['Demanda Vlasov elástica bruta de primeira ordem; barras bilaterais, sem resistência de tirantes ou ligações.',
        'Preserva N/M/B/T concomitantes. H4 isolado não encerra N+M+B quando N é diferente de zero.',
        'Sem contato, rigidez ou travamento da telha; sem 2D/casca, não linearidade ou novos críticos.',
        'G8.1 pode consumir o bimomento por combinação; não representa sozinho verificação global NBR, instabilidade ou ELS.',
        'Pontos de conexão e empenamento são declarações físicas/idealizações, não certificados.'])
    if verification_scope is not None:
        from ..three_girt_scope import SCHEMA as SCOPE_SCHEMA, record
        if verification_scope!=SCOPE_SCHEMA:raise ValueError('Unknown verification scope')
        out['verification_scope']=record(digest)
    annotate_support_scope(out)
    missing=out['missing']
    if config['section_orientation']!=ORIENTATION:missing.append('Declarar orientação boca para baixo: Y=-x_R01, Z=-y_R01, omega preservado.')
    if config['warping_end_condition'] not in ('free_assumed','restrained_assumed'):missing.append('Declarar empenamento livre ou impedido nos seis extremos; rx fixo não define psi.')
    if not isinstance(config['warping_condition_origin'],str) or not config['warping_condition_origin'].strip():missing.append('Informar origem da hipótese de empenamento.')
    raw=copy.deepcopy(config['three_girt']);raw['enabled']=True
    for key in ('sc_y_mm','sc_z_mm'):
        if raw.get(key) is not None and not math.isclose(raw[key],s[key],rel_tol=2e-12,abs_tol=1e-10):raise ValueError('Declared shear centre differs from coherent current contour: '+key)
        raw[key]=s[key]
    raw['sc_origin']=s['origin']
    adapted=copy.deepcopy(data);adapted['three_girt_model']=raw
    c=configuration(adapted);missing+=readiness(adapted,c)
    if not config['connections'] and topology(c['tie_count']):missing.append('Declarar os dois pontos materiais/omega ou resultantes sem bimomento de cada barra ativa.')
    if missing:return out
    connections=_connections(config['connections'],section,c)
    cases,bundle=load_cases(adapted,c)
    if any(any(abs(v)>0 for v in row['combination'].get('P_vector',{}).values()) for row in cases):raise ValueError('Concentrated current actions are unsupported, not discarded')
    spacing=finite(data['area_inputs']['spacing_m'],'girt spacing',True)*1000
    for row in cases:
        inp=dict(L_mm=finite(data['L_mm'],'L',True),upper_gap_mm=spacing,lower_gap_mm=spacing,
            attachment_x_mm=c['resolved_positions_mm'],section=copy.deepcopy(s),blue=c['blue'],green=c['green'],loads=row['loads'],
            connections=connections,warping_end_condition=config['warping_end_condition'],warping_condition_origin=config['warping_condition_origin'],
            include_green=True,brace_self_weight=c['brace_self_weight'],brace_weight_factor=row['brace_weight_factor'],nodal_loads=[])
        from ..load_application_policy import active as ct_active,FIELD as CT_FIELD,MODE as CT_MODE
        if ct_active(data):inp[CT_FIELD]=CT_MODE
        run=network.solve(_model(inp),'exact',1)
        result=_export(run,row['combination'],digest)
        out['cases'].append(dict(row,model=result))
    out.update(status='conditional_elastic_vlasov_demand',load_bundle=bundle,coverage_complete=True)
    if fingerprint(dict(data=data,config=config))!=digest:raise ArithmeticError('Input mutation during current-input calculation')
    return out


def attach_g81(result):
    """Evaluate the separate first-yield component, never reduced H4 with N."""
    from ..aisi_torsion_component import g81_capacity
    from ..torsion_study import section_for
    if result.get('schema')!=SCHEMA or result.get('status')!='conditional_elastic_vlasov_demand':
        raise ValueError('Fresh complete current 3D demand required for G8.1')
    if fingerprint(dict(data=result['input_data'],config=result['configuration']))!=result['input_fingerprint']:
        raise ValueError('Current 3D result/input/configuration fingerprint differs')
    section=section_for(result['input_data'])
    if section['content_sha256']!=result['source_geometry']['content_sha256']:raise ValueError('Demand/capacity contour differs')
    capacity=g81_capacity(section,result['input_data']['properties']['fy_MPa'])
    out=copy.deepcopy(result)
    for row in out['cases']:
        model=row['model'];saved=model.pop('demand_content_sha256')
        if fingerprint(model)!=saved:raise ValueError('Saved demand content changed; recalculate before G8.1')
        model['demand_content_sha256']=saved
        records=[]
        for state in model['G81_demand_inputs']:
            if state['limit_state']!='ELU':continue
            ratio=state['Bsd_abs_Nmm2']/capacity['Ba_Nmm2']
            records.append(dict(member=state['member'],combination_id=state['combination_id'],
                status='computed_conditional_component',ratio=ratio,component_condition=bool(ratio<=1.),
                B_Nmm2=state['concomitant_governing_state']['B_equilibrium_Nmm2'],
                x_mm=state['concomitant_governing_state']['x_mm'],side=state['concomitant_governing_state']['side'],
                concomitant_state=copy.deepcopy(state['concomitant_governing_state']),max_abs_N_N=state['max_abs_N_N'],
                N_preserved=True,H4_reduced_applied=False,N_M_B_interaction_complete=False,
                whole_member_approved=False))
        row['G81_component']=dict(capacity=copy.deepcopy(capacity),records=records,
            scope='AISI G8.1 first-yield bimoment component on current coherent contour; not N+M+B/global approval')
    out['G81_component_attached']=True
    return out


def recover_exported_state(model,beam,x_mm):
    """Evaluate N/M/V/B/T from saved expressions only; never solve the network.

    The caller may validate model.demand_content_sha256 once before a sequence
    of evaluations. Coefficients are exact interval fields, not interpolated
    component extrema. x must select one explicit beam, retaining node sides.
    """
    from .exact_torsion import state as torsion_state
    x=finite(x_mm,'saved section x');L=beam['length_mm'];t=(x-beam['x_start_mm'])/L
    if not -1e-12<=t<=1+1e-12:raise ValueError('Section outside selected saved interval')
    t=min(1.,max(0.,t));p=beam['normal_action_polynomials'];a=beam['torsion_state_parameters']
    def value(key,order=0):return float(np.polynomial.polynomial.polyval(t,np.polynomial.polynomial.polyder(p[key],order)))/L**order
    v=torsion_state(a['L_mm'],a['GJ_Nmm2'],a['ECw_Nmm4'],a['m_SC_N'],a['nodal_phi_psi'],t)
    Vy=value('Mz_weak_Nmm',1);Vz=-value('My_strong_Nmm',1);s=model['inputs']['section']
    out=dict(x_mm=x,girt=beam['girt'],element=beam['id'],side='right' if t==0 else 'left' if t==1 else 'interior',
        N_N=value('N_N'),My_strong_Nmm=value('My_strong_Nmm'),Mz_weak_Nmm=value('Mz_weak_Nmm'),Vy_N=Vy,Vz_N=Vz,
        B_equilibrium_Nmm2=v['B'],B_constitutive_Nmm2=v['B'],T_equilibrium_SC_Nmm=v['T'],T_constitutive_SC_Nmm=v['T'],
        T_equilibrium_CG_Nmm=v['T']+s['sc_z_mm']*Vy-s['sc_y_mm']*Vz,T_SV_Nmm=v['Tsv'],T_w_Nmm=v['Tw'],
        phi_rad=v['phi'],psi_per_mm=v['psi'],evaluation_source='saved exact interval expressions; no network recalculation')
    out['R01_concomitant_mapping']=dict(N_N=out['N_N'],Mx_physical_Nmm=-out['My_strong_Nmm'],My_physical_Nmm=-out['Mz_weak_Nmm'],B_Nmm2=out['B_equilibrium_Nmm2'])
    return out
