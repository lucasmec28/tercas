"""Release identification is descriptive, not a calculation or approval flag."""
from tercas.release_info import RELEASE_ID, RELEASE_CAPTION


def test_release_label_has_no_claim_of_structural_approval():
    assert RELEASE_ID == 'cobertura-familia-Pierin-Leff-20261106-r10'
    assert RELEASE_ID in RELEASE_CAPTION
    assert 'não é homologação estrutural' in RELEASE_CAPTION
    assert 'Critérios parciais' in RELEASE_CAPTION
