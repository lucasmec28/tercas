"""Dispatch only explicit independent flexural choices; no method fusion."""
from . import biaxial_component as gross
from . import aa_component as aa

def attach_fresh(result, source):
    if aa.selected(result['input_data']):
        try:return aa.attach_fresh(result,source)
        except (OSError,RuntimeError,ImportError) as exc:
            raise ValueError('Fonte/runtime AA indisponível ou sem integridade; cálculo não emitido: '+str(exc)) from exc
    return gross.attach_fresh(result,source)

def presentation_rows(result, rows):
    return aa.presentation_rows(result,gross.presentation_rows(result,rows))

def is_girt_result(result):
    return gross.is_girt_result(result) or aa.is_girt_result(result)

def claims_result(result):
    return gross.claims_result(result) or aa.claims_result(result)

def selected(data):
    return gross.selected(data) or aa.selected(data)

def scope_text(data):
    return aa.scope_text(data) if aa.selected(data) else gross.scope_text(data)
