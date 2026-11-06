import copy
from decimal import Decimal, localcontext, ROUND_FLOOR
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path

import pytest

from tercas import en_ue_shear as s
from tercas.catalogs import catalog_entry, entries
from tercas.catalog_torsion_section import nominal_channel_nodes

IDS=tuple(range(83))


def independent_floor(h,t,n):
    """Independent squared-rational branch test and reduced symbolic formulas."""
    h,t=F(str(h)),F(str(t));k=F(173,500);fy=F(250);E=F(210000)
    l2=k*k*h*h*fy/(t*t*E)
    def dec(q):return Decimal(q.numerator)/Decimal(q.denominator)
    with localcontext() as ctx:
        ctx.prec=90
        if l2<=F(83,100)**2: cap=dec(n*h*t*F(145))
        elif l2<F(7,5)**2:cap=dec(n*t*t*F(120)/k)/(dec(fy/E)).sqrt()
        else:cap=dec(n*t*t*t*F(335,2)*E/(k*k*h*fy))
        return int(cap.to_integral_value(rounding=ROUND_FLOOR))


def reseal(record):
    record.pop('content_sha256',None);record['content_sha256']=s._sha(record)
    return record


@pytest.mark.parametrize('index',IDS)
def test_all_83_independent_symbolic_values_and_coherent_identity(index):
    c=s.build_catalog_shear_capacity(index)
    e=catalog_entry(index);d=e['dimensions_mm'];t=d['t'];ri=e['published_properties']['ri_mm']
    assert e['family']=='Ue'
    for axis,dimension,n in [('strong','h',1),('weak','bf',2)]:
        hw=Decimal(str(d[dimension]))-Decimal(str(t))
        assert c['shear_capacity_lower_N'][axis]==independent_floor(hw,t,n)
        assert c['shear_capacity_lower_N'][axis]>0
        geom=c['shear_capacity_geometry'][axis]
        assert geom['walls']==n
        assert geom['hw_mm']==float(hw)==geom['sw_upper_mm']
        lam=.346*float(hw)/t*math.sqrt(250/210000)
        assert geom['lambda_upper']>=lam-2e-15
        assert geom['fbv_lower_MPa']<=s.table61_unstiffened_fbv(lam)+1e-12
        assert c['shear_capacity_lower_N'][axis]<=n*float(hw)*t*s.table61_unstiffened_fbv(lam)+1e-10
    nodes=nominal_channel_nodes(h_mm=d['h'],bf_mm=d['bf'],lip_mm=d['lip'],t_mm=t,ri_mm=ri,arc_segments=32)
    b=c['source_binding']
    assert b['nodes_sha256']==s._sha(nodes)
    assert b['nominal_identity_sha256']==s._sha(b['nominal_identity'])
    assert b['profile_id']=='OWN_PIERIN_NOMINAL_'+e['id']+'_'+b['nominal_identity_sha256'][:16]
    assert b['material']==s.MATERIAL
    assert s.validate_saved(c,{**b,'nodes_xy_mm':nodes})
    assert c['applicability']['satisfied'] is True
    assert all(c[key] is False for key in s.FALSE_FLAGS)
    assert c['shear_capacity_qualification']['inventory_sha256']==s.INVENTORY_SHA256
    assert c['shear_capacity_qualification']['method']==s.METHOD


@pytest.mark.parametrize('point',[.83,1.4])
def test_literal_table_transitions_with_downward_not_interpolated_jumps(point):
    before=s.table61_unstiffened_fbv(math.nextafter(point,-math.inf))
    at=s.table61_unstiffened_fbv(point)
    after=s.table61_unstiffened_fbv(math.nextafter(point,math.inf))
    assert before>=at>=after
    if point==.83:
        assert at==145.
        assert after==120./math.nextafter(.83,math.inf)
        assert after<at-.4
    else:
        assert at==167.5/1.4/1.4
        assert before>at+.2


