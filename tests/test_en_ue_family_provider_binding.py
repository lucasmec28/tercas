"""Non-numerical source-binding tests: no section solver or private inputs."""
import copy
import pytest
from tercas import en_ue_family_provider as p
from tercas import pierin_ue_registry as registry


@pytest.fixture
def isolated_sources(tmp_path,monkeypatch):
    # Simulate trusted local source bytes, without modifying production files.
    for relative in p.TECHNICAL_SOURCES:
        path=tmp_path/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('original technical source: '+relative)
    (tmp_path/'release_info.py').write_text('RELEASE = "before"')
    (tmp_path/'ui_family.py').write_text('CAPTION = "before"')
    monkeypatch.setattr(p,'_SOURCE_ROOT',tmp_path)
    monkeypatch.setattr(registry,'select_new_study',lambda index,include_routes=False:
        dict(catalog_id='synthetic',dimensions_mm={'h':125,'bf':50,'lip':17,'t':2},
             published_properties={'ri_mm':2}))
    calls=[]
    def build(index,*,fyb_MPa,gamma_M0,material_declaration):
        calls.append(index)
        return dict(schema='synthetic-no-numerics',catalog_index=index,
                    material={'fyb_MPa':fyb_MPa,'gamma_M0':gamma_M0},
                    material_declaration=copy.deepcopy(material_declaration),
                    components={'synthetic':{'capacity':123}},content_sha256='replaced')
    monkeypatch.setattr(p.kernel,'build',build)
    p._cached.cache_clear()
    yield tmp_path,calls
    p._cached.cache_clear()


def section():
    return p.section(26,fyb_MPa=300,material_declaration={
        'name':'synthetic','fu_MPa':400,'source':'test fixture'})


@pytest.mark.parametrize('relative',['release_info.py','ui_family.py','unrelated.json'])
def test_irrelevant_change_invalidates_cache_not_saved_identity(isolated_sources,relative):
    root,calls=isolated_sources
    saved=section(); initial_cache=p._source_key(); initial_technical=p._technical_source_key()
    (root/relative).write_text('changed unrelated source')
    assert p._source_key()!=initial_cache
    assert p._technical_source_key()==initial_technical
    assert section()==saved
    assert len(calls)==2  # Rebuild happened, but the stable result is identical.
    assert p.verify(saved)
    assert 'cache_source_key' not in saved['provider_binding']


@pytest.mark.parametrize('relative',[
    'en_ue_family_kernel.py','catalog_torsion_section.py',
    'three_girt_en_normal/en1993_normal_components.py','torsion_vlasov/intervals.py',
    'core/catalogo_documentado.json','data/pierin_2013_weak_reference.json'])
def test_technical_change_rejects_previous_certificate(isolated_sources,relative):
    root,calls=isolated_sources
    saved=section(); previous=p._technical_source_key()
    (root/relative).write_text('changed formula, convention or input data')
    assert p._technical_source_key()!=previous
    # Even this synthetic builder returning unchanged numbers cannot conceal a
    # technical source change. Canonical binding must match the local sources.
    with pytest.raises(ValueError,match='differs'):p.verify(saved)
    assert len(calls)==2


def test_resealed_payload_still_rejected(isolated_sources):
    saved=section()
    saved['components']['synthetic']['capacity']+=1
    saved.pop('content_sha256');saved['content_sha256']=p._sha(saved)
    with pytest.raises(ValueError,match='differs'):p.verify(saved)


def test_technical_identity_is_not_supplied_by_certificate(isolated_sources):
    saved=section()
    saved['provider_binding']['source_content_sha256']='0'*64
    saved.pop('content_sha256');saved['content_sha256']=p._sha(saved)
    with pytest.raises(ValueError,match='differs'):p.verify(saved)


def test_missing_technical_source_fails_closed(isolated_sources):
    root,_=isolated_sources
    saved=section();(root/'torsion_vlasov/intervals.py').unlink()
    with pytest.raises(FileNotFoundError):p.verify(saved)
