"""Recover existing workbook properties without inventing geometry conventions."""
import math
from .catalogs import catalog_entry
from .inclination import number
from .annex_e_properties import channel_properties

def nominal_mean_line(data):
 e=catalog_entry(data['catalog_index']);p=data['properties'];h=number(p['h'],'h',True);b=number(p['bf'],'bf',True);t=number(p['t'],'t',True);D=number(p['lip'],'D')
 if e['family']=='U':bm=b-t/2;cm=0.
 elif e['family']=='Ue':bm=b-t;cm=D-t/2
 else:raise ValueError('Conversão de linha média restrita a U/Ue.')
 am=h-t
 if min(am,bm)<=0 or cm<0:raise ValueError('Dimensões nominais incompatíveis com linha média.')
 return {'am_mm':am,'bm_mm':bm,'cm_mm':cm,'origin':'NBR 14762:2010 Figura E.1 p84/PDF90; Ue conferido no CBCA2014 Ex08 p69: am=h−t, bm=bf−t, cm=D−t/2; U: am=h−t, bm=bf−t/2, cm=0. ri preservado do catálogo, não inferido.','conversion':'nominal_external_to_mean_line_verified','source_nominal_dimensions':{'h':h,'bf':b,'D':D,'t':t}}

def geometry_mode(cfg):
 mode=cfg.get('geometry_mode')
 if mode is not None:
  if mode not in ('catalog','explicit'):raise ValueError('Modo de geometria do eixo fraco inválido.')
  return mode
 # Preserve explicitly completed legacy user inputs; empty old fields now use
 # the source-confirmed conventional conversion instead of staying pending.
 gm=cfg.get('mean_line',{})
 return 'explicit' if isinstance(gm,dict) and all(gm.get(k) is not None for k in ('am_mm','bm_mm','cm_mm')) and isinstance(gm.get('origin'),str) and gm['origin'].strip() else 'catalog'

