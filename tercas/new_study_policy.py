"""Creation-only adoption of the requested local deflection component.

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
    from . import ue_reference, ue_family_reference, homogeneous_reference
    out = activate_direct_PP(data)
    # Frozen own-reference consumers do not implement the catalogue FLT
    # contract. Do not inject it or erase an incompatible imported declaration:
    # their unchanged source gates must still reject any supplied extra marker.
    if homogeneous_reference.FIELD in data:
        return out  # Its own scalar deflection route is frozen as well.
    if ue_reference.claims_reference(data) or ue_family_reference.claims_reference(data):
        return activate(out)
    return activate(activate_combined(out))


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
