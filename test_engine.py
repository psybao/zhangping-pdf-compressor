"""Generated-fixture integration tests. Real PDFs, codec execution, text and render checks."""
import json
from pathlib import Path
import random
import shutil
import threading
import time
from unittest.mock import patch
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader
import pikepdf
import pypdfium2 as pdfium
from engine import Engine, SPEC, fingerprint, inspect, validate, CompressionError, Cancelled

BASE=Path(__file__).parent;OUT=BASE/'output';FIX=OUT/'fixtures';FIX.mkdir(parents=True,exist_ok=True)

def fixtures():
    rng=random.Random(20261118)
    # Texture plus flat regions approximates a scanned illustration; deterministic and nontrivial JPEG data.
    raw=rng.randbytes(1800*2400*3)
    image=Image.frombytes('RGB',(1800,2400),raw)
    draw=ImageDraw.Draw(image);draw.rectangle((50,50,1700,600),fill='white');draw.text((100,150),'SCANNED DOCUMENT 2026',fill='black')
    alpha=Image.new('RGBA',(900,700),(30,120,230,0));ad=ImageDraw.Draw(alpha);ad.ellipse((50,50,850,650),fill=(240,60,30,125))
    for name in ['text','scan','mixed','large','multipage','transparency','compressed']:
        c=canvas.Canvas(str(FIX/f'{name}.pdf'),pagesize=(612,792),pageCompression=1)
        pages=5 if name=='multipage' else 1
        for page in range(pages):
            if name not in ('scan','large'):
                c.setFont('Helvetica',14);c.drawString(40,750,f'SEARCHABLE PDF TEST {name} page {page+1}')
                c.setStrokeColorRGB(.1,.3,.8);c.rect(30,30,550,690,stroke=1,fill=0)
            if name in ('scan','mixed','large','multipage'):
                im=image if name!='large' else image.resize((3000,4000))
                c.drawImage(ImageReader(im),40,55,width=530,height=650)
            if name=='transparency':c.drawImage(ImageReader(alpha),40,80,width=530,height=550,mask='auto')
            if name=='compressed':
                import io
                b=io.BytesIO();image.resize((400,500)).save(b,format='JPEG',quality=35)
                c.drawImage(ImageReader(b),40,55,width=530,height=650)
            c.showPage()
        c.save()
    with pikepdf.open(FIX/'text.pdf') as p:p.save(FIX/'encrypted.pdf',encryption=pikepdf.Encryption(owner='owner',user='secret',R=6))
    (FIX/'empty.pdf').write_bytes(b'');(FIX/'broken.pdf').write_bytes(b'%PDF-1.7\ncorrupt')
    with pikepdf.open(FIX/'text.pdf') as p:
        p.Root.AcroForm=pikepdf.Dictionary(Fields=pikepdf.Array([p.make_indirect(pikepdf.Dictionary(FT=pikepdf.Name('/Sig'),T='TestSignature'))]))
        p.save(FIX/'signed.pdf')

def main():
    fixtures();engine=Engine(OUT/'test_cache');rows=[];start=time.time()
    for name in ['text','scan','mixed','large','multipage','transparency','compressed']:
        src=FIX/f'{name}.pdf';original=fingerprint(src);boxes=inspect(src)
        text=''.join(p.extract_text() or '' for p in PdfReader(src).pages)
        for quality in ['HIGH','MEDIUM','LOW']:
            r=engine.compress(src,quality)
            validate(r.cached,boxes);assert r.after<=r.before
            assert ''.join(p.extract_text() or '' for p in PdfReader(r.cached).pages)==text
            with pdfium.PdfDocument(str(r.cached)) as doc:
                page=doc[0];bitmap=page.render(scale=.6);im=bitmap.to_pil();im.save(OUT/f'render_{name}_{quality}.png');bitmap.close();page.close()
            rows.append(dict(file=name,mode=quality,before=r.before,after=r.after,met=r.met,attempts=r.attempts))
        for target in [500*1024,1048576]:
            r=engine.compress(src,target=target);validate(r.cached,boxes)
            assert r.met==(r.after<=target);assert r.attempts<=12
            assert ''.join(p.extract_text() or '' for p in PdfReader(r.cached).pages)==text
            rows.append(dict(file=name,mode=f'target_{target}',before=r.before,after=r.after,met=r.met,attempts=r.attempts))
        assert fingerprint(src)==original
    assert SPEC['units']['KB']*500==512000 and SPEC['units']['MB']==1048576
    for name in ['encrypted','empty','broken','signed']:
        try:engine.compress(FIX/f'{name}.pdf');raise AssertionError(f'{name} not rejected')
        except (CompressionError,pikepdf.PdfError):pass
    r=engine.compress(FIX/'text.pdf',target=1);assert not r.met
    try:engine.publish(r);raise AssertionError('unmet target published')
    except CompressionError:pass
    dst=OUT/'publication';dst.mkdir(exist_ok=True)
    r=engine.compress(FIX/'mixed.pdf');a=engine.publish(r,dst);b=engine.publish(r,dst);assert a!=b
    copy=dst/'overwrite.pdf';shutil.copyfile(FIX/'mixed.pdf',copy);r=engine.compress(copy);engine.publish(r,overwrite=True);validate(copy,inspect(FIX/'mixed.pdf'))
    changed=dst/'changed.pdf';shutil.copyfile(FIX/'text.pdf',changed);r=engine.compress(changed);changed.write_bytes(changed.read_bytes()+b'\n% changed')
    try:engine.publish(r);raise AssertionError('source change ignored')
    except CompressionError:pass
    cancel=threading.Event();cancel.set()
    try:engine.compress(FIX/'text.pdf',event=cancel);raise AssertionError('cancellation ignored')
    except Cancelled:pass
    r=engine.compress(FIX/'text.pdf')
    try:engine.publish(r,dst/'not_existing');raise AssertionError('missing directory ignored')
    except CompressionError:pass
    original=fingerprint(FIX/'text.pdf')
    with patch('engine.os.replace',side_effect=PermissionError('simulated locked destination')):
        try:engine.publish(r,overwrite=True);raise AssertionError('locked destination ignored')
        except PermissionError:pass
    assert fingerprint(FIX/'text.pdf')==original
    with patch('engine.shutil.disk_usage',return_value=type('Disk',(),{'free':0})()):
        try:engine.publish(r,dst);raise AssertionError('disk full ignored')
        except CompressionError:pass
    cached=engine.compress(FIX/'scan.pdf','MEDIUM');mtime=cached.cached.stat().st_mtime_ns
    assert engine.compress(FIX/'scan.pdf','MEDIUM').cached.stat().st_mtime_ns==mtime
    report=dict(passed=True,seconds=round(time.time()-start,2),rows=rows,checks=['35 actual compression cases','text extraction equality','page count and MediaBox','PDF syntax and stream decode','21 rendered previews','encrypted/empty/corrupt/signed rejection','unmet target refused','copy conflict uniqueness','atomic overwrite','source modification refusal','cancellation','missing output directory','locked replacement rollback (fault injection)','disk full (fault injection)','cache reuse'])
    (OUT/'windows_test_results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'PASS: {len(rows)} actual compression cases; {report["seconds"]} seconds')

if __name__=='__main__':main()
