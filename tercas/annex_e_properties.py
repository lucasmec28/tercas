"""NBR14762:2010 Annex E.2.1.1/E.2.1.2(a,b), printed83/PDF89.
Closed expressions for U/Ue in mean-line dimensions. No catalogue-coordinate
conversion is inferred. No local/distortional critical is generated here.
"""
from .inclination import number


def channel_properties(am_mm,bm_mm,t_mm,cm_mm=0.,Iy_mm4=None,Iy_provenance=None):
    a=number(am_mm,'am',True);b=number(bm_mm,'bm',True);t=number(t_mm,'t',True);c=number(cm_mm,'cm')
    if c<0 or c>=a/2:raise ValueError('cm must be >=0 and < am/2 for this U/Ue route')
    if t>=min(a,b):raise ValueError('thickness outside thin-wall geometry')
    xm=b*(b+2*c)/(a+2*b+2*c)
    x0=b*(3*a*a*b+c*(6*a*a-8*c*c))/(a**3+6*a*a*b+c*(8*c*c-12*a*c+6*a*a))+xm
    bw=-(t*xm*a**3/12+t*xm**3*a)
    bf=t/2*((b-xm)**4-xm**4)+t*a*a/4*((b-xm)**2-xm*xm)
    bl=2*c*t*(b-xm)**3+2/3*t*(b-xm)*((a/2)**3-(a/2-c)**3)
    iy_line=t*a*xm*xm+2*t/3*((b-xm)**3+xm**3)+2*c*t*(b-xm)**2
    if Iy_mm4 is not None and (not isinstance(Iy_provenance,str) or not Iy_provenance.strip()):
        raise ValueError('Iy override requires same-section/axis/convention provenance')
    iy=iy_line if Iy_mm4 is None else number(Iy_mm4,'Iy',True)
    j=(bw+bf+bl)/(2*iy)+x0
    return {'xm_mm':xm,'x0_mm':x0,'j_mm':j,'Iy_used_mm4':iy,'Iy_mean_line_mm4':iy_line,
            'beta_w_mm5':bw,'beta_f_mm5':bf,'beta_lip_mm5':bl,
            'source':'NBR14762:2010 Annex E.2.1.1/E.2.1.2(a,b) p83',
            'geometry_convention':'explicit mean-line dimensions am,bm,cm; x0 positive magnitude',
            'Iy_provenance':Iy_provenance if Iy_mm4 is not None else 'mean-line integration of explicit dimensions',
            'capacity_evaluated':False}
