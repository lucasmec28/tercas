from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_no_geometry_inputs_needed_for_conventional_route():
 a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
 assert not a.exception
 labels=[n.label for n in a.number_input]
 assert not any(x.startswith(('am —','bm —','cm —')) for x in labels)
 next(x for x in a.number_input if x.label=='q paralelo ELU [kN/m]').set_value(.01)
 next(x for x in a.number_input if x.label=='Mdist,y distorcional — My positivo — alma comprimida [kN·m]').set_value(5.)
 a.button[1].click().run(timeout=30)
 assert not a.exception
 assert not a.error
 result=a.session_state.result
 cap=result['inclination_evidence']['ELU']['weak_axis_capacities']['positive']
 assert cap['MRd_Nmm']>0
 assert cap['automatic_inputs']['mean_line']['cm_mm']==9.4
 assert cap['automatic_inputs']['mean_line_conversion_verified']
 assert result['input_data']['properties']['ri_mm']==1.2
 assert result['inclination_evidence']['ELU']['provisional_hypothesis']
