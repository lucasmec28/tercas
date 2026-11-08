"""Bounded in-process success tokens for unchanged NBR family validation.

This is not an offline reader, signature, persisted seal, or ingress authority.
Cold reads retain the original versioned source/mechanics replay. No snapshots,
object identities or client-provided hashes are trusted as cache keys.
"""
from collections import OrderedDict
from threading import RLock
import hashlib
import json
import math

# Complete result fields consumed by nbr_ue_family_application._build and its
# _inventory / own.preserved calls. Whole cases are intentionally over-bound.
# Presentation/global metadata are validated by their own consumers, and are
# not inputs to that NBR component reconstruction. Missing and null differ.
DEPENDENCIES=('input_data','input_fingerprint','schema','ue_catalog_reference_evidence',
              'load_bundle','cases','nbr_ue_family_application')
LIMIT=16
_SUCCESS=OrderedDict()
_LOCK=RLock()


def _native(value):
    t=type(value)
    if t in (str,int,bool,type(None)):return
    if t is float:
        if not math.isfinite(value):raise ValueError('Nonfinite JSON number')
        return
    if t is list:
        for item in value:_native(item)
        return
    if t is dict:
        for k,v in value.items():
            if type(k) is not str:raise ValueError('Native string keys required')
            _native(v)
        return
    raise ValueError('Native JSON types required for cache reuse')


def key(result):
    try:
        if type(result) is not dict:return None
        payload={k:result[k] for k in DEPENDENCIES if k in result}
        _native(payload)
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                       allow_nan=False).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()
    except (ValueError,TypeError,RecursionError,OverflowError,UnicodeError):
        return None


def contains(token):
    if token is None:return False
    with _LOCK:
        if token not in _SUCCESS:return False
        _SUCCESS.move_to_end(token)
        return True


def remember(token):
    if token is None:return
    with _LOCK:
        _SUCCESS[token]=True
        _SUCCESS.move_to_end(token)
        while len(_SUCCESS)>LIMIT:_SUCCESS.popitem(last=False)


def clear():
    """Explicit test/session maintenance; never changes saved engineering data."""
    with _LOCK:_SUCCESS.clear()