def test_fbv_nonincreasing_and_limits():
    xs=[0.,1e-100]+[i/1000 for i in range(1,5001)]+[1e10,1e100,1e308]
    ys=[s.table61_unstiffened_fbv(x) for x in xs]
    assert all(a>=b for a,b in zip(ys,ys[1:]))
    assert ys[0]==ys[1]==145.
    assert 0<=ys[-1]<1e-200
    assert s.table61_unstiffened_fbv(10)*4==pytest.approx(s.table61_unstiffened_fbv(5))


@pytest.mark.parametrize('bad',[True,False,None,'1',-1.,math.nan,math.inf,-math.inf])
def test_invalid_table_scalar(bad):
    with pytest.raises(ValueError):s.table61_unstiffened_fbv(bad)


def test_thickness_monotonicity_and_three_height_regimes():
    floors=[s._wall_floor(200,t/100,1)['capacity_floor_N'] for t in range(50,1001,5)]
    assert all(a<=b for a,b in zip(floors,floors[1:]))
    assert s._wall_floor(20,2,1)['capacity_floor_N']==2*s._wall_floor(10,2,1)['capacity_floor_N']
    # Medium branch exactly cancels h, unlike the slender branch.
    assert s._wall_floor(160,2,1)['capacity_floor_N']==s._wall_floor(200,2,1)['capacity_floor_N']
    assert s._wall_floor(400,2,1)['capacity_floor_N']<s._wall_floor(300,2,1)['capacity_floor_N']


def test_geometric_majorant_for_radii_not_a_single_size_analogy():
    for h,b,c,t in [(50,25,10,1.2),(100,50,17,2.),(300,100,25,4.75)]:
        for ri in [0.,t/2,t,1.5*t]:
            nodes=nominal_channel_nodes(h_mm=h,bf_mm=b,lip_mm=c,t_mm=t,ri_mm=ri,arc_segments=32)
            r=ri+t/2
            for axis,a,i,j in [('strong',h-t,50,83),('weak',b-t,50,17)]:
                k=1 if axis=='strong' else 0
                sw=abs(nodes[j][k]-nodes[i][k])
                assert sw==pytest.approx(a-2*r*(1-1/math.sqrt(2)),abs=1e-12)
                assert 0<sw<=a
                lower=s.table61_unstiffened_fbv(.346*a/t*math.sqrt(250/210000))
                actual=s.table61_unstiffened_fbv(.346*sw/t*math.sqrt(250/210000))
                assert lower<=actual
    # This mathematical lemma does not enroll arbitrary-radius certificates.
    c=s.qualified_reference(0);c['source_binding']['nominal_identity']['inner_radius_mm']=.6
    with pytest.raises(ValueError):s.verify_shear_capacity(reseal(c))


@pytest.mark.parametrize('path,value',[
    (('shear_capacity_lower_N','strong'),999999.),
    (('shear_capacity_lower_N','weak'),999999.),
    (('shear_capacity_qualification','support_stiffener_credit'),True),
    (('shear_capacity_qualification','lip_or_corner_resistance_credit'),True),
    (('shear_capacity_qualification','inventory_sha256'),'0'*64),
    (('shear_capacity_qualification','source_sha256'),'0'*64),
    (('shear_capacity_qualification','method'),'copied-normal-approval'),
    (('source_binding','nodes_sha256'),'0'*64),
    (('source_binding','thickness_mm'),1.5),
    (('normal_operators_qualified',),True),
    (('whole_member_approved',),True),
    (('runtime_release_approved',),True),
])
def test_adulteration_rehashed_still_rejected(path,value):
    c=s.qualified_reference(0);target=c
    for p in path[:-1]:target=target[p]
    target[path[-1]]=value
    with pytest.raises(ValueError):s.verify_shear_capacity(reseal(c))


def test_substitution_material_nodes_and_source_cannot_be_erased():
    a,b=s.qualified_reference(0),s.qualified_reference(1)
    with pytest.raises(ValueError):s.validate_saved(a,b['source_binding'])
    source=copy.deepcopy(a['source_binding']);source['material']['fyb_MPa']=350
    with pytest.raises(ValueError):s.validate_saved(a,source)
    source=copy.deepcopy(a['source_binding']);source['nodes_xy_mm']=[[0,0],[0,1],[1,1]]
    with pytest.raises(ValueError):s.validate_saved(a,source)
    with pytest.raises(ValueError):s.validate_saved(a,{})
    with pytest.raises(ValueError):s.validate_saved(a,None)
    a.pop('shear_capacity_qualification')
    with pytest.raises(ValueError):s.verify_shear_capacity(reseal(a))


