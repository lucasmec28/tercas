"""One-time removal of active UI caches after the shared integrator changed.

This session marker is not evidence of a runtime build or of physical validity.
It never enters input JSON, calculated snapshots, or historical Word records.
"""
EPOCH = 'active_ui_caches_Ue_CT_support_scope_20261108_r21'
KEY = 'calculation_cache_epoch'
ACTIVE_KEYS = ('result', 'catalog_scan_state', 'three_girt_warping_result')


def refresh(state):
    if state.get(KEY)==EPOCH:return False
    had_active=any(key in state for key in ACTIVE_KEYS)
    for key in ACTIVE_KEYS:state.pop(key,None)
    state[KEY]=EPOCH
    return had_active
