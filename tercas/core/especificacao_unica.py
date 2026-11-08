"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math,copy
from .selecao import evaluate as section_evaluate
from .travamentos_nbr import evaluate_segment
from .protocolo_ief import model,peak

def qualified_scalar(x):
 return isinstance(x,dict) and isinstance(x.get('value'),(int,float)) and not isinstance(x['value'],bool) and math.isfinite(x['value']) and x['value']>0 and isinstance(x.get('origin'),str) and bool(x['origin'].strip())

def evaluate(spec):
 selected=copy.deepcopy(spec['selected_section']);f=selected['fields'];value=lambda k:f[k]['value']
 out={'schema':'NBR14762_one_span_v1','input_snapshot':copy.deepcopy(spec),'whole_member_approved':False,'sheet_restraint_credit':False,'issues':[]}
 try:
  out['section_checks']=section_evaluate(selected,L=spec.get('L_mm'))
  # This section-only diagnostic has no separate restraint/load contract.
  # Do not report the supplied span as missing or confuse it with the member route.
  for key in ('elastic_Me','local_FLT_resistance'):
   if key in out['section_checks']:
    out['section_checks'][key]['scope']='Diagnóstico auxiliar de seção; não é a verificação de FLT da barra. Consultar FLT_segments para o resultado por trecho e os comprimentos efetivos informados.'
    out['section_checks'][key]['member_verification_path']='FLT_segments'
 except (ValueError,TypeError,KeyError) as e:out['section_checks']={'status':'invalid_inputs','reason':str(e)}
 L=spec.get('L_mm');uls=spec.get('ULS');sls=spec.get('SLS');critical=spec.get('Ml')
 fields=['E_MPa','G_MPa','Iy_cm4','J_mm4','Cw_mm6','Wx_cm3','fy_MPa']
 missing=[k for k in fields if value(k) is None]
 if not qualified_scalar(critical):missing.append('Ml with positive value and origin')
 segments=[]
 for seg in spec.get('segments',[]):
  if missing:segments.append({'segment':seg,'status':'not_evaluated','missing':missing});continue
  try:
   sec={'route_domain':spec.get('route_domain'),'E':value('E_MPa'),'G':value('G_MPa'),'Iy':value('Iy_cm4')*1e4,'J':value('J_mm4'),'Cw':value('Cw_mm6'),'W':value('Wx_cm3')*1e3,'fy':value('fy_MPa'),'Ml':critical['value']}
   if not isinstance(uls,dict) or not isinstance(uls.get('origin'),str) or not uls['origin'].strip():raise ValueError('ULS action provenance missing')
   r=evaluate_segment(sec,dict(L=L,q=uls['q_Nmm'],P=uls['P_N'],a=uls['x_mm']),seg)
   if spec.get('roof_top_load'):
    r['reason']='Esquema de carga no topo selecionado: o Me elástico com altura aparece na componente própria de cobertura. A resistência conjunta de flexão e torção ainda não foi liberada; a expressão antiga no CT não é usada para representar esta carga.'
   r['section_property_convention_pending']=selected['source_geometry_convention_unresolved'];segments.append(r)
  except (ValueError,TypeError,KeyError) as e:segments.append({'status':'invalid_inputs','reason':str(e),'segment':seg})
 out['FLT_segments']=segments
 # Service-only critical must never change the shared ELU/FLT denominator.
 if 'Ml_SLS' in spec:
  from ..own_service_critical import for_spec
  critical=for_spec(spec)
 miss=[k for k in ['E_MPa','Ix_cm4'] if value(k) is None]
 if not qualified_scalar(critical) and 'MLE_SLS' not in spec:miss.append('Ml with origin')
 if not isinstance(sls,dict) or not isinstance(sls.get('origin'),str) or not sls['origin'].strip():miss.append('SLS actions with origin')
 if miss:out['ELS']={'status':'not_evaluated','missing':miss}
 else:
  try:
   if 'MLE_SLS' in spec:
    from ..own_service_mle import evaluate as evaluate_service_mle
    out['ELS']=evaluate_service_mle(spec)
   else:
    signed=None
    if 'Ml_SLS' in spec and sls['q_Nmm']*sls['P_N']<0:
     from ..nbr_service_strong_mse_signed import peak_deflection as signed_peak
     signed=signed_peak(L_mm=L,E_MPa=value('E_MPa'),Ig_mm4=value('Ix_cm4')*1e4,Ml_Nmm=critical['value'],q_Nmm=sls['q_Nmm'],P_N=sls['P_N'],a_mm=sls['x_mm'])
     z,d=signed['peak_x_mm'],signed['deflection_mm']
    else:
     args=model(L,value('E_MPa'),value('Ix_cm4')*1e4,critical['value'],sls['q_Nmm'],sls['P_N'],sls['x_mm']);z,d=peak(args)
    out['ELS']={'status':'computed_bending_component','x_mm':z,'deflection_mm':d,'same_span_mm':L,'model':'Euler-Bernoulli bending with sectionwise Ief(M), explicitly clamped to Ig for rounded transition','section_property_convention_pending':selected['source_geometry_convention_unresolved'],'criterion_scope':'bending component only, not complete system ELS approval'}
    if signed is not None:out['ELS']['service_mse_signed_evidence']=signed
   d=out['ELS']['deflection_mm']
   limit=spec.get('ELS_limit_mm')
   if qualified_scalar(limit):out['ELS'].update(limit_mm=limit['value'],limit_origin=limit['origin'],index=abs(d)/limit['value'],criterion_status='meets' if abs(d)<=limit['value'] else 'fails')
   else:out['ELS'].update(criterion_status='not_evaluated',missing=['applicable ELS limit with source'])
  except (ValueError,TypeError,KeyError,ArithmeticError) as e:out['ELS']={'status':'invalid_or_outside_implemented_domain','reason':str(e)}
 if 'MLE_SLS' in spec:out['ELS']['service_mle_input_evidence']=copy.deepcopy(spec['MLE_SLS'])
 if 'Ml_SLS' in spec:out['ELS']['local_critical_evidence']=copy.deepcopy(spec['Ml_SLS']['evidence'])
 from .ramos_genericos import calculate
 out['NBR_branches']=calculate(spec,out)
 out['remaining_checks']=['actual catalogue property convention/critical source, restraints and connection design remain as declared inputs; partial branches are explicit']
 return out
