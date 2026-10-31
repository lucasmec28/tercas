"""Portuguese presentation of restraints; no catalogue or load generation."""
import copy
CB_LABELS={'one':'Adotar Cb = 1,0','quarter_formula':'Calcular pelos momentos do trecho'}
CB_CODES={v:k for k,v in CB_LABELS.items()}

def cb_code(value):
 if value in CB_LABELS:return value
 if value in CB_CODES:return CB_CODES[value]
 raise ValueError('Selecione uma opção de Cb válida.')

def flange_segments(segments):
 result=[]
 for source in segments:
  s=copy.deepcopy(source)
  old=s.pop('Ly_effective_mm',None)
  s.setdefault('Ly_top_effective_mm',old)
  s.setdefault('Ly_bottom_effective_mm',old)
  s['Cb_mode']=cb_code(s.get('Cb_mode','one'))
  result.append(s)
 return result

def whole_span(L,upper,lower,torsion,cb='one',origin='Comprimentos efetivos informados; sem crédito de travamento da telha'):
 return [dict(start_mm=0.,end_mm=L,Ly_top_effective_mm=upper,Ly_bottom_effective_mm=lower,Lz_effective_mm=torsion,Cb_mode=cb_code(cb),restraint_provenance=origin)]
