"""Creation-only preservation policy after cancellation of the timed fallback.

No clock, backend default mutation, import migration or result requalification.
Existing studies keep their recorded choice, including an omitted choice.
"""
import copy
from .deflection_scope import activate, enabled


def for_new_study(data):
    """Only fresh inputs from a named UI creation action may call this helper."""
    enabled(data)  # Reject an unknown pre-existing value instead of overwriting it.
    from .direct_self_weight import activate as activate_direct_PP
    from .flt_height_effective import activate_combined
    return activate_combined(activate_direct_PP(data))  # No automatic ELS fallback or biaxial adoption.


def initialize_session(state, factory):
    """Only an empty session proves creation; any existing key is conservative.

    A partial existing session can retain its last input as base, without adding
    a choice or rewriting that input. This is not a repair of unknown content.
    """
    if 'base' in state:
        return False
    preexisting = bool(state)
    data = copy.deepcopy(state['last_input']) if 'last_input' in state else factory()
    state['base'] = data if preexisting else for_new_study(data)
    return not preexisting
