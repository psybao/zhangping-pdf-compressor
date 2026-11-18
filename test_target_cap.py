import json
from pathlib import Path
from dataclasses import replace
from engine import Engine,quick_estimate,CompressionError
root=Path(__file__).parent;fixtures=root/'output/fixtures';dest=root/'output/target_cap_test';dest.mkdir(exist_ok=True)
engine=Engine(root/'output/test_cache');rows=[]
for name in ['text','scan','mixed']:
    source=fixtures/f'{name}.pdf';preview=quick_estimate(source,target=2097152)
    assert preview.after<=2097152 and preview.upper<=2097152
    r=engine.compress(source,target=2097152);assert r.met
    out=engine.publish(r,dest);assert out.stat().st_size<=2097152
    rows.append(dict(file=name,preview=preview.after,range_max=preview.upper,actual=out.stat().st_size))
r=engine.compress(fixtures/'text.pdf',target=1);assert not r.met
try:engine.publish(r,dest);raise AssertionError('oversized result published')
except CompressionError:pass
r=engine.compress(fixtures/'text.pdf',target=2097152)
before=set(dest.iterdir())
try:engine.publish(replace(r,cached=fixtures/'mixed.pdf'),dest);raise AssertionError('changed cache bypassed byte limit')
except CompressionError:pass
assert set(dest.iterdir())==before
(root/'output/target_cap_tests.json').write_text(json.dumps({'passed':True,'target':2097152,'rows':rows,'unmet_refused':True,'actual_bytes_rechecked':True},indent=2),encoding='utf-8')
print('PASS: 2MB preview/range/output caps; unmet target refused; actual bytes checked before publication')
