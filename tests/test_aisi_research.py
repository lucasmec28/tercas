"""Fixed cases, independent packaging and fail-closed provenance."""
import ast,copy,itertools,json,shutil
import numpy as np
import pytest
from tercas.aisi_research import adapter as a, aisi_candidate as kernel
from tercas.aisi_research.panel import technical
CASES=list(itertools.product(a.THICKNESSES,a.LENGTHS,a.FACTORS))
@pytest.mark.parametrize('t,L,f',CASES)
def test_all_48_records_exact(t,L,f):
    result=a.evaluate(t,L,f)
    frozen=next(r for r in json.loads((a.ROOT/'RESULTS.json').read_text())['records'] if r['thickness_mm']==t and r['length_mm']==L and r['load_factor']==f)
    assert a.canonical(result['record'])==a.canonical(frozen)
    assert a.validate_snapshot(result,t,L,f)
    assert json.loads(a.export_json(result,t,L,f))==result
    for obj in [result,result['record']]:assert all(obj[k] is False for k in a.FLAGS)
    assert result['follows_project_inputs'] is False and result['NBR_capacities_used'] is False
@pytest.mark.parametrize('pos,bad',[(i,v) for i in range(3) for v in [True,False,None,'1',[],{},float('nan'),float('inf'),-1,0]])
def test_invalid_selection(pos,bad):
    args=[1.5,3000.,1.];args[pos]=bad
    with pytest.raises(ValueError):a.evaluate(*args)
@pytest.mark.parametrize('args',[(1.2,3000,1),(1.6,3000,1),(3.35,3001,1),(1.5,4500,1),(1.5,3000,.5),(1.5,3000,.01001)])
def test_unqualified_cases(args):
    with pytest.raises(ValueError):a.evaluate(*args)
def test_exact_domain_and_material():
    records=json.loads((a.ROOT/'RESULTS.json').read_text())['records']
    assert len(records)==48
    assert set((r['thickness_mm'],r['length_mm'],r['load_factor']) for r in records)==set(CASES)
    assert all(r['material']==dict(E_MPa=203000.,G_MPa=78000.,nu=.3,Fy_MPa=250.) for r in records)
def test_kernel_only_relative_import_changed():
    old=(a.ROOT/'provenance/aisi_candidate.py').read_text();new=(a.ROOT/'aisi_candidate.py').read_text()
    assert new==old.replace('from vendor.section import load_profile','from .vendor.section import load_profile')
    assert {n.name:ast.dump(n) for n in ast.parse(old).body if isinstance(n,ast.FunctionDef)}=={n.name:ast.dump(n) for n in ast.parse(new).body if isinstance(n,ast.FunctionDef)}
@pytest.mark.parametrize('name',['BUNDLE_MANIFEST.json']+list(a.verify_bundle()['files']))
def test_every_pin_fail_closed(monkeypatch,tmp_path,name):
    shutil.copytree(a.ROOT,tmp_path/'bundle',ignore=shutil.ignore_patterns('__pycache__'))
    monkeypatch.setattr(a,'ROOT',tmp_path/'bundle');p=a.ROOT/name;p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError):a.evaluate(1.5,4000.,1.)
def test_missing_source(monkeypatch,tmp_path):
    shutil.copytree(a.ROOT,tmp_path/'bundle',ignore=shutil.ignore_patterns('__pycache__'))
    monkeypatch.setattr(a,'ROOT',tmp_path/'bundle');(a.ROOT/'inputs/elastic_inputs.json').unlink()
    with pytest.raises(OSError):a.evaluate(1.5,4000.,1.)
@pytest.mark.parametrize('field',list(a.FLAGS)+['follows_project_inputs','warnings','project'])
def test_modified_snapshot_not_exported(field):
    result=a.evaluate(1.5,4000.,1.);result[field]=True
    with pytest.raises(ValueError):a.export_json(result,1.5,4000.,1.)
@pytest.mark.parametrize('where,key,value',[('record','H4_ratio_upper',.001),('selection','length_mm',3000),('provenance','bundle_sha256','fake')])
def test_nested_snapshot_mutation(where,key,value):
    result=a.evaluate(1.5,4000.,1.);result[where][key]=value
    with pytest.raises(ValueError):a.export_json(result,1.5,4000.,1.)
def test_changed_choices_no_reuse():
    result=a.evaluate(1.5,4000.,1.)
    for args in [(2.,4000.,1.),(1.5,3000.,1.),(1.5,4000.,.01)]:
        with pytest.raises(ValueError):a.export_json(result,*args)
def test_no_mutable_return_sharing():
    first=a.evaluate(1.5,4000,1);second=a.evaluate(1.5,4000,1);first['record']['material']['E_MPa']=1
    assert second['record']['material']['E_MPa']==203000.
def test_runtime_drift_rejected(monkeypatch):
    monkeypatch.setattr(kernel,'E',200000.)
    with pytest.raises(ValueError,match='difere'):a.evaluate(1.5,4000.,1.)
@pytest.mark.parametrize('v',[True,0.,-1.,float('nan'),float('inf')])
def test_kernel_bad_scalar(v):
    with pytest.raises(ValueError):kernel.flexural_floor(v,1,1,1)
@pytest.mark.parametrize('beta',[0.,.4,2.,float('nan')])
def test_kernel_beta(beta):
    with pytest.raises(ValueError):kernel.flexural_floor(1,1,1,1,beta)
def test_domain_and_10000_floor_comparisons():
    with pytest.raises(ValueError):kernel.flexural_floor(1,1e-6,1/26,1)
    with pytest.raises(ValueError):kernel.flexural_floor(1,1,1,1/26)
    assert kernel.flexural_floor(1,1,1/25,1/25)['lambda_local_real_sufficient_upper']==5
    rng=np.random.default_rng(91823)
    for _ in range(10000):
        My=10**rng.uniform(3,9);Mp=My*rng.uniform(1,3);cre=My*10**rng.uniform(-4,3)
        crl=My*10**rng.uniform(np.log10(.04),3);crd=My*10**rng.uniform(np.log10(.04),3)
        floor=kernel.flexural_floor(My,cre,crl,crd);exact=kernel.full_DSM(My,Mp,cre,crl,crd,*rng.uniform(0,1,2))
        for k,e in [('Mne_floor_Nmm','Mne'),('Mnl_floor_Nmm','Mnl'),('Mnd_floor_Nmm','Mnd'),('Mn_floor_Nmm','Mn')]:assert floor[k]<=exact[e]*(1+1e-14)
def test_small_values_not_displayed_zero():
    records=json.loads((a.ROOT/'RESULTS.json').read_text())['records']
    values=[abs(r['required_midspan']['phi_rad']) for r in records]+[abs(r['declared_uniform_force_N_mm'][1]) for r in records]
    assert min(values)>0 and float(technical(min(values)))>0
    assert float(technical(min(values)))==pytest.approx(min(values),rel=1e-9)
def test_no_project_imports_or_state():
    for name in ['adapter.py','panel.py']:
        text=(a.ROOT/name).read_text()
        assert not any(word in text for word in ['last_input','session_state.result','session_state.base','complete_result','render_results','from tercas.application'])
    assert 'MRd_Nmm' not in (a.ROOT/'inputs/elastic_inputs.json').read_text()
