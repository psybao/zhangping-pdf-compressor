"""Local PDF optimization, verified cache and transactional publication."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
import sys
import time
import pikepdf
from pdfdiet import Optimizer, Profile, RemovalOptions

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent.parent))
SPEC = json.loads((ROOT / 'product.json').read_text(encoding='utf-8'))

class CompressionError(Exception): pass
class Cancelled(CompressionError): pass

@dataclass(frozen=True)
class Estimate:
    after: int
    lower: int
    upper: int
    signature: tuple
    target: int | None = None

def quick_estimate(source, quality='MEDIUM', target=None, event=None):
    """Read bounded object metadata only: no image decoding, encoding or PDF writes."""
    source=Path(source);stat=source.stat();before=stat.st_size
    if not before: raise CompressionError('文件为空')
    if target is not None and target<1: raise CompressionError('目标体积必须大于零')
    check_cancel(event)
    image_bytes=0;weighted=0;started=time.monotonic()
    try:
        with pikepdf.open(source,attempt_recovery=False) as pdf:
            if pdf.is_encrypted: raise CompressionError(SPEC['errors']['encrypted'])
            if not len(pdf.pages): raise CompressionError('PDF 没有页面')
            for i,obj in enumerate(pdf.objects):
                check_cancel(event)
                if i>=256 or time.monotonic()-started>.35: break
                if isinstance(obj,pikepdf.Stream) and obj.get('/Subtype')==pikepdf.Name('/Image'):
                    length=max(0,int(obj.get('/Length',0)))
                    if obj.get('/SMask') or obj.get('/Mask'): factor=.90
                    else:
                        jpeg='/DCTDecode' in str(obj.get('/Filter',''))
                        q=quality if target is None else 'LOW'
                        width=max(1,int(obj.get('/Width',1)));height=max(1,int(obj.get('/Height',1)))
                        assumed_dpi=max(72,max(width,height)/11.7)
                        area=min(1,(SPEC['qualities'][q]['dpi']/assumed_dpi)**2)
                        codec=({'HIGH':.90,'MEDIUM':.75,'LOW':.58} if jpeg else {'HIGH':.65,'MEDIUM':.40,'LOW':.25})[q]
                        if jpeg and length/(width*height)<.30:codec=.98
                        factor=min(.98,max(.03,area*codec))
                    image_bytes+=length;weighted+=length*factor
    except pikepdf.PasswordError as e: raise CompressionError(SPEC['errors']['encrypted']) from e
    except pikepdf.PdfError as e: raise CompressionError('PDF 损坏或格式不支持: '+str(e)) from e
    image_bytes=min(before,image_bytes)
    predicted=min(before,max(1,round((before-image_bytes)*.93+weighted)))
    if target is not None: predicted=min(predicted,target)
    spread=.30 if image_bytes else .12
    return Estimate(predicted,max(1,int(predicted*(1-spread))),min(before,target if target is not None else before,int(predicted*(1+spread))),
                    (stat.st_size,stat.st_mtime_ns),target)

def check_cancel(event):
    if event and event.is_set(): raise Cancelled(SPEC['errors']['cancelled'])

def fingerprint(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def inspect(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0: raise CompressionError('文件不存在或为空')
    try:
        with pikepdf.open(path, attempt_recovery=False) as pdf:
            if pdf.is_encrypted: raise CompressionError(SPEC['errors']['encrypted'])
            if not len(pdf.pages): raise CompressionError('PDF 没有页面')
            if any(obj.get('/Type') == pikepdf.Name('/Sig') or obj.get('/FT') == pikepdf.Name('/Sig') for obj in pdf.objects if isinstance(obj, pikepdf.Dictionary)):
                raise CompressionError(SPEC['errors']['signed'])
            return [tuple(float(v) for v in page.mediabox) for page in pdf.pages]
    except pikepdf.PasswordError as e: raise CompressionError(SPEC['errors']['encrypted']) from e
    except pikepdf.PdfError as e: raise CompressionError('PDF 损坏或格式不支持: ' + str(e)) from e

def validate(path, boxes):
    with pikepdf.open(path, attempt_recovery=False) as pdf:
        if len(pdf.pages) != len(boxes): raise CompressionError('输出页数不一致')
        for page, box in zip(pdf.pages, boxes):
            if tuple(float(v) for v in page.mediabox) != box: raise CompressionError('输出页面尺寸改变')
        problems = pdf.check_pdf_syntax()
        if problems: raise CompressionError('输出 PDF 验证失败: ' + '; '.join(problems[:3]))
        # Force stream decoding to detect damaged compressed streams.
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream) and obj.get('/Subtype') != pikepdf.Name('/Image'):
                obj.read_bytes()

@dataclass(frozen=True)
class Result:
    source: Path
    cached: Path
    before: int
    after: int
    digest: str
    target: int | None = None
    attempts: int = 1
    @property
    def met(self): return self.target is None or self.after <= self.target

class Engine:
    def __init__(self, cache=None):
        self._temp = tempfile.TemporaryDirectory(prefix='zhangping_pdf_') if cache is None else None
        self.cache = Path(cache or self._temp.name)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def close(self):
        if self._temp: self._temp.cleanup()

    def _candidate(self, source, digest, boxes, dpi=None, quality=None, event=None):
        check_cancel(event)
        key = hashlib.sha256(f'{digest}:{dpi}:{quality}:v1'.encode()).hexdigest()
        dest = self.cache / (key + '.pdf')
        if dest.exists():
            validate(dest, boxes)
            return dest
        fd, temp = tempfile.mkstemp(suffix='.pdf', dir=self.cache)
        os.close(fd)
        try:
            if dpi is None:
                with pikepdf.open(source) as pdf:
                    pdf.save(temp, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate, recompress_flate=True)
            else:
                removal = RemovalOptions(**{name: False for name in RemovalOptions.__dataclass_fields__})
                profile = Profile(resolution_dpi=dpi, compression_quality=quality, removal=removal,
                                  crop_to_visible=False, reduce_color_complexity=False)
                Optimizer(workers=1).optimize_document(source, temp, profile)
            check_cancel(event)
            validate(temp, boxes)
            if os.path.getsize(temp) > source.stat().st_size:
                shutil.copyfile(source, temp)
            os.replace(temp, dest)
            return dest
        finally:
            if os.path.exists(temp): os.unlink(temp)

    def compress(self, source, quality='MEDIUM', target=None, event=None, progress=None):
        source = Path(source).resolve()
        with self.lock:
            check_cancel(event)
            digest = fingerprint(source)
            boxes = inspect(source)
            before = source.stat().st_size
            if target is not None and target < 1: raise CompressionError('目标体积必须大于零')
            candidates = []
            def run(dpi=None, q=None):
                if progress: progress(len(candidates), 12 if target else 1)
                out = self._candidate(source, digest, boxes, dpi, q, event)
                candidates.append(out)
                return out.stat().st_size
            if target is None:
                p = SPEC['qualities'][quality]
                run(p['dpi'], p['diet_quality'])
            else:
                size = run()
                if size > target:
                    # Monotonic quality ladder; all candidates are actually written and measured.
                    # Exhaust the bounded ladder because PDF codec sizes need not be monotonic.
                    for dpi, q in [(240,.92),(200,.85),(175,.80),(150,.75),(125,.67),(110,.60),(96,.50),(80,.40),(64,.30),(48,.20),(36,.10)]:
                        run(dpi, q)
            check_cancel(event)
            if fingerprint(source) != digest: raise CompressionError(SPEC['errors']['changed'])
            valid = [p for p in candidates if target is not None and p.stat().st_size <= target]
            # Closest valid size below the bound, otherwise smallest verified result.
            best = max(valid, key=lambda p:p.stat().st_size) if valid else min(candidates, key=lambda p:p.stat().st_size)
            return Result(source, best, before, best.stat().st_size, digest, target, len(candidates))

    def publish(self, result, directory=None, overwrite=False, event=None):
        check_cancel(event)
        if not result.met: raise CompressionError(f"未达目标体积：最小 {result.after} 字节，目标 {result.target} 字节；未写入输出")
        if fingerprint(result.source) != result.digest: raise CompressionError(SPEC['errors']['changed'])
        if result.after > result.before: raise CompressionError('压缩后变大，未写入')
        parent = result.source.parent if overwrite or directory is None else Path(directory)
        if not parent.is_dir(): raise CompressionError('输出目录不存在')
        if shutil.disk_usage(parent).free < result.after + 1024*1024: raise CompressionError('磁盘空间不足')
        fd, temp = tempfile.mkstemp(prefix='.pdfcompress_', suffix='.tmp', dir=parent)
        reserved = None
        try:
            with os.fdopen(fd, 'wb') as out, open(result.cached, 'rb') as src:
                shutil.copyfileobj(src, out)
                out.flush(); os.fsync(out.fileno())
            validate(temp, inspect(result.source))
            actual=os.path.getsize(temp)
            if actual>result.before or (result.target is not None and actual>result.target):
                raise CompressionError('实际输出超过体积上限，未写入输出')
            check_cancel(event)
            if fingerprint(result.source) != result.digest: raise CompressionError(SPEC['errors']['changed'])
            if overwrite:
                dest = result.source
            else:
                for i in range(10000):
                    dest = parent / (result.source.stem + SPEC['suffix'] + (f'_{i}' if i else '') + '.pdf')
                    try:
                        handle = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.close(handle); reserved = dest; break
                    except FileExistsError: continue
                else: raise CompressionError('同名文件冲突过多')
            os.replace(temp, dest)
            reserved = None
            return dest
        finally:
            if os.path.exists(temp): os.unlink(temp)
            if reserved: reserved.unlink(missing_ok=True)
