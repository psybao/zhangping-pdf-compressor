"""Cold-cache performance evidence, with Python and codec call timings."""
import cProfile,json,pstats,time,sys,importlib.util
from pathlib import Path
from engine import Engine
ROOT=Path(__file__).parent
def run(label):
    cls=Engine
    if label=='before':
        spec=importlib.util.spec_from_file_location('engine_before_performance',ROOT/'benchmarks/legacy_engine.py')
        old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old);cls=old.Engine
    results=[]
    for name,target in [('scan',None),('scan',2097152),('mixed',512000)]:
        engine=cls();prof=cProfile.Profile();start=time.perf_counter()
        prof.enable();r=engine.compress(ROOT/'output/fixtures'/f'{name}.pdf',target=target);prof.disable()
        seconds=time.perf_counter()-start
        stats=pstats.Stats(prof)
        codecs=[{'function':key[2],'calls':v[1],'cumulative_seconds':v[3]} for key,v in stats.stats.items() if key[2] in ['_encode_jp2','_encode_jpeg','psnr','fingerprint','validate']]
        row={'file':name,'target':target,'seconds':seconds,'attempts':r.attempts,'bytes':r.after,'met':r.met,'functions':codecs};results.append(row)
        prof.dump_stats(str(ROOT/'output'/f'perf_{label}_{name}_{target}.prof'))
        (ROOT/'output'/f'performance_{label}.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(f'{label}: {name} target={target} {seconds:.2f}s attempts={r.attempts} bytes={r.after}',flush=True)
        engine.close()
if __name__=='__main__':run(sys.argv[1])
