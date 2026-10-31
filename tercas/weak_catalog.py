"""Recover existing workbook properties without inventing geometry conventions."""
import math
from .catalogs import catalog_entry
from .inclination import number
from .annex_e_properties import channel_properties

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
 if any(v>.03 for v in checks.values()):return {'status':'not_evaluated','missing':['Propriedades alteradas/incompatíveis com xg/x0/Wy/r0 da planilha'],'checks':checks,'signs':{}}
 geom=cfg.get('mean_line') or e.get('mean_line_dimensions_mm')
 if not isinstance(geom,dict) or not all(geom.get(k) is not None for k in ('am_mm','bm_mm','cm_mm')) or not isinstance(geom.get('origin'),str) or not geom['origin'].strip():
  return {'status':'not_evaluated','missing':['Dimensões médias am/bm/cm e convenção rastreada para j do Anexo E'],'checks':checks,'catalog_properties':{'W_mm3':W,'xg_mm':xg,'x0_mm':x0,'r0_mm':r0},'signs':{}}
 if (e['family']=='U' and geom['cm_mm']!=0) or (e['family']=='Ue' and geom['cm_mm']<=0):
  return {'status':'not_evaluated','missing':['cm da linha média incompatível com família U/Ue selecionada'],'checks':checks,'signs':{}}
 gp=channel_properties(geom['am_mm'],geom['bm_mm'],p['t'],geom['cm_mm'],Iy_mm4=iy,Iy_provenance=geom['origin']+'; Iy planilha mesma seção/eixo; conferir arredondamentos')
 checks.update(xg_relative_difference=abs((gp['xm_mm']+p['t']/2)/xg-1),x0_relative_difference=abs(gp['x0_mm']/x0-1),Iy_mean_line_relative_difference=abs(gp['Iy_mean_line_mm4']/iy-1))
 if any(v>.03 for v in checks.values()):return {'status':'not_evaluated','missing':['Linha média incompatível com xg/x0/Iy tabelados; conferir convenção e raio'], 'checks':checks,'geometry':gp,'signs':{}}
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
 return {'status':'computed_catalog_inputs','catalog_convention_pending':bool(e.get('source_geometry_convention_unresolved',True)),'geometry_basis':'Dimensões médias explicitamente informadas; guarda de compatibilidade não certifica conversão da fonte.','checks':checks,'geometry':gp,'mean_line':geom,'catalog_properties':{'W_published_mm3':W,'xg_mm':xg,'x0_mm':x0,'r0_mm':r0},'Lx_mm':lx,'Lz_mm':lz,'signs':signs,'convention':'My positivo: alma comprimida (Cs=+1); My negativo: bordas/lábios comprimidos (Cs=-1). Orientação deve corresponder aos eixos locais.'}

def critical_hypothesis(index):
 """User-authorized provisional interpretation, NOT bilateral qualification."""
 e=catalog_entry(index);v=e['critical_values'].get('Mly_Nmm')
 return {'positive':{'provisional_hypothesis':v is not None,'Ml_Nmm':v,'Mdist_Nmm':None,'plain_u_no_distortion':e['family']=='U','provenance':(f"HIPÓTESE PROVISÓRIA autorizada: Ml,y tabulado interpretado com alma comprimida; planilha V03 linha {e['source_workbook_row']}; {e['critical_source']}. Comparação pyCUFSM de Ue 200x75x20x2 indica este sentido, diferença ~1,94%, não validação de todos os perfis. Conferência por exemplos CBCA pendente." if v is not None else '')},'negative':{'Ml_Nmm':None,'Mdist_Nmm':None,'plain_u_no_distortion':e['family']=='U','provenance':''}}
