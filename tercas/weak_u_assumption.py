"""Explicit, section-bound U/web sense inference for exploratory calculations.

Off by default. Coverage is an evidence whitelist, NOT a normative geometry or
thickness criterion. This does not assert a bending sense declared by Pierin.
"""
import copy
from .catalogs import catalog_entry
from .weak_pierin import reference_for_index,reference_for_inputs

VERSION='u_pierin_web_inference_20261102_r01'
FIELD='u_pierin_assumption'
MARKER='HIPÓTESE PROVISÓRIA U/ALMA INFERIDA'
WARNING='Exploratório — hipótese de sentido inferida, pendente de confirmação. Pierin não declara a face comprimida; índice calculado não constitui aprovação.'
EVIDENCE_LIBRARY_ID='libfile_ca60144081c08191b498e2c7adb1135a'
# Exactly the four non-diagnostic geometries with n6/n9/modes independently
# reviewed in R01. No rule in t, h/b or numerical agreement is inferred.
COVERED={(50.,25.,0.,1.2),(100.,75.,0.,2.65),(200.,50.,0.,2.),(300.,100.,0.,2.65)}
TOKEN_KEYS={'version','catalog_id','reference_id','source_pdf_sha256','compression_side','acknowledged_as_inference'}

def marked(s):
 return FIELD in s or MARKER in s.get('provenance','').upper()

def selected(s):
 token=s.get(FIELD)
 return isinstance(token,dict) and token.get('acknowledged_as_inference') is True

def validate_token(s):
 if FIELD not in s:return
 token=s[FIELD]
 if not isinstance(token,dict) or set(token)!=TOKEN_KEYS:raise ValueError('Hipótese U/alma: registro explícito incompleto ou desconhecido.')
 if not isinstance(token['acknowledged_as_inference'],bool):raise ValueError('Hipótese U/alma: reconhecimento deve ser booleano explícito.')
 if any(not isinstance(token[k],str) or not token[k] or len(token[k])>200 for k in TOKEN_KEYS-{'acknowledged_as_inference'}):raise ValueError('Hipótese U/alma: identidade ou versão inválida.')

def covered(index):
 e=catalog_entry(index);d=e['dimensions_mm']
 return e['family']=='U' and tuple(d[k] for k in ('h','bf','lip','t')) in COVERED

def expected_token(index):
 e=catalog_entry(index);r=reference_for_index(index)
 return dict(version=VERSION,catalog_id=e['id'],reference_id=r.get('id',''),
  source_pdf_sha256=r.get('source_pdf_sha256',''),compression_side='web',acknowledged_as_inference=True)

def origin(index):
 e=catalog_entry(index);r=reference_for_index(index)
 return (f"{MARKER}: escolha explícita para My positivo/alma comprimida; não é declaração de sentido de Pierin. "
  f"Ml,y oficial: Tabela {r.get('table')}, p{r.get('printed_page')}/PDF{r.get('PDF_page')}; planilha V03 linha {e['source_workbook_row']}; "
  f"{VERSION}; benchmark 124/124 apoia inferência, com refinamento/modal apenas nos casos identificados. "
  "Modelo próprio E=200000 MPa, nu=0,3, G=76923,076923 MPa e linha média reta; G/nu e convenção exata da fonte não confirmados. Pendente de revisão; sem aprovação de resistência.")

def input_row(index):
 if not covered(index):raise ValueError('Hipótese U/alma não disponível fora da lista explícita de evidência revisada.')
 r=reference_for_index(index)
 return dict(Ml_Nmm=r['Mly_Nmm'],Mdist_Nmm=None,plain_u_no_distortion=True,
  provisional_hypothesis=True,provenance=origin(index),**{FIELD:expected_token(index)})

def reasons(data,family,sign,s):
 ref=reference_for_inputs(data);e=catalog_entry(data['catalog_index']);out=list(ref.get('compatibility_reasons',[]))
 if not covered(data['catalog_index']):out.append('Seção fora da lista explícita de quatro geometrias com evidência revisada desta hipótese.')
 if family!='U' or e['family']!='U' or sign!='positive':out.append('Hipótese U/alma restrita a U com My positivo; não transferir família ou sentido.')
 if ref['status']=='not_tabulated':out.append('Sem linha exata de Pierin para esta hipótese.')
 if s.get(FIELD)!=expected_token(data['catalog_index']):out.append('Falta reconhecimento explícito ou identidade/versão da hipótese não corresponde à seção e fonte.')
 if s.get('Ml_Nmm')!=ref.get('Mly_Nmm'):out.append('Ml,y da hipótese diverge do valor oficial da referência; não há escala ou substituição automática.')
 if s.get('provenance')!=origin(data['catalog_index']):out.append('Origem da hipótese inferida foi alterada ou não corresponde à seção.')
 if data.get('weak_catalog') is None:out.append('Esta opção exige a rota de propriedades do catálogo/linha média, não dados manuais misturados.')
 if any(data['properties'].get(k)!=v for k,v in e['published_properties'].items()):out.append('Propriedades de seção alteradas: a hipótese exploratória está vinculada ao conjunto original do catálogo.')
 if s.get('Mdist_Nmm') is not None or s.get('plain_u_no_distortion') is not True:out.append('Esta opção U simples não admite Mdist,y atribuído ou alteração da condição de não aplicabilidade.')
 return out

def evidence(data):
 selections=[dict(sign=sign,token=copy.deepcopy(row.get(FIELD))) for sign,row in data.get('weak_axis',{}).items() if marked(row)]
 if not selections:return None
 return dict(version=VERSION,selections=selections,warning=WARNING,
  inferred_side='web',source_sign=None,source_sign_declared=False,
  evidence_library_id=EVIDENCE_LIBRARY_ID,source_confirmation_pending=True,
  design_approved=False,whole_member_approved=False,
  scope='Explicit exploratory opt-in only; no bilateral use, no transfer across sections or catalogue scan.',
  limitation='124 paired numerical comparisons support inference, not source-sign proof. This option covers only four separately refined/reviewed geometries. Source G/nu/model geometry remain unconfirmed.')
