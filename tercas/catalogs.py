"""Read-only workbook catalogue and material presets, with explicit provenance."""
import copy,json,math
from pathlib import Path

GERDAU='https://gsn.gerdau.com/sites/gsn_gerdau/files/downloadable_files/Catalogo-Chapa-Grossa.pdf'
USIMINAS='https://pt.slideshare.net/slideshow/catalogo-geral-usiminas-01/87514983'
STEELS={
 'ASTM A36':{'fy_MPa':250.,'fu_MPa':400.,'source':GERDAU},
 'USI-CIVIL 300':{'fy_MPa':300.,'fu_MPa':400.,'source':USIMINAS},
 'USI-CIVIL 350':{'fy_MPa':350.,'fu_MPa':500.,'source':USIMINAS},
 'ASTM A572 Gr.50':{'fy_MPa':345.,'fu_MPa':450.,'source':GERDAU},
}
STEEL_NAMES=tuple(STEELS)+('Personalizado',)

def entries():
 return json.loads((Path(__file__).parent/'core/catalogo_documentado.json').read_text(encoding='utf-8'))['entries']

def catalog_entry(index):
 es=entries()
 if not isinstance(index,int) or isinstance(index,bool) or not 0<=index<len(es):raise ValueError('Perfil de catálogo inválido.')
 return es[index]

def catalog_labels():return [e['family']+' '+e['name'].removeprefix('U ').removeprefix('Ue ') for e in entries()]

def critical_defaults(index):
 e=catalog_entry(index);c=e['critical_values']
 return {'Ml_Nmm':c['Ml_Nmm'],'Mdist_Nmm':c['Mdist_Nmm'], 'critical_origin':f"{e['critical_source']} — planilha V03, 03_Perfis, linha {e['source_workbook_row']}; valores tabulados, não validação independente"}

def material(name,custom=None):
 """Nominal fy/fu; E/G are NBR14762 physical constants, not catalogue claims."""
 if name=='Personalizado':
  if custom is None:raise ValueError('Informe fy e fu do aço personalizado.')
  values={k:custom.get(k) for k in ['fy_MPa','fu_MPa']}
  origin=str(custom.get('origin','Aço personalizado informado pelo usuário')).strip()
  if not origin:raise ValueError('Informe a origem do aço personalizado.')
 elif name in STEELS:
  values={k:STEELS[name][k] for k in ['fy_MPa','fu_MPa']};origin=STEELS[name]['source']
 else:raise ValueError('Aço não reconhecido.')
 for k,v in values.items():
  if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0:raise ValueError(f'{k}: informe valor positivo e finito.')
 if values['fu_MPa']<values['fy_MPa']:raise ValueError('fu não pode ser menor que fy.')
 return {'name':name,'properties':{**values,'E_MPa':200000.,'G_MPa':77000.},'origin':origin,'physical_origin':'ABNT NBR 14762:2010 §4.6 — E=200000 MPa; G=77000 MPa', 'note':'Valores mínimos nominais do grau selecionado. Conferir especificação/certificado do produto; seleção não certifica fornecimento.'}

def apply_material(data,name,custom=None):
 out=copy.deepcopy(data);m=material(name,custom)
 out['properties'].update(m['properties'])
 out['property_origin']=f"{name}: {m['origin']}; {m['physical_origin']}"
 return out
