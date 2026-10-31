"""Explicit combination previews; never combine independent q/P maxima."""
import copy
from .batch import area_bundle

def drawing_cases(data):
    if data.get('load_mode')!='area':
        return [('Entradas diretas ELU',copy.deepcopy(data))]
    combinations=area_bundle(data)['combinations']
    # Put P first so its presence is discoverable, not hidden behind max-|q|.
    combinations=sorted(combinations,key=lambda c:(not bool(c.get('P_N',0)),c['id']))
    previews=[]
    for c in combinations:
        d=copy.deepcopy(data)
        d.update(q_uls=c['q_N_mm'],P_uls=c.get('P_N',0.),x_uls=data['L_mm']/2)
        label=f"{c['id']} — {c['type']} — q={c['q_N_mm']:.2f} kN/m; P={c.get('P_N',0)/1000:.2f} kN"
        previews.append((label,d))
    return previews
