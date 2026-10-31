"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math

def support(route=None,evidence=None):
 if route=='web_connection' and isinstance(evidence,str) and evidence.strip():
  return {'status':'stiffener_exception_9_5_1','reason':'web connected to another beam/column','connection_design_checked':False,'provenance':evidence,'support_contact_assumed':False}
 return {'status':'not_evaluated','missing':'select actual web connection, transverse stiffener or flange-contact geometry; no new normative check invented'}
