"""Release identification is descriptive, not a calculation or approval flag."""
from tercas.release_info import RELEASE_ID, RELEASE_CAPTION


def test_release_label_has_no_claim_of_structural_approval():
    assert RELEASE_ID == 'componentes-Ue-ELS-MV-FLT-20261107-r11'
    assert RELEASE_ID in RELEASE_CAPTION
    assert 'não é homologação estrutural' in RELEASE_CAPTION
    assert 'Critérios parciais' in RELEASE_CAPTION
