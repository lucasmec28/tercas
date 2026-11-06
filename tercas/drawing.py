from .presentation import fmt
"""Pure SVG, no untrusted markup. Scaled schematic, not fabrication drawing."""
from html import escape
from .catalogs import catalog_entry
from .inclination_adapter import configuration

def svg(data):
 from .direct_self_weight import calculation_inputs
 data=calculation_inputs(data)
 from .member_application import is_girt
 if is_girt(data):return wall_girt_svg(data)
 p=data['properties'];h,b,t,lip=[float(p[k]) for k in ['h','bf','t','lip']];scale=min(120/h,100/b);x,y=90,100;H=h*scale;B=b*scale;T=max(2,t*scale);D=lip*scale
 _,ang=configuration(data);theta=ang['degrees']
 path=f'M{x+B},{y+D} L{x+B},{y} L{x},{y} L{x},{y+H} L{x+B},{y+H} L{x+B},{y+H-D}'
 # Centroid xg measured from the outer web face (catalogue convention).
 xg=catalog_entry(data['catalog_index'])['raw_source_values'].get('xg cm')
 cx=x+(float(xg)*10 if xg is not None else b/2)*scale;cy=y+H/2
 axes=f'<g id="section-local-axes" stroke="#147d92" stroke-width="1.4"><path d="M{x-15} {cy} H{x+B+25} m-7 -4 l7 4 l-7 4 M{cx} {y+H+15} V{y-10} m-4 7 l4 -7 l4 7" fill="none"/><g fill="#147d92" stroke="none" font-family="Arial" font-size="13"><text x="{x+B+28}" y="{cy+5}">X</text><text x="{cx+8}" y="{y-5}">Y</text></g></g>'
 L=data['L_mm'];a=data['x_uls'];px=340+500*a/max(L,1)
 position_text='x → 0+ (limite junto ao apoio)' if data.get('point_position')=='support_limit' else 'x = '+fmt(a)+' mm'
 P=data['P_uls']
 arrow_path=(f'M{px} 75 v55 m-5 -8 l5 8 l5 -8' if P>0 else f'M{px} 130 v-55 m-5 8 l5 -8 l5 8')
 arrow=(f'<path id="point-load-arrow" data-direction="{"down" if P>0 else "up"}" d="{arrow_path}" fill="none" stroke="#e87722" stroke-width="3"/>' if P!=0 else '')
 marks=''.join(f'<line x1="{340+500*s.get("start_mm",0)/max(L,1):.2f}" y1="126" x2="{340+500*s.get("start_mm",0)/max(L,1):.2f}" y2="147" stroke="#147d92"/>' for s in data.get('segments',[]) if isinstance(s,dict))
 return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 410" role="img" aria-label="Seção U ou Ue e viga biapoiada com carga informada">
 <rect width="920" height="410" fill="#fafbfc" rx="14"/>
 <g id="section-oriented" data-angle-degrees="{theta:.12g}" transform="rotate({theta:.12g} {cx:.12g} {cy:.12g})">
 <line id="roof-plane" x1="{x-25}" y1="{y-12}" x2="{x+B+25}" y2="{y-12}" stroke="#768595" stroke-dasharray="5 3"/>
 <path d="{path}" fill="none" stroke="#e87722" stroke-width="{T}" stroke-linejoin="round"/>
 {axes}
 <text x="{x+B+8}" y="{cy+24}" font-family="Arial" font-size="11" fill="#25334a">Boca / +paralelo</text>
 <path id="normal-positive" d="M{x-30} {cy-25} v45 m-4 -7 l4 7 l4 -7" fill="none" stroke="#7b4397" stroke-width="2"/>
 <text x="{x-55}" y="{cy+36}" font-family="Arial" font-size="10" fill="#7b4397">+normal</text>
 </g>
 <g id="gravity-global" stroke="#424b57" stroke-width="2"><path d="M280 85 v60 m-5 -8 l5 8 l5 -8" fill="none"/></g>
 <text x="250" y="75" font-family="Arial" font-size="11" fill="#424b57">Gravidade</text>
 <g font-family="Arial" font-size="14" fill="#25334a"><text x="25" y="25">Seção vista do apoio A para B</text><text x="20" y="260">h={fmt(h)} · b={fmt(b)} · t={fmt(t)} · D={fmt(lip)} mm</text>
 <text x="340" y="25">Vista longitudinal — cargas normais locais</text><text x="520" y="195">L = {fmt(L)} mm</text><text x="{px-40}" y="65">P = {fmt(data['P_uls']/1000)} kN</text><text x="350" y="240">q = {fmt(data['q_uls'])} kN/m · {position_text}</text></g>
 <line x1="340" y1="140" x2="840" y2="140" stroke="#34455f" stroke-width="5"/>
 <path d="M340 143 l-10 18 h20 z M840 143 l-10 18 h20 z" fill="none" stroke="#34455f" stroke-width="2"/>
 {arrow}{marks}
 <g font-family="Arial" font-size="12" fill="#25334a">
 <text x="20" y="295">θ = {fmt(theta)}° · 0°: boca à direita. +θ: caimento para a boca; −θ: caimento oposto.</text>
 <text x="20" y="318">X local: para a boca; Y local: para fora da cobertura. +normal = −Y. A seção gira com a cobertura.</text>
 <text x="20" y="341">Gravidade é vertical; vento é normal ao plano. Setas de referência, não escala de forças.</text>
 <text x="20" y="364">{'Modo direto: ações já locais; a inclinação NÃO gira novamente os valores informados.' if data.get('load_mode')!='area' else 'Modo por área: gravidade decomposta; vento normal. Sem travamento da telha.'}</text>
 </g>
 <text x="335" y="182" font-family="Arial" font-size="12" fill="#25334a">A</text><text x="835" y="182" font-family="Arial" font-size="12" fill="#25334a">B</text>
 <text x="340" y="265" font-family="Arial" font-size="12" fill="#667085">Esquema dinâmico. Telha não considerada como travamento. Trechos em azul.</text></svg>'''


def wall_girt_svg(data):
 """Physical section +90°; longitudinal normal-force diagram explicitly unfolded.
 No spring/support is inferred or rendered as rigid from an effective length.
 """
 p=data['properties'];h,b,t,lip=[float(p[k]) for k in ('h','bf','t','lip')]
 scale=min(120/h,100/b);x,y=100.,80.;H=h*scale;B=b*scale;D=lip*scale;T=max(2.,t*scale)
 cx=x+B/2;cy=y+H/2
 path=f'M{x+B},{y+D} L{x+B},{y} L{x},{y} L{x},{y+H} L{x+B},{y+H} L{x+B},{y+H-D}'
 L=float(data['L_mm']);a=float(data['x_uls']);px=360+500*a/max(L,1.)
 P=float(data['P_uls']);qp=float(data.get('q_parallel_uls',0.));pp=float(data.get('P_parallel_uls',0.))
 point=''
 if P:
  d=f'M{px} 95 v45 m-5 -8 l5 8 l5 -8' if P>0 else f'M{px} 140 v-45 m-5 8 l5 -8 l5 8'
  point=f'<path id="point-load-arrow" data-direction="{"left-physical" if P>0 else "right-physical"}" d="{d}" fill="none" stroke="#e87722" stroke-width="3"/>'
 mode='Direto: ações locais totais calculadas; PP conforme convenção das entradas.' if data.get('load_mode')!='area' else 'Área: PP/permanente verticais, vento horizontal; sem SC/P de cobertura automáticos.'
 return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 440" role="img" aria-label="Travessa lateral U ou Ue boca para baixo, vento horizontal e gravidade vertical">
 <rect width="940" height="440" fill="#fafbfc" rx="14"/>
 <g font-family="Arial" fill="#25334a" font-size="13">
 <text x="20" y="25">Travessa — vista do apoio A para B</text>
 <g id="section-oriented" data-member-application="wall_girt" data-angle-degrees="90" transform="rotate(90 {cx} {cy})">
 <path id="section-outline" d="{path}" fill="none" stroke="#e87722" stroke-width="{T}" stroke-linejoin="round"/>
 </g>
 <path id="normal-positive" data-direction="left" d="M260 140 h-60 m8 -5 l-8 5 l8 5" stroke="#7b4397" stroke-width="2" fill="none"/>
 <text x="215" y="125" fill="#7b4397">+normal ←</text>
 <path id="parallel-positive" data-direction="down" d="M{cx} 160 v65 m-5 -8 l5 8 l5 -8" stroke="#147d92" stroke-width="2" fill="none"/>
 <text x="20" y="245">Boca ↓ · +paralelo vertical ↓</text>
 <text x="20" y="265">h={fmt(h)} · b={fmt(b)} · t={fmt(t)} · D={fmt(lip)} mm</text>
 <text x="360" y="25">Vão do modelo — plano forte rebatido no papel</text>
 <text x="360" y="47">Setas deste diagrama representam forças normais horizontais.</text>
 <text x="{px-40}" y="80">P normal = {fmt(P/1000)} kN</text>
 <line x1="360" y1="150" x2="860" y2="150" stroke="#34455f" stroke-width="5"/>
 <path d="M360 153 l-10 18 h20 z M860 153 l-10 18 h20 z" fill="none" stroke="#34455f" stroke-width="2"/>
 {point}<text x="355" y="193">A</text><text x="855" y="193">B</text>
 <text x="510" y="205">L modelo = {fmt(L)} mm</text>
 <text x="360" y="230">q horizontal normal = {fmt(data['q_uls'])} kN/m</text>
 <text x="360" y="252">q vertical paralelo = {fmt(qp)} kN/m; P vertical = {fmt(pp/1000)} kN</text>
 <text x="20" y="300">Flexão forte horizontal; flexão fraca vertical. X local para baixo; Y local para a direita.</text>
 <text x="20" y="323">Mesa superior do referencial = direita física; mesa inferior = esquerda física.</text>
 <text x="20" y="346">{escape(mode)}</text>
 <text x="20" y="369">L modelo, Lref ELS e comprimentos efetivos FLT são distintos. Sem crédito da telha.</text>
 <text x="20" y="392">Tirantes não são apoios rígidos nem travamentos torsionais automáticos. Estudo bruto separado.</text>
 <text x="20" y="415">Esquema, não desenho de fabricação. Forças aplicadas no modelo declarado, sem escala de intensidade.</text>
 </g></svg>'''
