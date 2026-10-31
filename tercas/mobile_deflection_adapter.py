"""Qualify and present conservative bound only for existing isolated ELS model."""
from .mobile_deflection_bound import mobile_deflection_bound

def apply_bound(row,result,combo):
 d=result['input_data'];els=result.get('ELS',{});props=d.get('properties',{})
 # Presence of source does not certify it. The bound is of the declared model.
 missing=[]
 for key in ('critical_origin','property_origin','ELS_origin'):
  if not isinstance(d.get(key),str) or not d[key].strip():missing.append(key)
 if missing:return {'status':'not_evaluated','missing':missing}
 if els.get('status')!='computed_bending_component':return {'status':'not_evaluated','reason':'modelo ELS base indisponível ou fora do domínio'}
 try:
  if isinstance(props.get('Ix_cm4'),bool):raise ValueError('Ix: número positivo obrigatório')
  bound=mobile_deflection_bound(L_mm=d['L_mm'],E_N_mm2=props.get('E_MPa'),Ig_mm4=props.get('Ix_cm4')*1e4,Ml_Nmm=d.get('Ml_Nmm'),q_N_mm=combo['q_N_mm'],P_N=combo['P_N'],limit_mm=els.get('limit_mm'))
 except (TypeError,ValueError) as exc:return {'status':'not_evaluated','reason':str(exc)}
 bound['property_origin']=d['property_origin'];bound['critical_origin']=d['critical_origin']
 bound['section_property_convention_pending']=els.get('section_property_convention_pending',True)
 bound['scope']='Somente componente normal de flexão do modelo biapoiado informado; exclui deslocamento paralelo, torção e deformação dos vínculos.'
 idx=bound['upper_bound_ratio'];candidate=row.get('Índice') if row.get('Índice') is not None and row['Índice']>1 else result.get('ELS',{}).get('index')
 central_value=row.get('Demanda / valor','—')
 row['Observação']=row.get('Observação','').replace(' P avaliada no centro somente; valor exibido é candidato, não envelope móvel qualificado desta rota.',' Candidato central mantido na evidência; limite superior cobre a posição móvel da componente no domínio declarado.')
 row['Observação']+=' '+bound['scope']+' Limite superior conservador com Imin global; não é flecha exata. Origem e adequação física das propriedades mantêm as ressalvas do modelo.'
 row['Demanda / valor']=f"Limite superior |δ| ≤ {bound['bound_abs_mm']:.6f} mm"
 if idx is None:return bound
 if candidate is not None and candidate>1:
  row['Situação']='Não atende já no candidato central — envelope exato não concluído'
  row['Índice']=candidate
  row['Demanda / valor']=f'Candidato central: {central_value}; limite superior: {bound["bound_abs_mm"]:.6f} mm'
  row['Observação']+=' A reprovação provém da flecha central calculada, não do limite superior.'
 elif idx<=1:
  row['Situação']='Atende pelo limite superior conservador do modelo — componente isolada'
  row['Índice']=idx
  row['Observação']+=' Índice exibido é limite superior/limite ELS, não utilização exata.'
 else:
  row['Situação']='Inconclusivo — limite superior conservador excede'
  row['Índice']=None
  row['Observação']+=f' Razão limite superior/limite ELS={idx:.6f}; isso não prova reprovação física.'
 return bound
