import importlib.util,json,sys,time
import pikepdf
from pathlib import Path
from engine import Engine,inspect,validate
from pypdf import PdfReader
ROOT=Path(__file__).parent
def main():
    spec=importlib.util.spec_from_file_location('engine_before_performance',ROOT/'benchmarks/legacy_engine.py')
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    source=ROOT/'output/fixtures/parallel_images.pdf';rows=[]
    if not source.exists():
        with pikepdf.Pdf.new() as merged:
            for name in ['scan','mixed','large','compressed']:
                with pikepdf.open(ROOT/'output/fixtures'/f'{name}.pdf') as part:merged.pages.extend(part.pages)
            merged.save(source)
    text=''.join(p.extract_text() or '' for p in PdfReader(source).pages)
    for label,cls in [('before',old.Engine),('after',Engine)]:
        engine=cls();start=time.perf_counter();r=engine.compress(source);elapsed=time.perf_counter()-start
        validate(r.cached,inspect(source));assert ''.join(p.extract_text() or '' for p in PdfReader(r.cached).pages)==text
        rows.append({'version':label,'seconds':elapsed,'bytes':r.after,'workers':engine._workers(source) if hasattr(engine,'_workers') else 1})
        (ROOT/'output/performance_parallel.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(rows[-1],flush=True);engine.close()
if __name__=='__main__':main()
