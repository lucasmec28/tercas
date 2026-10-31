from .presentation import fmt
"""Pure SVG, no untrusted markup. Scaled schematic, not fabrication drawing."""
from html import escape

def svg(data):
 p=data['properties'];h,b,t,lip=[float(p[k]) for k in ['h','bf','t','lip']];scale=min(170/h,150/b);x,y=55,45;H=h*scale;B=b*scale;T=max(2,t*scale);D=lip*scale
 path=f'M{x+B},{y+D} L{x+B},{y} L{x},{y} L{x},{y+H} L{x+B},{y+H} L{x+B},{y+H-D}'
 L=data['L_mm'];a=data['x_uls'];px=340+500*a/max(L,1)
 P=data['P_uls']
 arrow_path=(f'M{px} 75 v55 m-5 -8 l5 8 l5 -8' if P>0 else f'M{px} 130 v-55 m-5 8 l5 -8 l5 8')
 arrow=(f'<path id="point-load-arrow" data-direction="{"down" if P>0 else "up"}" d="{arrow_path}" fill="none" stroke="#e87722" stroke-width="3"/>' if P!=0 else '')
 marks=''.join(f'<line x1="{340+500*s.get("start_mm",0)/max(L,1):.2f}" y1="126" x2="{340+500*s.get("start_mm",0)/max(L,1):.2f}" y2="147" stroke="#147d92"/>' for s in data.get('segments',[]) if isinstance(s,dict))
 return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 280" role="img" aria-label="Seção U ou Ue e viga biapoiada com carga informada">
 <rect width="920" height="280" fill="#fafbfc" rx="14"/>
 <path d="{path}" fill="none" stroke="#e87722" stroke-width="{T}" stroke-linejoin="round"/>
 <g font-family="Arial" font-size="14" fill="#25334a"><text x="25" y="25">Seção transversal</text><text x="20" y="260">h={escape(fmt(h))} · b={escape(fmt(b))} · t={escape(fmt(t))} · D={escape(fmt(lip))} mm</text>
 <text x="340" y="25">Vão e posição da resultante</text><text x="520" y="195">L = {escape(fmt(L))} mm</text><text x="{px-40}" y="65">P = {escape(fmt(data['P_uls']/1000))} kN</text><text x="350" y="240">q = {escape(fmt(data['q_uls']))} kN/m · x = {escape(fmt(a))} mm</text></g>
 <line x1="340" y1="140" x2="840" y2="140" stroke="#34455f" stroke-width="5"/>
 <path d="M340 143 l-10 18 h20 z M840 143 l-10 18 h20 z" fill="none" stroke="#34455f" stroke-width="2"/>
 {arrow}{marks}
 <text x="340" y="265" font-family="Arial" font-size="12" fill="#667085">Esquema dinâmico. Telha não considerada como travamento. Trechos em azul.</text></svg>'''
