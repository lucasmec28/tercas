"""One-time removal of active UI caches after the shared integrator changed.

This session marker is not evidence of a runtime build or of physical validity.
It never enters input JSON, calculated snapshots, or historical Word records.
"""
EPOCH = 'active_ui_caches_ief_transition_20261103_r1'
KEY = 'calculation_cache_epoch'


def refresh(state):
    if state.get(KEY)==EPOCH:return False
    had_active=any(key in state for key in ('result','catalog_scan_state'))
    for key in ('result','catalog_scan_state'):state.pop(key,None)
    state[KEY]=EPOCH
    return had_active
