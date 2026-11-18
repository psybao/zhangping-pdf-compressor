import json,time
from pathlib import Path
from unittest.mock import patch
from engine import quick_estimate,CompressionError

base=Path(__file__).parent;rows=[]
with patch('engine.Optimizer.optimize_document',side_effect=AssertionError('estimation must not compress')),patch('engine.pikepdf.Pdf.save',side_effect=AssertionError('estimation must not write PDF')),patch('engine.fingerprint',side_effect=AssertionError('estimation must not hash whole file')):
    start=time.perf_counter()
    for name in ['text','scan','mixed','large','multipage','transparency','compressed']:
        source=base/'output/fixtures'/f'{name}.pdf'
        for q in ['HIGH','MEDIUM','LOW']:
            r=quick_estimate(source,q);assert 0<r.lower<=r.after<=r.upper<=source.stat().st_size
        for target in [512000,1048576,2097152,1]:
            r=quick_estimate(source,target=target);assert 0<r.lower<=r.after<=r.upper<=min(target,source.stat().st_size)
        rows.append({'file':name,'bytes':source.stat().st_size,'estimated':r.after})
    seconds=time.perf_counter()-start
for name in ['empty','encrypted','broken']:
    try:quick_estimate(base/'output/fixtures'/f'{name}.pdf');raise AssertionError(f'{name} not rejected')
    except CompressionError:pass
(base/'output/quick_estimate_test.json').write_text(json.dumps({'passed':True,'cases':49,'seconds':seconds,'checks':['no complete compression','no PDF writes','no full-file hashing','quality and target modes','preview and range never exceed target','invalid PDF errors'],'rows':rows},indent=2),encoding='utf-8')
print(f'49 metadata-only estimate cases passed in {seconds:.4f}s; target and range hard caps verified')
