"""Exact diagnostic counterexamples. Not a normative resistance implementation."""
from fractions import Fraction as F
import json
from pathlib import Path


def polynomial_integral(coefficients, lo, hi, power=0):
    return sum((c*(hi**(i+power+1)-lo**(i+power+1))/F(i+power+1)
                for i,c in enumerate(coefficients)), F(0))


def run():
    beta=F(4,5)
    a=F(5,4)*(beta-F(1,5))
    q=[F(1),-4*(1-a),6*(1-a),-4*(1-a),1-a]
    full=polynomial_integral(q,F(0),F(1))
    assert full==beta
    bands=[(F(0),F(1,4)),(F(3,4),F(1))]
    area=sum((hi-lo for lo,hi in bands),F(0))
    weighted=sum((polynomial_integral(q,lo,hi) for lo,hi in bands),F(0))
    assert weighted!=beta*area
    # Equal-area measures on a normalized plate do not determine moments.
    # Retained widths at root/tip and a uniformly thinned full plate.
    measures={'root':(F(1),F(0),beta),
              'tip':(F(1),1-beta,F(1)),
              'uniform':(beta,F(0),F(1))}
    moments={k:[t*polynomial_integral([F(1)],lo,hi,p) for p in range(3)]
             for k,(t,lo,hi) in measures.items()}
    assert all(v[0]==beta for v in moments.values())
    assert len({v[1] for v in moments.values()})==3
    assert len({v[2] for v in moments.values()})==3
    central={k:v[2]-v[1]**2/v[0] for k,v in moments.items()}
    assert central['root']==central['tip']!=central['uniform']
    # A rescaling enforcing area is an extra choice, not a spatial derivation.
    multiplier=beta*area/weighted
    assert multiplier!=1
    return dict(schema='EN_Ue_shear_lag_spatial_gap_diagnostics_v1',
        qualification_inferred=False,production_changed=False,
        beta=str(beta),quartic_coefficients=[str(c) for c in q],
        full_plate_q_integral=str(full),retained_bands=[[str(x) for x in b] for b in bands],
        local_effective_area=str(area),eq3_3_target=str(beta*area),
        naive_quartic_on_retained_area=str(weighted),
        ad_hoc_normalization_needed=str(multiplier),
        equal_area_raw_moments={k:[str(x) for x in v] for k,v in moments.items()},
        central_second_moments={k:str(v) for k,v in central.items()},
        tests=['quartic_full_plate_area','quartic_retained_strip_mismatch',
               'equal_area_different_first_moments','equal_area_different_second_moments',
               'equal_area_different_central_second_moments'])

if __name__=='__main__':
    result=run()
    Path(__file__).with_name('exact_diagnostics.json').write_text(json.dumps(result,indent=2)+'\n')
    print('5 exact diagnostic assertions passed; no resistance qualified.')
