"""Authenticate persisted finalists at their locations, never search maxima."""
import math
from . import shear_interaction as si


def verify_piece(piece,evaluate,fields,tw,torsion,limit):
    from . import application as engine
    from ..ue_catalog_reference import digest
    rows={(r['segment_index'],r['face']):r for r in fields}
    limits=dict(normal=limit,shear=limit/math.sqrt(3),interaction=1.1*limit)
    records=[('normal',piece['normal'])]+[(k,piece['shear_interaction'][k]) for k in limits]
    for key,record in records:
        engine._validate_saved_bound(record,True)
        w=record['witness']
        if w is None:continue
        t=w.get('t');u=w.get('u');i=w.get('segment_index');face=w.get('thickness_face_sign')
        if ((isinstance(t,bool) or not isinstance(t,(int,float))) or not math.isfinite(t) or not piece['left']<=t<=piece['right']
            or (isinstance(u,bool) or not isinstance(u,(int,float))) or not math.isfinite(u) or not 0<=u<=1
            or type(i) is not int or type(face) is not int or (i,face) not in rows
            or (key=='normal' and u not in (0.,1.))):
            raise ValueError('Invalid persisted physical witness location')
        row=rows[(i,face)];sigma,tau=si._evaluate(row,torsion,tw,t,u)
        candidate=dict(t=t,u=u,segment_index=i,thickness_face_sign=face,
            normal_xy=row['normal_xy'],xy_relative_to_gross_CG_mm=(row['xy_start']+u*row['xy_delta']).tolist(),
            sigma_MPa=sigma,tau_MPa=tau,equivalent_MPa=math.hypot(sigma,math.sqrt(3)*tau))
        actual=evaluate(candidate)
        if actual is None:raise ValueError('Persisted witness is not a physical signed-section point')
        # These fields are wholly reconstructed, never copied from the JSON.
        exact_fields=('t','u','segment_index','thickness_face_sign','normal_xy','xy_relative_to_gross_CG_mm',
            'sigma_MPa','tau_MPa','equivalent_MPa','sigma_error_MPa','tau_error_MPa','x_mm','combination_id','girt','segment_id','side',
            'concomitant_7DOF_state','normal_contributions_MPa','stress_contributions_MPa',
            'shear_contributions_MPa','normal_action_reference','selected_component_keys',
            'canonical_signed_actions_R01','canonical_action_signs','omega_mm2','normal_index',
            'normal_limit_MPa','section_fiber','section_fiber_index','witness_scope','witness_error_method')
        if any(digest(w.get(name))!=digest(actual[name]) for name in exact_fields):
            raise ValueError('Persisted witness differs from authenticated point recovery')
        errors=w.get('witness_error_MPa',{})
        if not isinstance(errors,dict) or set(errors)!={'sigma','tau'}:
            raise ValueError('Missing physical witness error guard')
        for name in ('sigma','tau'):
            value=errors[name]
            if (isinstance(value,bool) or not isinstance(value,(int,float))) or not math.isfinite(value) or value<actual['witness_error_MPa'][name]:
                raise ValueError('Persisted witness error below recovered point guard')
        value=abs(actual['sigma_MPa']) if key=='normal' else abs(actual['tau_MPa']) if key=='shear' else actual['equivalent_MPa']
        error=errors['sigma'] if key=='normal' else errors['tau'] if key=='shear' else math.hypot(errors['sigma'],math.sqrt(3)*errors['tau'])
        low=max(0.,math.nextafter((value-error)/limits[key],-math.inf))
        high=math.nextafter((value+error)/limits[key],math.inf)
        if (w.get('index')!=value/limits[key] or w.get('index_lower_witness')!=low
            or w.get('index_upper_witness')!=high or record['index_lower_witness']!=low
            or record['bound_gap']!=record['index_upper_bound']-low):
            raise ValueError('Persisted witness index differs from authenticated stress/error')
