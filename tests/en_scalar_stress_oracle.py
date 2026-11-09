import math
from tercas.three_girt_en_normal.bound_certificate import controls,point,add,mul,scale,field_bernstein,elevation_weights,up,mag,hyperbolic
def scalar_stress_bound(row,pk,wk,field,x0,x1,u0,u1,scale_key,weight_scale):
    # Transform u, then x; interval coefficients include every transform op.
    uc=[controls([point(v) for v in row[pk][:,j]],u0,u1) for j in range(3)]
    wc=controls([point(v) for v in row[wk]],u0,u1)
    bm,tail=field_bernstein(*(field[k] for k in ('h','B0','U','V')),x0,x1)
    upper=0.
    dx=add(point(x1),point(-x0));a=point(x0)
    for i in range(3):
        p=[uc[j][i] for j in range(3)]
        q0=add(p[0],mul(a,add(p[1],mul(a,p[2]))))
        q1=mul(dx,add(p[1],scale(mul(a,p[2]),2)))
        q2=mul(mul(dx,dx),p[2])
        for k,weights in enumerate(elevation_weights()):
            poly=q0
            if k>=1:poly=add(poly,mul(q1,weights[1]))
            if k>=2:poly=add(poly,mul(q2,weights[2]))
            value=add(poly,mul(wc[i],bm[k]))
            upper=max(upper,up(mag(value)+up(mag(wc[i])*tail)))
    # Same construction-error convention as the numerical envelope, with
    # outward operations and a global field magnitude, not trusted JSON.
    c,s=hyperbolic(field['h'],1.)
    fm=add(point(abs(field['B0'])),add(scale(c,abs(field['U'])),scale(s,abs(field['V']))))[1]
    def abs_sum(values):
        total=0.
        for v in values:total=up(total+abs(float(v)))
        return total
    ps=max(float(row[scale_key]),abs_sum(row[pk].flat))
    ws=max(weight_scale,abs_sum(row[wk]))
    guard=up(128*2.220446049250313e-16*max(1.,up(ps+up(ws*fm))))
    return up(upper+guard)

from tercas.three_girt_en_normal.bound_certificate import SCHEMA,KEYS,boxes,down

def scalar_verify(certificate,rows,tw,torsion,left,right,limit):
    if not isinstance(certificate,dict) or set(certificate)!={'schema','faces'} or certificate['schema']!=SCHEMA:
        raise ValueError('Missing/versioned interval bound certificate')
    faces=certificate['faces']
    if not isinstance(faces,list) or len(faces)!=len(rows):raise ValueError('Certificate face coverage')
    result=dict.fromkeys(KEYS,0.)
    for face,row in zip(faces,rows):
        if not isinstance(face,dict) or set(face)!={'segment_index','face','paths'} or (face['segment_index'],face['face'])!=(row['segment_index'],row['face']):
            raise ValueError('Certificate face identity')
        for x0,x1,u0,u1 in boxes(face['paths'],left,right):
            s=scalar_stress_bound(row,'sigma','omega',torsion,x0,x1,u0,u1,'sigma_roundoff_scale',sum(abs(row['omega'])))
            t=scalar_stress_bound(row,'tau','tw_weight',tw,x0,x1,u0,u1,'tau_roundoff_scale',row['tw_roundoff_scale'])
            # Outward elementary operations include the sqrt and denominator
            # roundoff; no sampled physical point is substituted for a bound.
            vals=(up(s/limit),up(up(t*up(math.sqrt(3)))/limit),
                  up(up(math.sqrt(up(up(s*s)+up(3*up(t*t)))))/down(1.1*limit)))
            for k,v in zip(KEYS,vals):
                if not math.isfinite(v) or v<0:raise ValueError('Nonfinite certificate bound')
                result[k]=max(result[k],v)
    return result
