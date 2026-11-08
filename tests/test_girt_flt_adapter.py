"""Isolated-girt resistance adapters, synthetic scalar-only calculation/replay."""
import copy
import json
import pytest
from test_wall_girt_own_isolated import data
from tercas import nbr_ue_family_application as app, ue_catalog_reference as own
from tercas import girt_flt_adapter as adapter, wall_girt_isolated as girt
from tercas import flt_height_effective as flt, flt_height_energy_floor as energy
from tercas.application import fingerprint
from tercas.resistance_effective_lengths import declare


def source(mode='direct',*,point=False,ly=None,lz=None):
    d=data(26,mode)
    if not point:d.update(P_uls=0.,P_sls=0.)
    L=d['L_mm']
    d=declare(d,Lx_mm=L,Ly_mm=ly or L,Lz_mm=lz or L,origin='Synthetic separate resistance lengths')
    r=dict(input_data=d,input_fingerprint=fingerprint(d),schema='NBR14762_one_span_v1',
           model_domain_evidence=dict(status='fixed_model_domain',conflict=False))
    if mode=='area':
        from tercas.batch import area_bundle
        b=area_bundle(d);r.update(schema='tercas_batch_results_v1',load_bundle=b,
            cases=[dict(combination=c) for c in b['combinations']])
    return own.attach_source(r)


def no_roof_or_ritz(monkeypatch):
    from tercas import roof_top_load,ltb_load_height
    monkeypatch.setattr(roof_top_load,'geometry',lambda *a,**k:pytest.fail('Girt used roof geometry'))
    monkeypatch.setattr(ltb_load_height,'refined',lambda *a,**k:pytest.fail('Girt invoked Ritz'))


@pytest.mark.parametrize('mode',['direct','area'])
def test_authentic_inventory_and_json_replay_without_mechanics(monkeypatch,mode):
    no_roof_or_ritz(monkeypatch)
    r=source(mode);before=copy.deepcopy(r)
    out=app.attach(r);ev=out[app.FIELD]
    assert ev['schema']==app.GIRT_SCHEMA
    assert ev['application_source_binding']['schema']==own.GIRT_SCHEMA
    assert ev['records']
    assert app.preserved(json.loads(json.dumps(out)))==ev
    assert r==before
    for row in ev['records']:
        binding=row['height_source']['girt_action_binding']
        assert binding['eligible'] and not binding['roof_geometry_used']
        assert binding['source_binding']==own.source_binding(r['input_data'])
        assert row['height_source']['actions']==row['actions']
    from tercas import nbr_family_panorama as panorama
    checks,binding=panorama.apply(out,[])
    assert binding and any(c['id'].endswith(':FLT:family') for c in checks)
    out['global_verification']=dict(checks=checks,**{panorama.BINDING:binding})
    panorama.validate_saved(out)
    assert not ev['whole_member_approved']
    # The native report reads/replays the saved scalar evidence only.
    import io
    from docx import Document
    from tercas.nbr_ue_family_ui import report
    doc=Document();report(doc,out);buf=io.BytesIO();doc.save(buf)
    reopened=Document(io.BytesIO(buf.getvalue()))
    assert reopened.tables and any('NBR' in p.text for p in reopened.paragraphs)
    assert any('Travessa isolada:' in p.text for p in reopened.paragraphs)


def test_documentary_uniform_and_qp_energy_use_real_local_lines(monkeypatch):
    no_roof_or_ritz(monkeypatch)
    r=source();row=app.attach(r)[app.FIELD]['records'][0]
    assert row['height_source']['elastic_reference_eligible']
    assert row['height_source']['method']==flt.METHOD
    r=source(point=True,lz=1800.)
    row=app.attach(r)[app.FIELD]['records'][0]
    assert not row['height_source']['elastic_reference_eligible']
    floor=row['height_energy_floor']
    assert floor['energy_floor']['method']==energy.POLICY_V3
    assert floor['energy_floor']['girt_action_binding']['eligible']
    assert floor['resistance_floor_eligible']
    assert floor['energy_floor']['physical_span_mm']==r['input_data']['L_mm']
    assert not floor['energy_floor']['demand_span_changed']
    sc=own.section_for(r['input_data'])['properties']['shear_center_xy_mm']
    cg=own.section_for(r['input_data'])['properties']['centroid_xy_mm']
    for a in row['actions']:
        if a['name']=='PP':
            assert a['height_above_SC_mm']==cg[1]-sc[1]
            assert a['x_from_SC_mm']==cg[0]-sc[0]
        else:
            assert a['height_above_SC_mm']==cg[1]+7.-sc[1]
            assert a['x_from_SC_mm']==cg[0]+3.-sc[0]


@pytest.mark.parametrize('mutation',['missing_line','old_roof_choice','disabled'])
def test_unadopted_lines_never_inherited(monkeypatch,mutation):
    no_roof_or_ritz(monkeypatch);r=source();d=r['input_data']
    if mutation=='missing_line':d['torsion_model']['load_lines']['EXTERNAL']['declared']=False
    elif mutation=='old_roof_choice':
        from tercas.torsion_study import blank_choice
        d['torsion_model']=blank_choice()
    else:d['torsion_model']['enabled']=False
    r['input_fingerprint']=fingerprint(d);r=own.attach_source(r)
    row=app.attach(r)[app.FIELD]['records'][0]
    assert not row['height_source']['elastic_reference_eligible']
    assert not row['height_source']['girt_action_binding']['eligible']
    assert row['load_position_by_axis']['normal']['classification']=='unknown'
    assert any(c['method']=='local' and c['index'] is not None for c in row['components'])
    assert all(c['index'] is None for c in row['components'] if c['route']=='own_rounded_contour' and c['method'] in ('FLT_reference','FLT_height_effective_reference','FLT_height_energy_floor'))


def test_ct_branch_and_no_roof_marker_mutation(monkeypatch):
    no_roof_or_ritz(monkeypatch);r=source();d=r['input_data']
    s=own.section_for(d);cg=s['properties']['centroid_xy_mm'];sc=s['properties']['shear_center_xy_mm']
    d['torsion_model']['load_lines']['EXTERNAL']['xy_from_CG_mm']=[sc[0]-cg[0],sc[1]-cg[1]]
    r['input_fingerprint']=fingerprint(d);r=own.attach_source(r);before=copy.deepcopy(d)
    row=app.attach(r)[app.FIELD]['records'][0]
    assert row['load_position_by_axis']['normal']['classification']=='shear_center'
    classical=next(c for c in row['components'] if c['route']=='own_rounded_contour' and c['method']=='FLT_reference')
    assert classical['index'] is not None
    assert d==before


def test_action_mutation_rejected_and_old_girt_pending_not_promoted(monkeypatch):
    no_roof_or_ritz(monkeypatch);r=source();d=r['input_data']
    old=copy.deepcopy(r);old[app.FIELD]=app._build(old)
    assert old[app.FIELD]['schema']==app.SCHEMA
    assert old[app.FIELD]['status']=='outside_isolated_N0_domain'
    assert app.preserved(old)==old[app.FIELD]
    fresh=app.attach(r);row=fresh[app.FIELD]['records'][0]
    a=copy.deepcopy(row['actions']);a[0]['height_above_SC_mm']+=1
    assert not adapter.qualify(d,a)['eligible']
    assert not flt.qualify_family_fresh(d,a)['elastic_reference_eligible']
    assert not energy.qualify_family(d,a,method=energy.POLICY_V3)['elastic_reference_eligible']
    fresh[app.FIELD]['records'][0]['actions']=a
    with pytest.raises(ValueError):app.preserved(fresh)