@pytest.mark.parametrize('index',[True,0.,-1,83,100,208,None,'0'])
def test_nonqualified_rows_and_index_types(index):
    with pytest.raises(ValueError):s.qualified_reference(index)


@pytest.mark.parametrize('material',[{'fyb_MPa':350},{'E_MPa':200000},
    {'nu':.29},{'gamma_M0':1.1},{'fya_MPa':260},{'fy_MPa':250},{'nu':True}])
def test_material_variants_rejected(material):
    with pytest.raises(ValueError):s.build_catalog_shear_capacity(0,**material)


def test_no_rebuild_on_saved_read_and_no_normal_import(monkeypatch):
    c=s.qualified_reference(0);source=copy.deepcopy(c['source_binding'])
    def forbidden(*args,**kwargs):raise AssertionError('Saved read rebuilt a source')
    monkeypatch.setattr(s,'_derive',forbidden)
    import tercas.catalogs as cat
    import tercas.catalog_torsion_section as geo
    monkeypatch.setattr(cat,'catalog_entry',forbidden)
    monkeypatch.setattr(geo,'nominal_channel_nodes',forbidden)
    assert s.qualified_reference(0)==c
    assert s.verify_shear_capacity(c)
    assert s.validate_saved(c,source)


def test_inventory_is_immutable_and_unqualified_hashes_do_not_enroll(tmp_path,monkeypatch):
    good=s.qualified_reference(0)
    inventory=json.loads(s.INVENTORY_PATH.read_text())
    inventory['entries']['0']['shear_capacity_lower_N']['strong']+=1
    inventory['entries']['0']=reseal(inventory['entries']['0'])
    path=tmp_path/'changed.json';path.write_text(json.dumps(reseal(inventory)))
    monkeypatch.setattr(s,'INVENTORY_PATH',path);s._inventory.cache_clear()
    try:
        with pytest.raises(ValueError):s.verify_shear_capacity(good)
    finally:s._inventory.cache_clear()


def test_source_manifest_and_note_are_pinned():
    source=json.loads(s.SOURCE_PATH.read_text())
    assert s._verify_seal(source)==s.SOURCE_SHA256
    root=Path(__file__).resolve().parents[1]
    assert hashlib.sha256((root/source['qualification_note_path']).read_bytes()).hexdigest()==source['qualification_note_file_sha256']
    assert s.available_indices()==list(IDS)
    assert all(entries()[i]['family']=='Ue' for i in s.available_indices())


def test_caller_mutation_does_not_change_frozen_library():
    c=s.qualified_reference(0);c['shear_capacity_lower_N']['strong']=1
    assert s.qualified_reference(0)['shear_capacity_lower_N']['strong']!=1
    assert s.build_catalog_shear_capacity(0,**s.MATERIAL)==s.qualified_reference(0)


def test_catalogue_scalars_and_pierin_criticals_are_not_operands(monkeypatch):
    import tercas.catalogs as cat
    original=cat.catalog_entry
    def altered(index):
        e=original(index)
        for key in list(e['published_properties']):
            if key!='ri_mm':e['published_properties'][key]=-123456789.
        for key in list(e['critical_values']):e['critical_values'][key]=-987654321.
        return e
    monkeypatch.setattr(cat,'catalog_entry',altered)
    assert s.build_catalog_shear_capacity(19)==s.qualified_reference(19)


@pytest.mark.parametrize('changed',['ri','t','lip','h','bf'])
def test_current_nominal_changes_do_not_gain_frozen_qualification(monkeypatch,changed):
    import tercas.catalogs as cat
    original=cat.catalog_entry
    def altered(index):
        e=original(index)
        if changed=='ri':e['published_properties']['ri_mm']+=.1
        else:e['dimensions_mm'][changed]+=.1
        return e
    monkeypatch.setattr(cat,'catalog_entry',altered)
    with pytest.raises(ValueError):s.build_catalog_shear_capacity(19)
