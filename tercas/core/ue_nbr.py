"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math
import numbers
import numpy as np
ROWS=np.array([[.25,.12,.10,.06,.05],[.25,.12,.10,.06,.05],[.22,.12,.09,.06,.05],[.22,.11,.09,.06,.05],[.20,.11,.09,.06,.05],[.20,.10,.09,.06,.05],[.20,.10,.09,.06,.05],[.19,.10,.09,.06,.05],[.19,.10,.09,.06,.05]])

def table14(bw,bf,D,t):
 if not all(isinstance(v,numbers.Real) and not isinstance(v,(bool,np.bool_)) and math.isfinite(v) and v>0 for v in [bw,bf,D,t]):raise ValueError('positive dimensions required')
 eta=bf/bw;s=bw/t
 if not .4<=eta<=2 or not 50<=s<=250:return {'exempt':False,'status':'outside_table_not_automatic_failure'}
 along=[float(np.interp(s,[50,100,125,200,250],row)) for row in ROWS]
 req=float(np.interp(eta,np.linspace(.4,2,9),along))
 return {'exempt':D/bw>=req,'status':'in_table','D_bw':D/bw,'required_D_bw':req,'source':'NBR14762 Table14 nominal dimensions linear interpolation'}
