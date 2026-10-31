"""Human-readable numbers only; never feed these strings back into calculation."""
import math
import re
from numbers import Real

def fmt(value, limit=None):
    if value is None:
        return '—'
    if isinstance(value, bool) or not isinstance(value, Real):
        return str(value)
    n=float(value)
    if not math.isfinite(n):
        return 'não finito'
    rounded=f'{n:.2f}'
    if n != 0 and float(rounded) == 0:
        return ('−' if n < 0 else '') + '<0,01'
    result=('0.00' if n == 0 else rounded).replace('.', ',')
    if limit is not None and n != limit and rounded == f'{limit:.2f}':
        result += ' (' + ('>' if n > limit else '<') + fmt(limit) + ')'
    return result

def display(value):
    if isinstance(value, dict):
        return '{' + '; '.join(str(k) + ': ' + (fmt(v,limit=1.) if k in ('index','index_squared') else display(v)) for k,v in value.items()) + '}'
    if isinstance(value, (list, tuple)):
        return '[' + '; '.join(display(v) for v in value) + ']'
    return fmt(value)

# Only measurement text from known presentation columns, never normative references,
# profile names, project text, source URLs, fingerprints or technical JSON.
_NUMBER=re.compile(r'(?<![\w.,])[-+]?(?:\d+\.\d+|\d+)(?:[eE][-+]?\d+)?(?![\w.,])')
def measurement_text(value):
    if not isinstance(value,str):
        return fmt(value)
    return _NUMBER.sub(lambda m:fmt(float(m.group())),value)

def display_records(records):
    output=[]
    for row in records:
        new={}
        for key,value in row.items():
            if key == 'Índice':
                new[key]=fmt(value,limit=1.)
            elif isinstance(value, Real) and not isinstance(value,bool):
                new[key]=fmt(value)
            elif key in ('Demanda / valor','Resistência / limite','Expressão'):
                new[key]=measurement_text(value)
            elif key == 'Observação' and isinstance(value,str):
                new[key]=re.sub(r'(?<![\w.,])[-+]?\d+(?:\.\d+)?(?= mm(?:[.; ,]|$))',lambda m:fmt(float(m.group())),value)
            else:
                new[key]=value
        output.append(new)
    return output

DISPLAY_NOTE=('Exibição com duas casas decimais; cálculos e arquivos JSON mantêm a precisão completa. '
              'Valores não nulos inferiores à resolução aparecem como <0,01 (ou −<0,01). '
              'Índices arredondados para 1,00 indicam > ou < quando necessário; a situação usa o valor não arredondado.')


def display_frame(records):
    """Format a presentation copy, including all pandas missing-value sentinels."""
    import pandas as pd
    frame = pd.DataFrame(records)
    def formatter(key):
        return lambda value: display_records([{key: value}])[0][key]
    return frame.style.format({key: formatter(key) for key in frame.columns}, na_rep='—')