def automatic_inputs(data):
 e=catalog_entry(data['catalog_index']);raw=e['raw_source_values'];p=data['properties'];L=data['L_mm'];cfg=data.get('weak_catalog',{})
 if not isinstance(cfg,dict):raise ValueError('Configuração automática do eixo fraco inválida.')
 lx=number(cfg.get('Lx_mm',L),'Lx eixo fraco',True)
 # Conservative effective torsion length over supplied full-span segments.
 lzs=[s.get('Lz_effective_mm') for s in data['segments']]
 if not lzs or any(v is None for v in lzs):return {'status':'not_evaluated','missing':['Lz torsional efetivo'],'signs':{}}
 lz=max(number(v,'Lz',True) for v in lzs)
 A=number(p['A_cm2'],'A',True)*100;ix=number(p['Ix_cm4'],'Ix',True)*1e4;iy=number(p['Iy_cm4'],'Iy',True)*1e4
 r0=number(raw.get('r0 cm'),'r0 tabelado',True)*10;xg=number(raw.get('xg cm'),'xg tabelado',True)*10;x0=number(raw.get('x0 cm'),'x0 tabelado',True)*10
 W=number(raw.get('Wy cm³'),'Wy tabelado',True)*1000;b=number(p['bf'],'bf',True)
 if not 0<xg<b:raise ValueError('Centroide tabelado fora da largura da seção.')
 # Detect incompatible edited property sets rather than silently mixing them.
 rcheck=math.sqrt((ix+iy)/A+x0*x0);wcheck=iy/max(xg,b-xg)
 checks={'r0_relative_difference':abs(r0/rcheck-1),'Wy_relative_difference':abs(W/wcheck-1)}
 catalog_warnings=[]
 if any(v>.03 for v in checks.values()):
  original=all(p.get(k)==v for k,v in e['published_properties'].items())
  if original and checks['r0_relative_difference']<=.03 and W<=wcheck:
   catalog_warnings.append('Wy original tabelado difere mais de3% da reconstrução Iy/distância extrema; adota-se o menor Wy conservador, sem corrigir a fonte. Conferência documental pendente; isto não é uma verificação normativa adicional.')
  else:return {'status':'not_evaluated','missing':['Propriedades alteradas/incompatíveis com xg/x0/Wy/r0 da planilha'],'checks':checks,'signs':{}}
 mode=geometry_mode(cfg)
 geom=cfg.get('mean_line') if mode=='explicit' else nominal_mean_line(data)
 if not isinstance(geom,dict) or not all(geom.get(k) is not None for k in ('am_mm','bm_mm','cm_mm')) or not isinstance(geom.get('origin'),str) or not geom['origin'].strip():
  return {'status':'not_evaluated','missing':['Dimensões médias am/bm/cm e convenção rastreada para j do Anexo E'],'checks':checks,'catalog_properties':{'W_mm3':W,'xg_mm':xg,'x0_mm':x0,'r0_mm':r0},'signs':{}}
 if mode=='explicit':
  expected=nominal_mean_line(data)
  if any(not math.isclose(geom[k],expected[k],rel_tol=1e-6,abs_tol=1e-6) for k in ('am_mm','bm_mm','cm_mm')):
   return {'status':'not_evaluated','missing':['Linha média explícita difere da conversão nominal comprovada; outro modelo de seção não pode usar automaticamente Iy do catálogo. Selecione a conversão automática ou qualifique o conjunto geométrico.'],'mean_line':geom,'mean_line_conversion_verified':False,'checks':checks,'signs':{}}
 if geom['am_mm']>p['h'] or geom['bm_mm']>p['bf'] or geom['cm_mm']>p['lip']:
  return {'status':'not_evaluated','missing':['Dimensão média excede dimensão externa do mesmo perfil'],'checks':checks,'signs':{}}
 if (e['family']=='U' and geom['cm_mm']!=0) or (e['family']=='Ue' and geom['cm_mm']<=0):
  return {'status':'not_evaluated','missing':['cm da linha média incompatível com família U/Ue selecionada'],'checks':checks,'signs':{}}
 gp=channel_properties(geom['am_mm'],geom['bm_mm'],p['t'],geom['cm_mm'],Iy_mm4=iy,Iy_provenance=geom['origin']+'; Iy planilha mesma seção/eixo; conferir arredondamentos')
 checks.update(xg_relative_difference=abs((gp['xm_mm']+p['t']/2)/xg-1),x0_relative_difference=abs(gp['x0_mm']/x0-1),Iy_mean_line_relative_difference=abs(gp['Iy_mean_line_mm4']/iy-1))
 warnings=list(catalog_warnings)
 if any(checks[k]>.03 for k in ('xg_relative_difference','x0_relative_difference','Iy_mean_line_relative_difference')):
  warnings.append('Linha média idealizada e catálogo com cantos apresentam diferenças superiores a3%; comparação informativa, não exigência normativa nem bloqueio. Iy e demais propriedades tabuladas preservados.')
 j=gp['j_mm']
 E=number(p['E_MPa'],'E',True);G=number(p['G_MPa'],'G',True);J=number(p['J_mm4'],'J',True);Cw=number(p['Cw_mm6'],'Cw',True)
 nex=math.pi**2*E*ix/lx**2;nez=(G*J+math.pi**2*E*Cw/lz**2)/r0**2
 origin=f"Planilha V03 03_Perfis linha {e['source_workbook_row']}; {e['source_url']}; am/bm/cm: {geom['origin']}; Nex/Nez NBR14762 Anexo E com Lx={lx:g} mm, Lz={lz:g} mm; sem telha"
 signs={}
 for sign,c,cs in [('positive',xg,1),('negative',b-xg,-1)]:
  wc=iy/c
  # Published rounded Wy may exceed the reconstructed minimum by rounding.
  w=min(W,iy/max(xg,b-xg))
  signs[sign]=dict(W_mm3=w,Wc_mm3=wc,Nex_N=nex,Nez_N=nez,r0_mm=r0,j_mm=j,Cm=1.,Cs=cs,provenance=origin)
 return {'status':'computed_catalog_inputs','catalog_convention_pending':bool(e.get('source_geometry_convention_unresolved',True)),'mean_line_conversion_verified':mode=='catalog','geometry_mode':mode,'warnings':warnings,'geometry_basis':geom['origin'],'checks':checks,'geometry':gp,'mean_line':geom,'catalog_properties':{'W_published_mm3':W,'xg_mm':xg,'x0_mm':x0,'r0_mm':r0},'Lx_mm':lx,'Lz_mm':lz,'signs':signs,'convention':'My positivo: alma comprimida (Cs=+1); My negativo: bordas/lábios comprimidos (Cs=-1). Orientação deve corresponder aos eixos locais.'}

def critical_hypothesis(index):
 """Official table value != qualified sense. Preserve only prior Ue hypothesis."""
 from .weak_pierin import reference_for_index
 e=catalog_entry(index);ref=reference_for_index(index)
 # Lucas adopted Pierin values as the official app reference. That decision does
 # not supply a missing bending sense. New U values are displayed, not assigned.
 v=ref['Mly_Nmm'] if e['family']=='Ue' else None
 origin=(f"HIPÓTESE PROVISÓRIA autorizada SOMENTE de sentido: Ml,y é valor oficial da referência adotada Pierin2013, Tabela {ref.get('table')}, p{ref.get('printed_page')}/PDF{ref.get('PDF_page')}; interpretado com alma comprimida; planilha V03 linha {e['source_workbook_row']}; {e['critical_source']}. Comparação pyCUFSM Ue200x75x20x2 apoia este sentido, não valida todo catálogo. O sentido não é explicitado na tabela; Mdist,y continua independente." if v is not None else '')
 return {'positive':{'provisional_hypothesis':v is not None,'Ml_Nmm':v,'Mdist_Nmm':None,'plain_u_no_distortion':e['family']=='U','provenance':origin},'negative':{'Ml_Nmm':None,'Mdist_Nmm':None,'plain_u_no_distortion':e['family']=='U','provenance':''}}
