"""New recovery QA of every frozen normal branch and both transverse floors.

Constant actions are synthetic mathematical boundary cases, not member approval.
The independent providers, not test-supplied capacity dictionaries, are consumed.
"""
from tercas import en_ue_catalog_capacity_reference as composed


def test_all_83_real_pinned_sources_and_signed_boundaries(monkeypatch):
    from tercas import en_ue_qualified_library as normal
    from tercas import en_ue_shear as shear
    from tercas import en_signed_partial_interaction as signed

    def forbidden(*args, **kwargs):
        raise AssertionError('Reading frozen authorities must not rebuild sections')

    monkeypatch.setattr(normal, 'build_qualified_component_sections', forbidden)
    monkeypatch.setattr(shear, 'build_catalog_shear_capacity', forbidden)
    available = missing = 0
    for index in range(83):
        source = normal.qualified_reference(index)
        digest = source['qualified_content_sha256']
        ref = composed.qualified_reference(index, digest)
        binding = {key: ref[key] for key in (
            'catalog_index', 'profile_id', 'nominal_identity_sha256', 'nodes_sha256',
            'component_sections_sha256', 'material', 'action_convention')}
        binding.update(source_sha256='2'*64, case_id='synthetic-boundary',
            segment_id='catalogue-'+str(index))
        kwargs = dict(catalog_index=index, component_sections_sha256=digest,
            source_binding=binding)
        for branch in signed.BRANCHES:
            axis = branch.split('_')[0]
            positive = branch.endswith(('positive', 'tension'))
            floor = ref['signed_capacity_floor'][branch]
            fields = {key:[0] for key in signed.ACTIONS}
            fields[axis] = [(floor if floor is not None else 1) * (1 if positive else -1)]
            if axis != 'N':fields[axis+'_original'] = fields[axis][:]
            result = signed.polynomial_bound(fields, **kwargs)
            signed.validate_polynomial_bound(result, fields, **kwargs)
            assert all(result[key] is False for key in signed.FALSE_FLAGS)
            if floor is None:
                missing += 1
                assert result['status'] == 'pending_required_signed_capacity'
                assert result['index_upper'] is None
                assert result['missing_branches'] == [branch]
            else:
                available += 1
                assert result['status'] == 'sufficient'
                assert result['index_upper'] == 1
                assert result['required_branches'] == [branch]
        for axis, name in (('Vstrong', 'strong'), ('Vweak', 'weak')):
            fields = {key:[0] for key in signed.ACTIONS}
            fields[axis] = [ref['shear_capacity_lower_N'][name]]
            result = signed.polynomial_bound(fields, **kwargs)
            assert result['index_upper'] == result['shear_ratio_upper'] == 1
            assert result['status'] == 'sufficient'
            assert result['required_branches'] == []
            assert result['separate_EN_6_1_6_required'] is True
            assert result['whole_member_approved'] is False
    assert (available, missing) == (400, 98)
