"""Explicit isolated application transition; no automatic input/history migration."""
import copy
import math
from .ue_member_application import KINDS,LABELS,TEXT,apply


def render_choice(st,data,key,load):
    current=data.get('member_application','purlin')
    st.caption('Aplicação ativa da fonte própria: '+LABELS[current]+'.')
    proposed=st.selectbox('Aplicação da referência própria',KINDS,index=KINDS.index(current),
        format_func=LABELS.get,key=key+'_kind')
    if proposed==current:return False
    st.session_state.pop('result',None)
    st.warning('Proposta de aplicação ainda não aplicada. Cargas diretas continuam com os mesmos números locais, sem rotação. '
        'Na travessa, PP/CP por área serão verticais, vento horizontal e SC/P automáticos de cobertura inativos. '
        'Troca usa somente seção e vão já aplicados; uma proposta de geometria não aplicada não é consumida.')
    if st.button('Descartar proposta de aplicação própria',key=key+'_discard'):
        load(data);st.rerun()
    if st.button('Aplicar aplicação isolada da referência',key=key+'_apply'):
        try:new=apply(data,proposed)
        except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:st.error('Aplicação não alterada: '+str(exc))
        else:load(new);st.rerun()
    return True


def render_horizontal_limit(st,data,key):
    if data.get('member_application')!='wall_girt':return
    st.caption(TEXT)
    cfg=copy.deepcopy(data['wall_els'])
    st.markdown('**Critério da componente horizontal**')
    for field,label in [('normal_reference_mm','Comprimento de referência horizontal [mm]'),
                        ('normal_denominator','Denominador do limite horizontal')]:
        widget_key=key+'_'+field
        if widget_key not in st.session_state:
            st.session_state[widget_key]=None if cfg[field] is None else float(cfg[field])
        # A nullable widget must keep a None default on every run. Otherwise
        # clearing a previously numeric value silently restores that value.
        cfg[field]=st.number_input(label,value=None,key=widget_key,format='%.6f')
    cfg['origin']=st.text_input('Origem do critério horizontal',value=cfg['origin'],key=key+'_origin')
    st.caption('Comprimento de referência vazio usa o vão do modelo. Valor explícito não altera o vão, os esforços ou FLT. '
               'Critério declarado, não prescrição normativa automática. Critério vertical armazenado permanece separado e não recebe novo índice.')
    # The inherited vertical diagnostic is preserved in the saved calculation.
    # An invalid imported draft must remain repairable, not hidden behind a
    # horizontal-only editor or silently replaced by a default.
    def valid_positive(value):
        return type(value) in (int,float) and math.isfinite(value) and value>0
    invalid_vertical=(not valid_positive(cfg['vertical_denominator']) or
        (cfg['vertical_reference_mm'] is not None and not valid_positive(cfg['vertical_reference_mm'])))
    if invalid_vertical:
        st.warning('Dados verticais preservados inválidos para o diagnóstico legado. Corrija os campos abaixo; isso não libera ELS vertical nem altera o critério horizontal.')
        for field,label in [('vertical_reference_mm','Reparar referência vertical preservada [mm]'),
                            ('vertical_denominator','Reparar denominador vertical preservado')]:
            widget_key=key+'_'+field
            if widget_key not in st.session_state:
                st.session_state[widget_key]=None if cfg[field] is None else float(cfg[field])
            cfg[field]=st.number_input(label,value=None,key=widget_key,format='%.6f')
    data['wall_els']=cfg
