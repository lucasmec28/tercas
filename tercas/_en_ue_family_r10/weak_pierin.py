"""Official adopted Pierin Mly reference, distinct from sense qualification.

The original workbook data are never overwritten. Exact nominal geometry only;
no interpolation, assumed sign, source nu, source G or elastic table scaling.
"""
import copy,json
from functools import lru_cache
from pathlib import Path
from .catalogs import catalog_entry

@lru_cache(maxsize=1)
def _database():
    return json.loads((Path(__file__).parent/'data/pierin_2013_weak_reference.json').read_text(encoding='utf-8'))

def reference_for_index(index):
    e=catalog_entry(index);db=_database();d=e['dimensions_mm']
    matches=[r for r in db['entries'] if r['family']==e['family'] and r['dimensions_mm']==d]
    if len(matches)!=1:
        return {'status':'not_tabulated','Mly_Nmm':None,'source_sign':None,
                'reason':'Sem linha geométrica exata nas Tabelas 1/2 de Pierin; sem interpolação ou troca de espessura.'}
    r=copy.deepcopy(matches[0])
    r.update(status='tabulated_adopted_reference',adopted_as_app_reference=True,
             title=db['title'],url=db['url'],source_pdf_sha256=db['source_pdf_sha256'],
             source_E_MPa=db['E_MPa'],source_G_MPa=db['G_MPa'],source_nu=db['nu'],
             boundary=db['boundary'],corners=db['corners'],
             source_geometry_to_mean_line=db['source_geometry_to_mean_line'],
             meaning=db['meaning'],sense_qualification='not_explicit_in_source',
             automatically_qualified_for_both_senses=False)
    return r

def reference_for_inputs(data):
    r=reference_for_index(data['catalog_index'])
    if r['status']=='not_tabulated':return r
    p=data['properties'];reasons=[]
    if any(p.get(k)!=v for k,v in r['dimensions_mm'].items()):
        reasons.append('Geometria nominal atual difere da linha tabelada de Pierin.')
    if p.get('E_MPa')!=r['source_E_MPa']:
        reasons.append('E difere de 200000 MPa declarado para Pierin.')
    if p.get('G_MPa')!=77000.:
        reasons.append('G difere da configuração original do app; G e ν da fonte não foram explicitados.')
    r.update(app_original_G_MPa=77000.,original_configuration_unchanged=not reasons,
             compatibility_reasons=reasons,
             compatibility_note='Compatibilidade de origem/configuração não é qualificação física; G=77000 MPa é detector de alteração do app, não valor atribuído a Pierin.',
             resistance_release=False)
    return r
