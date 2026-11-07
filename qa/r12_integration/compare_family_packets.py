"""Compare synthetic R11/R12 results without solving or migrating either.

Pass the verified R11 saved-fields directory and freshly generated R12 directory.
The comparison is exact JSON equality, not a tolerance or a reclassification.
"""
import argparse
import gzip
import json
from pathlib import Path
from tercas import isolated_en_ue_family_application as app
from tercas import pierin_ue_registry as registry

PACKETS=('input_data','input_fingerprint','input_snapshot','ELS','FLT_segments',
    'NBR_branches','section_checks','direct_self_weight_evidence','inclination_evidence',
    'torsion_evidence','aisi_torsion_component','roof_top_load_evidence',
    'roof_top_nbr_component','ue_catalog_reference_evidence',
    'ue_catalog_nbr_bending_evidence','nbr_ue_family_application',
    'isolated_combined_service_component')


def read(folder,index):
    with gzip.open(folder/(str(index)+'.json.gz')) as stream:return json.load(stream)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('old',type=Path);parser.add_argument('new',type=Path)
    args=parser.parse_args();rows=[];qualified=0
    for index in registry.new_study_indices():
        old,new=read(args.old,index),read(args.new,index)
        mismatches=[key for key in PACKETS if old.get(key)!=new.get(key)]
        assert not mismatches,(index,mismatches)
        a=old[app.FIELD]['records'][0]['check'];b=new[app.FIELD]['records'][0]['check']
        if a['applicability']['qualified']:
            assert a==b,index
            qualified+=1
        rows.append(dict(index=index,all_17_packets_identical=True,
            original_qualified_EN_identical=a==b if a['applicability']['qualified'] else None))
    assert len(rows)==66 and qualified==36
    out=dict(kind='EXACT_SYNTHETIC_R11_R12_PACKET_COMPARISON',profiles=66,
        packet_keys=PACKETS,packets_identical_in_all_profiles=True,
        original_qualified_EN_checks_identical=qualified,records=rows,
        member_solver_used=False,global_approval_inferred=False)
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
