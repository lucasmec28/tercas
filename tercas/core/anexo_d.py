"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math
ROWS={
(True,True,1,'end'):(9,4.6,.14,.35,.02),
(True,True,1,'internal'):(5,15.8,.23,.14,.01),
(True,True,2,'end'):(12,8.6,.08,.12,.048),
(True,True,2,'internal'):(12,23,.10,.08,.031),
(False,True,1,'end'):(5,4.3,.14,.35,.02),
(False,True,1,'internal'):(5,15.8,.23,.14,.01),
(False,True,2,'end'):(3,15.8,.32,.05,.04),
(False,True,2,'internal'):(3,25.9,.52,.15,.001),
(False,False,1,'end'):(2,4.6,.40,.60,.03),
(False,False,1,'internal'):(1,14.9,.32,.10,.01),
(False,False,2,'end'):(1,2,.11,.37,.01),
(False,False,2,'internal'):(1,14,.47,.25,.04)}


def classify(h,end_distance,opposite_clear_distance,*,no_opposite_force=False):
    # Distâncias fornecidas já medidas segundo FiguraD.1; não estimadas pelo centróide.
    if type(no_opposite_force) is not bool:
        raise ValueError('declaração de ausência de força oposta deve ser booleana')
    if no_opposite_force:
        if opposite_clear_distance is not None:
            raise ValueError('ausência de força oposta não admite distância concorrente')
        if not all(math.isfinite(v) and v>=0 for v in (h,end_distance)) or h==0:
            raise ValueError('distancias invalidas')
        return (1, 'end' if end_distance<=1.5*h else 'internal')
    if opposite_clear_distance is None:
        raise ValueError('ausência de força oposta não declarada; distância física não informada')
    if not all(math.isfinite(v) and v>=0 for v in (h,end_distance,opposite_clear_distance)) or h==0:
        raise ValueError('distancias invalidas')
    return (1 if opposite_clear_distance>=1.5*h else 2,
            'end' if end_distance<=1.5*h else 'internal')

def frd(*,h,t,ri,c,fy,end_distance,opposite_clear_distance,connected=False,lip=True,theta=90,no_opposite_force=False):
    if not all(math.isfinite(v) for v in (h,t,ri,c,fy,theta)) or min(h,t,c,fy)<=0 or ri<0:
        raise ValueError('geometria/material invalido')
    if c<20: raise ValueError('contato fora do dominio: nao elevar c automaticamente')
    if theta!=90 or h/t>200 or c/t>210 or c/h>2: raise ValueError('fora da TabelaD.2')
    n,loc=classify(h,end_distance,opposite_clear_distance,no_opposite_force=no_opposite_force)
    key=(connected,lip,n,loc)
    if key not in ROWS: raise ValueError('configuracao sem linha tabulada')
    if connected and n==2 and loc=='internal' and end_distance<=2.5*h:
        raise ValueError('fora da nota e: distancia deve superar2.5h')
    rmax,a,ar,ac,ah=ROWS[key]
    if ri/t>rmax: raise ValueError('raio fora da linha tabulada')
    factors=(1-ar*math.sqrt(ri/t),1+ac*math.sqrt(c/t),1-ah*math.sqrt(h/t))
    if min(factors)<=0: raise ValueError('fator nao positivo')
    return a*t*t*fy*math.sin(math.radians(theta))*math.prod(factors)/1.35

def reactions(L,q,P,x):
    if not all(math.isfinite(v) for v in (L,q,P,x)) or not 0<=x<=L or L<=0: raise ValueError('entrada/posicao invalida')
    return q*L/2+P*(1-x/L), q*L/2+P*x/L
