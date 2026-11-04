"""Fail-closed fixed-case boundary. No project imports, cache or input dictionary."""
from pathlib import Path
import copy
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
BUNDLE_SHA256 = '46688d981b9bb6bb855b4f04ad5286bc03111b16724fa5893ca5b591e6dc184a'
THICKNESSES = (1.5, 2., 2.25, 2.65, 3., 3.35)
LENGTHS = (3000., 4000., 5000., 6000.)
FACTORS = (1., .01)
FLAGS = dict(physical_design_approved=False, whole_member_approved=False, NBR_design_check=False)
WARNING = ('Pesquisa isolada: não é dimensionamento NBR nem resultado do projeto atual. '
           'O índice longitudinal é condicional e usa um piso algébrico conservador; '
           'não representa capacidade literal publicada nem limite físico universal. '
           'Hipóteses para cargas e apoios reais, cisalhamento e suas interações, '
           'estabilidade, serviço, ligações e produto real permanecem pendentes.')
SCOPE = ('Somente seis geometrias próprias Ue100×50×17, ri=t, 209 nós, sem furos; '
         'vãos de 3, 4, 5 ou 6 m. Flexão biapoiada, garfos torcionais, empenamento livre, '
         'Vlasov linear com Saint-Venant e empenamento. Sem contato/rigidez da telha '
         'ou travamento intermediário. Carga vertical uniforme no CG, com excentricidade '
         'horizontal ao centro de cisalhamento e altura relativa nula na geometria inicial.')
LOAD_NOTE = ('PP isolado com coeficiente 1 não é combinação AISI. O controle a 1% '
             'é somente teste matemático de homogeneidade, não carga real ou limiar de pequeno giro.')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle():
    """Check uncached bytes on every active rerun, before importing the kernel."""
    manifest_path = ROOT / 'BUNDLE_MANIFEST.json'
    if _sha(manifest_path) != BUNDLE_SHA256:
        raise ValueError('Manifesto da pesquisa AISI alterado; resultado retirado.')
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest['files'].items():
        if _sha(ROOT / name) != digest:
            raise ValueError('Fonte da pesquisa AISI alterada: ' + name)
    return manifest


def selection(thickness, length, factor):
    values = []
    for name, value, allowed in [('espessura', thickness, THICKNESSES),
                                  ('vão', length, LENGTHS), ('carga', factor, FACTORS)]:
        if type(value) not in (int, float) or not math.isfinite(value) or value not in allowed:
            raise ValueError('Escolha AISI fora dos casos congelados: ' + name)
        values.append(float(value))
    return dict(thickness_mm=values[0], length_mm=values[1], load_factor=values[2])


def _source(chosen):
    rows = json.loads((ROOT / 'inputs/elastic_inputs.json').read_text())['profiles']
    row = next(r for r in rows if r['thickness_mm'] == chosen['thickness_mm'])
    records = json.loads((ROOT / 'RESULTS.json').read_text())['records']
    frozen = next(r for r in records if all(r[k] == v for k, v in chosen.items()))
    return row, frozen


def _envelope(chosen, row, record, manifest):
    return dict(schema='tercas_isolated_AISI2024_fixed_case_v1',
        selection=copy.deepcopy(chosen), record=copy.deepcopy(record),
        fixed_input_snapshot=copy.deepcopy(row),
        snapshot_kind='Isolated research, not a project input/result or AISI design combination',
        follows_project_inputs=False, project_result=False, project_counts_modified=False,
        NBR_capacities_used=False, source_editions_mixed=False,
        material_route=dict(E_MPa=203000., G_MPa=78000., nu=.3, Fy_MPa=250., phi_b=.9, phi_B=.9, beta=1., Cb=1.),
        source_material_note='Elastic FSM source E=200000 MPa, nu=0.30; only elastic criticals scaled by 1.015. No NBR strength is used.',
        provenance=dict(bundle_sha256=BUNDLE_SHA256, manifest=copy.deepcopy(manifest),
            source_pins=json.loads((ROOT / 'SOURCE_PINS.json').read_text()),
            material_scaling=json.loads((ROOT / 'MATERIAL_SCALING.json').read_text()),
            official_reference='https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf'),
        warnings=[WARNING, SCOPE, LOAD_NOTE], **FLAGS)


def evaluate(thickness, length, factor):
    chosen = selection(thickness, length, factor)
    manifest = verify_bundle()
    row, frozen = _source(chosen)
    from .aisi_candidate import assess
    record = assess(copy.deepcopy(row), chosen['length_mm'], chosen['load_factor'])
    if canonical(record) != canonical(frozen):
        raise ValueError('Resultado AISI difere do registro congelado; cálculo não disponibilizado.')
    return _envelope(chosen, row, record, manifest)


def validate_snapshot(snapshot, thickness, length, factor):
    """Compare saved evidence; do not recalculate or repair stale historical results."""
    chosen = selection(thickness, length, factor)
    manifest = verify_bundle()
    row, frozen = _source(chosen)
    if canonical(snapshot) != canonical(_envelope(chosen, row, frozen, manifest)):
        raise ValueError('Snapshot AISI incompatível ou alterado; calcule explicitamente outra vez.')
    return True


def export_json(snapshot, thickness, length, factor):
    validate_snapshot(snapshot, thickness, length, factor)
    return json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False)
