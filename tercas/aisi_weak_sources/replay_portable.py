"""Portable replay without app/candidate/research-source import paths."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parent
runhash=hashlib.sha256((ROOT/'weak_capacity.py').read_bytes()).hexdigest()
(ROOT/'PORTABLE_REPLAY.json').write_text(json.dumps(dict(passed=False,status='RUNNING',consumer_sha256=runhash))+'\n')
folder=Path(tempfile.mkdtemp(prefix='aisi_weak_portable_'))/'renamed_reference_bundle'
shutil.copytree(ROOT,folder,ignore=shutil.ignore_patterns('__pycache__','PORTABLE_*'))
commands=['weak_capacity.py','test_weak_capacity.py','check_material_scaling.py','independent_review/test_consumer_independent.py','independent_review/check_material_independent.py'];rows=[]
for script in commands:
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',PYTHONPATH='')
 p=subprocess.run([sys.executable,str(folder/script)],cwd='/tmp',env=env,text=True,capture_output=True)
 log=ROOT/('PORTABLE_'+script.replace('/','_')+'.log');log.write_text(p.stdout+p.stderr)
 rows.append(dict(script=script,returncode=p.returncode,log=log.name,passed=p.returncode==0))
 if p.returncode:
  (ROOT/'PORTABLE_REPLAY.json').write_text(json.dumps(dict(passed=False,status='FAILED',consumer_sha256=runhash,commands=rows),indent=2)+'\n')
  raise RuntimeError(rows[-1])
for name in ['RESULTS.json','SUMMARY.json','MATERIAL_SCALING.json','independent_review/MATERIAL_INDEPENDENT.json']:
 a=json.loads((ROOT/name).read_text());b=json.loads((folder/name).read_text());assert a==b,name
preservation=json.loads((ROOT/'SOURCE_PRESERVATION.json').read_text());checks={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in preservation['sources'].items()};assert all(checks.values())
out=dict(passed=True,consumer_sha256=runhash,commands=rows,exact_json_replays=['RESULTS.json','SUMMARY.json','MATERIAL_SCALING.json','independent_review/MATERIAL_INDEPENDENT.json'],source_preservation=checks,source_candidate_imported=False,temporary_replay=str(folder))
(ROOT/'PORTABLE_REPLAY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
