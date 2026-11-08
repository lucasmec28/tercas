"""Current UI calculation boundary; saved readers never migrate prior inputs."""
import copy

POLICY_FIELDS = ('load_application_policy', 'local_support_verification_scope')


def prepare(data):
    """Disposable current-model input, suitable for controls or a new solve."""
    from .load_application_policy import for_calculation
    from .support_scope import adopt_for_calculation
    return adopt_for_calculation(for_calculation(data))


def preserve_policy_choices(edited, source):
    """Keep the opening/imported policy choice until the calculation click."""
    out = copy.deepcopy(edited)
    for field in POLICY_FIELDS:
        if field in source:out[field] = copy.deepcopy(source[field])
        else:out.pop(field, None)
    return out


def begin_calculation(state, data):
    """Archive once, then persist the exact new payload before fingerprints."""
    current = prepare(data)
    if current != data:
        from .pierin_ue_registry_ui import HISTORY, _snapshot
        state[HISTORY] = list(state.get(HISTORY, [])) + [_snapshot(state)]
    state['base'] = copy.deepcopy(current)
    state['last_input'] = copy.deepcopy(current)
    return current
