from __future__ import annotations
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QSettings
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QRadioButton, QDoubleSpinBox,
    QProgressBar, QScrollArea, QFrame, QCheckBox, QMessageBox, QButtonGroup, QSizePolicy, QLayout, QDialog)
from engine import Engine, SPEC, ROOT, Cancelled, quick_estimate

LOGDIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ZhangPingPDF' / 'logs'
LOGDIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(LOGDIR/'app.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')])

def size(n):
    return f'{n/1048576:.2f} MB' if n >= 1048576 else f'{n/1024:.1f} KB'

class Guide(QDialog):
    steps=[('添加 PDF','点击“添加 PDF”或将 PDF 拖入窗口，可一次添加多份文件。导入后不会自动执行预估或压缩。'),
           ('压缩设置','选择“按品质压缩”或“按体积压缩”。品质模式选择高、中、低品质；体积模式输入每份文件的目标大小和 KB/MB 单位。'),
           ('预览','点击“预估尺寸”快速预览近似大小和范围，仅供参考。调整参数后需重新预估；预估不会完整执行压缩，也不保证达到目标。'),
           ('开始压缩','确认预估结果及保存位置后点击“开始压缩”，查看进度条。软件会验证实际输出，无法达到体积目标时明确提示；默认保存为副本。')]
    def __init__(self,parent):
        super().__init__(parent);self.index=0;self.setWindowTitle('使用引导 · 张平PDF压缩器');self.setMinimumWidth(540)
        self.setWindowModality(Qt.WindowModal);self.setAttribute(Qt.WA_DeleteOnClose)
        layout=QVBoxLayout(self);layout.setContentsMargins(28,24,28,24);layout.setSpacing(18)
        heading=QLabel('四步完成 PDF 压缩');heading.setStyleSheet('font-size:23px;font-weight:700');layout.addWidget(heading)
        self.track=QLabel();self.track.setWordWrap(True);self.track.setStyleSheet('color:#2476e5;font-size:14px');layout.addWidget(self.track)
        self.title=QLabel();self.title.setStyleSheet('font-size:21px;font-weight:600');layout.addWidget(self.title)
        self.body=QLabel();self.body.setWordWrap(True);self.body.setMinimumHeight(110);layout.addWidget(self.body)
        reminder=QLabel('右上角“？”可随时重新打开本引导');reminder.setStyleSheet('color:#78869b');layout.addWidget(reminder)
        buttons=QHBoxLayout();layout.addLayout(buttons)
        close=QPushButton('跳过 / 关闭');close.clicked.connect(self.reject);buttons.addWidget(close);buttons.addStretch()
        self.previous=QPushButton('上一步');self.previous.clicked.connect(self.back);buttons.addWidget(self.previous)
        self.next=QPushButton();self.next.setObjectName('primary');self.next.clicked.connect(self.advance);buttons.addWidget(self.next);self.render()
    def render(self):
        self.track.setText('  →  '.join(f'{i+1} {title}' if i!=self.index else f'【{i+1} {title}】' for i,(title,_) in enumerate(self.steps)))
        title,body=self.steps[self.index];self.title.setText(f'{self.index+1} / 4   {title}');self.body.setText(body)
        self.previous.setEnabled(self.index>0);self.next.setText('完成，开始使用' if self.index==3 else '下一步')
    def advance(self):
        if self.index==3:self.accept()
        else:self.index+=1;self.render()
    def back(self):
        self.index=max(0,self.index-1);self.render()

class Worker(QThread):
    update = Signal(str, str, object)
    progress = Signal(int)
    def __init__(self, engine, jobs, event, execute=False, directory=None, overwrite=False):
        super().__init__(); self.engine=engine; self.jobs=jobs; self.cancel_event=event
        self.execute=execute; self.directory=directory; self.overwrite=overwrite
    def run(self):
        for index,(path, quality, target) in enumerate(self.jobs):
            if self.cancel_event.is_set():
                self.update.emit(path, 'cancel', '已取消'); continue
            try:
                if self.execute:
                    self.update.emit(path, 'status', '压缩与验证中…')
                    r=self.engine.compress(path, quality, target, self.cancel_event,
                        lambda n,t: (self.update.emit(path,'status',f'目标体积匹配 · 第 {n+1} 组参数' if target else '正在优化图片与页面结构…'),self.progress.emit(int(100*(index+.05+.85*n/t)/len(self.jobs)))))
                    if not r.met:
                        self.update.emit(path,'error',f'未达标：最小 {size(r.after)} / 目标 {size(target)}；未写入')
                        continue
                    dest=self.engine.publish(r,self.directory,self.overwrite,self.cancel_event)
                    self.update.emit(path,'done',(r,str(dest)))
                else:
                    self.update.emit(path,'status','快速预估中…')
                    r=quick_estimate(path,quality,target,self.cancel_event)
                    self.update.emit(path,'estimate',((quality,target),r))
                    self.update.emit(path,'ready',None)
            except Cancelled:
                self.update.emit(path,'cancel','已取消')
            except Exception as e:
                logging.exception('PDF task failed: %s',path)
                self.update.emit(path,'error',str(e))
            finally:
                self.progress.emit(round(100*(index+1)/len(self.jobs)))

class Card(QFrame):
    def __init__(self,path,window):
        super().__init__(); self.path=path; self.window=window; self.estimates={}; self.output=None
        self.setObjectName('card'); self.setMinimumHeight(140)
        root=QVBoxLayout(self); top=QHBoxLayout(); root.addLayout(top)
        self.check=QCheckBox(); self.check.setChecked(True); top.addWidget(self.check)
        icon=QLabel('PDF'); icon.setObjectName('pdfIcon'); top.addWidget(icon)
        name=QLabel(Path(path).name); name.setWordWrap(True); name.setToolTip(path); top.addWidget(name,1)
        self.quality=QComboBox(); self.quality.addItems(['跟随全局','高品质','中品质','低品质']); top.addWidget(self.quality)
        self.quality.currentIndexChanged.connect(window.refresh)
        self.info=QLabel(); root.addWidget(self.info)
        bottom=QHBoxLayout(); root.addLayout(bottom)
        self.status=QLabel('已导入，请选择参数后点击预估尺寸'); self.status.setWordWrap(True); bottom.addWidget(self.status,1)
        for label,fn in [('打开',self.open),('所在文件夹',self.folder),('移除',lambda:window.remove(path))]:
            b=QPushButton(label); b.clicked.connect(fn); bottom.addWidget(b)
        self.output_button=QPushButton('压缩后文件');self.output_button.clicked.connect(self.open_output);self.output_button.hide();bottom.addWidget(self.output_button)
        self.check.toggled.connect(window.refresh)
    def q(self): return list(SPEC['qualities'])[self.quality.currentIndex()-1] if self.quality.currentIndex() else self.window.global_quality()
    def open(self): QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))
    def open_output(self):
        if self.output:QDesktopServices.openUrl(QUrl.fromLocalFile(self.output))
    def folder(self): QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.output or self.path).parent)))

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f'{SPEC["name"]} · {SPEC["developer"]}')
        self.resize(1450,820); self.setMinimumSize(1000,650); self.setAcceptDrops(True)
        self.engine=Engine(); self.cards={}; self.worker=None; self.cancel_event=threading.Event(); self.completed=0; self.pending=[]
        main=QWidget(); self.setCentralWidget(main); row=QHBoxLayout(main); row.setContentsMargins(25,25,25,25); row.setSpacing(25)
        left=QVBoxLayout(); row.addLayout(left,1)
        title=QLabel(SPEC['name']); title.setObjectName('title'); left.addWidget(title)
        toolbar=QHBoxLayout(); left.addLayout(toolbar)
        for label,fn in [('＋ 添加 PDF',self.add_dialog),('全选',self.select_all),('删除选中',self.delete_selected),('清空',self.clear)]:
            b=QPushButton(label); b.clicked.connect(fn); toolbar.addWidget(b)
        self.sort=QComboBox(); self.sort.addItems(['按添加顺序','按文件名称','按文件大小']); self.sort.currentIndexChanged.connect(self.reorder); toolbar.addWidget(self.sort)
        self.empty=QPushButton('＋\n\n点击添加文件 或 拖拽到此区域\n\n支持批量添加 PDF · 文件始终在本机处理')
        self.empty.setObjectName('drop'); self.empty.clicked.connect(self.add_dialog); left.addWidget(self.empty,1)
        self.empty.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        content=QWidget(); self.list=QVBoxLayout(content); self.list.setAlignment(Qt.AlignTop); self.scroll.setWidget(content); left.addWidget(self.scroll,1); self.scroll.hide()
        self.progress=QProgressBar(); self.progress.setValue(0); left.addWidget(self.progress)
        self.note=QLabel('本地压缩 · 保留文字与矢量 · 开发者：可达包'); left.addWidget(self.note)
        panel=QFrame(); panel.setObjectName('panel'); panel.setMinimumWidth(380)
        panel_scroll=QScrollArea();panel_scroll.setFixedWidth(410);panel_scroll.setWidgetResizable(True);panel_scroll.setFrameShape(QFrame.NoFrame);panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);panel_scroll.setWidget(panel);row.addWidget(panel_scroll)
        side=QVBoxLayout(panel); side.setContentsMargins(24,24,24,24); side.setSpacing(8)
        side.setSizeConstraint(QLayout.SetMinimumSize)
        heading_row=QHBoxLayout();h=QLabel('压缩设置');h.setObjectName('heading');heading_row.addWidget(h,1)
        self.help_button=QPushButton('?');self.help_button.setObjectName('helpButton');self.help_button.setAccessibleName('使用提示');self.help_button.setToolTip('使用提示');self.help_button.setFixedSize(32,32);self.help_button.clicked.connect(self.show_guide);heading_row.addWidget(self.help_button);side.addLayout(heading_row)
        self.quality_mode=QRadioButton('按品质压缩'); self.target_mode=QRadioButton('按体积压缩'); group=QButtonGroup(self); group.addButton(self.quality_mode);group.addButton(self.target_mode);self.quality_mode.setChecked(True)
        side.addWidget(self.quality_mode); self.quality=QComboBox();self.quality.addItems(['高品质','中品质','低品质']);self.quality.setCurrentIndex(1);side.addWidget(self.quality)
        side.addWidget(self.target_mode); tr=QHBoxLayout(); self.target=QDoubleSpinBox();self.target.setRange(.001,100000);self.target.setDecimals(3);self.target.setValue(1); self.unit=QComboBox();self.unit.addItems(['KB','MB']);self.unit.setCurrentText('MB');tr.addWidget(self.target,1);tr.addWidget(self.unit);side.addLayout(tr)
        tip=QLabel('先选择参数，再点击预估尺寸。预估为快速近似值，实际大小以压缩结果为准；体积目标不保证能够达到。'); tip.setWordWrap(True);side.addWidget(tip)
        side.addSpacing(10);side.addWidget(QLabel('批次统计'))
        self.stats=QLabel();self.stats.setWordWrap(True);self.stats.setMinimumHeight(94); side.addWidget(self.stats);side.addStretch()
        side.addWidget(QLabel('保存方式'));self.save=QComboBox();self.save.addItems(['另存为副本','覆盖原文件']);side.addWidget(self.save)
        side.addWidget(QLabel('输出位置'));self.location=QComboBox();self.location.addItems(['原文件相同目录','自定义目录']);side.addWidget(self.location)
        self.directory=QPushButton('选择输出目录…');self.directory.clicked.connect(self.choose_dir);side.addWidget(self.directory);self.output_dir=None
        self.estimate_button=QPushButton('预估尺寸');self.estimate_button.setMinimumHeight(42);self.estimate_button.clicked.connect(self.estimate_sizes);side.addWidget(self.estimate_button)
        self.start=QPushButton('开始压缩');self.start.setObjectName('primary');self.start.setMinimumHeight(52);self.start.clicked.connect(self.compress);side.addWidget(self.start)
        self.cancel=QPushButton('取消任务');self.cancel.clicked.connect(self.cancel_work);self.cancel.setEnabled(False);side.addWidget(self.cancel)
        for control in [self.quality,self.unit,self.target,self.quality_mode,self.target_mode,self.location,self.save]:
            if isinstance(control,QComboBox): control.currentIndexChanged.connect(self.refresh)
            elif isinstance(control,QDoubleSpinBox): control.valueChanged.connect(self.refresh)
            else: control.toggled.connect(self.refresh)
        self.refresh()

    def busy(self): return self.worker is not None
    def maybe_show_guide(self):
        if not QSettings('Kedabao','ZhangPingPDF').value('guide_seen',False,type=bool):self.show_guide()
    def show_guide(self,checked=False,remember=True):
        if getattr(self,'guide',None) is not None:
            self.guide.raise_();return
        self.guide=Guide(self)
        def closed(_):
            self.guide=None
            if remember:QSettings('Kedabao','ZhangPingPDF').setValue('guide_seen',True)
        self.guide.finished.connect(closed);self.guide.open()
    def global_quality(self): return list(SPEC['qualities'])[self.quality.currentIndex()]
    def choose_dir(self):
        d=QFileDialog.getExistingDirectory(self,'选择输出目录')
        if d:self.output_dir=d; self.directory.setText(d);self.directory.setToolTip(d)
    def add_dialog(self):
        files,_=QFileDialog.getOpenFileNames(self,'添加 PDF','','PDF 文件 (*.pdf)');self.add(files)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and not self.busy():event.acceptProposedAction()
    def dropEvent(self,event):self.add([u.toLocalFile() for u in event.mimeData().urls()])
    def add(self,files):
        if self.busy():return
        new=[]; duplicates=0
        for name in files:
            p=Path(name).resolve();key=str(p)
            if p.suffix.lower()!='.pdf' or not p.is_file():continue
            if os.path.normcase(key) in [os.path.normcase(k) for k in self.cards]:duplicates+=1;continue
            card=Card(key,self);self.cards[key]=card;self.list.addWidget(card);new.append((key,'MEDIUM',None))
        self.refresh()
        if duplicates:self.note.setText(f'已跳过 {duplicates} 个重复路径')
        if new:self.note.setText(f'已导入 {len(new)} 份文件，请选择参数后点击“预估尺寸”')
    def target_bytes(self):
        return int(self.target.value()*SPEC['units'][self.unit.currentText()]) if self.target_mode.isChecked() else None
    def current_estimate(self,c):
        r=c.estimates.get((c.q(),self.target_bytes()))
        try:stat=Path(c.path).stat()
        except OSError:return None
        return r if r and r.signature==(stat.st_size,stat.st_mtime_ns) else None
    def estimate_sizes(self):
        if self.busy():return
        jobs=[(p,c.q(),self.target_bytes()) for p,c in self.cards.items() if c.check.isChecked()]
        if jobs:self.run(jobs)
    def run(self,jobs,execute=False):
        self.cancel_event=threading.Event();self.worker=Worker(self.engine,jobs,self.cancel_event,execute,self.output_dir if self.location.currentIndex() else None,self.save.currentIndex()==1)
        self.progress.setValue(0);self.progress.setFormat('%p%')
        self.worker.progress.connect(self.progress.setValue)
        self.worker.update.connect(self.update_card);self.worker.finished.connect(self.finished);self.worker.start();self.refresh()
    def update_card(self,path,kind,data):
        c=self.cards.get(path)
        if not c:return
        if kind=='estimate':q,r=data;c.estimates[q]=r
        elif kind=='done':
            r,c.output=data;c.output_button.show();self.completed+=1;c.status.setStyleSheet('color:#168447');c.status.setText(f'成功  {size(r.before)} → {size(r.after)}  减少 {(1-r.after/r.before)*100:.1f}%')
        elif kind in ('error','cancel'):c.status.setStyleSheet('color:#c8333e');c.status.setText(str(data))
        elif kind=='ready':c.status.setStyleSheet('color:#657189');c.status.setText('近似预估完成，可开始压缩')
        else:c.status.setText(str(data));self.note.setText(f'{Path(path).name} · {data}')
        self.refresh()
    def finished(self):
        old=self.worker;self.worker=None;old.deleteLater();self.note.setText('压缩结束 · 实际结果已验证' if old.execute else '快速预估完成；可调整参数重新预估，或点击开始压缩');self.refresh()
    def cancel_work(self):
        self.cancel_event.set();self.note.setText('正在取消；当前 PDF 操作结束后停止，尚未开始的任务将取消')
    def compress(self):
        if self.busy():return
        if any(c.check.isChecked() and self.current_estimate(c) is None for c in self.cards.values()):
            self.note.setText('请先点击“预估尺寸”，确认当前参数的近似结果');return
        if self.location.currentIndex() and not self.output_dir: self.choose_dir();return
        if self.save.currentIndex() and QMessageBox.question(self,'覆盖原文件','验证成功后将安全替换原文件。是否继续？')!=QMessageBox.Yes:return
        target=int(self.target.value()*SPEC['units'][self.unit.currentText()]) if self.target_mode.isChecked() else None
        jobs=[(p,c.q(),target) for p,c in self.cards.items() if c.check.isChecked()]
        self.completed=0
        if jobs:self.run(jobs,True)
    def remove(self,path):
        if self.busy():return
        c=self.cards.pop(path,None)
        if c:self.list.removeWidget(c);c.deleteLater()
        self.refresh()
    def delete_selected(self):
        for p,c in list(self.cards.items()):
            if c.check.isChecked():self.remove(p)
    def clear(self):
        for p in list(self.cards):self.remove(p)
    def select_all(self):
        for c in self.cards.values():c.check.setChecked(True)
    def reorder(self):
        cards=list(self.cards.values())
        if self.sort.currentIndex()==1:cards.sort(key=lambda c:Path(c.path).name.casefold())
        if self.sort.currentIndex()==2:cards.sort(key=lambda c:Path(c.path).stat().st_size)
        for c in cards:self.list.removeWidget(c);self.list.addWidget(c)
    def refresh(self,*_):
        busy=self.busy();selected=[c for c in self.cards.values() if c.check.isChecked()]
        self.estimate_button.setEnabled(bool(selected) and not busy)
        self.start.setEnabled(bool(selected) and not busy and all(self.current_estimate(c) for c in selected));self.cancel.setEnabled(busy)
        self.empty.setVisible(not self.cards);self.scroll.setVisible(bool(self.cards))
        self.quality.setEnabled(self.quality_mode.isChecked() and not busy);self.target.setEnabled(self.target_mode.isChecked() and not busy);self.unit.setEnabled(self.target_mode.isChecked() and not busy)
        for control in [self.save,self.location,self.quality_mode,self.target_mode,self.directory]:control.setEnabled(not busy)
        total=0;estimated=0;known=0
        for p,c in self.cards.items():
            before=Path(p).stat().st_size if Path(p).exists() else 0
            if c.check.isChecked():total+=before
            r=self.current_estimate(c); text=f'{"目标内参考：" if r and r.target is not None else ""}约 {size(r.after)}（{size(r.lower)}–{size(r.upper)}，{"达标待验证" if r and r.target is not None else "仅供参考"}）' if r else '待预估 / 参数变化后请重新预估'
            c.info.setText(f'原始 {size(before)}   ·   {SPEC["qualities"][c.q()]["label"]}   ·   {text}')
            c.info.setWordWrap(True)
            c.quality.setEnabled(not busy)
            if r and c.check.isChecked():estimated+=r.after;known+=1
        estimate_text=f'约 {size(estimated)} / 约减少 {(1-estimated/total)*100:.1f}%' if known==len(selected) and total else '点击预估尺寸'
        self.stats.setText(f'已选 / 全部：{len(selected)} / {len(self.cards)}\n原始总大小：{size(total)}\n近似总大小：{estimate_text}\n已完成：{self.completed}')
        self.progress.setRange(0,100)
    def closeEvent(self,event):
        if self.busy():self.cancel_work();QMessageBox.information(self,'任务处理中','已请求取消，请等待当前任务结束后关闭。');event.ignore();return
        self.engine.close();event.accept()

STYLE='''QWidget{font-family:"Microsoft YaHei UI";font-size:14px;color:#24344d;background:#f6f8fc;} QMainWindow{background:#f6f8fc;} QLabel#title{font-size:28px;font-weight:700;padding:8px 0 22px;} QLabel#heading{font-size:22px;font-weight:700;} QFrame#panel,QFrame#card{background:white;border:1px solid #e0e6ef;border-radius:12px;} QFrame#panel QLabel,QFrame#card QLabel{background:transparent;} QPushButton{background:white;border:1px solid #d7deea;border-radius:6px;padding:9px 13px;} QPushButton:hover{background:#edf4ff;border-color:#2878e8;} QPushButton:disabled{color:#a5afbd;background:#e8ecf2;} QPushButton#primary{background:#2476e5;color:white;font-weight:700;border:0;} QPushButton#primary:disabled{background:#b4c7e0;} QPushButton#drop{border:2px dashed #c6d6ee;background:white;font-size:20px;color:#6483ad;} QComboBox,QDoubleSpinBox{padding:9px;border:1px solid #d7deea;border-radius:6px;background:white;} QRadioButton,QCheckBox{background:transparent;spacing:9px;} QLabel#pdfIcon{color:#e25959;font-weight:700;padding:12px;background:#fff0f0;border-radius:6px;} QProgressBar{border:0;border-radius:4px;background:#e3eaf4;max-height:8px;color:transparent;}QProgressBar::chunk{background:#2476e5;} QScrollArea{background:transparent;}'''
STYLE+='''QRadioButton{font-weight:600;spacing:10px;padding:5px 0;} QRadioButton::indicator{width:18px;height:18px;border:2px solid #7e91ad;border-radius:11px;background:#fff;} QRadioButton::indicator:hover{border-color:#2476e5;} QRadioButton::indicator:checked{border:2px solid #2476e5;background:qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,stop:0 #2476e5,stop:.50 #2476e5,stop:.56 white,stop:1 white);} QRadioButton::indicator:disabled{border-color:#c2cbd8;background:#edf0f5;} QRadioButton:disabled{color:#99a4b5;} QComboBox:disabled,QDoubleSpinBox:disabled{background:#edf0f5;color:#99a4b5;border:1px solid #d8dfe9;} QComboBox::drop-down:disabled{background:#e5eaf1;border-left:1px solid #d8dfe9;} QDoubleSpinBox::up-button:disabled,QDoubleSpinBox::down-button:disabled{background:#e5eaf1;} QProgressBar{max-height:18px;min-height:18px;color:#24344d;text-align:center;}'''
STYLE+='''QPushButton#helpButton{padding:0;border:1px solid #c6d8f0;border-radius:16px;background:#f0f6ff;color:#2476e5;font-family:"Segoe UI";font-size:20px;font-weight:600;} QPushButton#helpButton:hover{background:#e0edff;border-color:#2476e5;} QPushButton#helpButton:pressed{background:#cce0ff;}'''

def main():
    app=QApplication(sys.argv)
    fontfile=ROOT/'assets'/'NotoSansCJKsc-Regular.otf'
    if fontfile.exists():QFontDatabase.addApplicationFont(str(fontfile))
    app.setFont(QFont('Noto Sans CJK SC',10));app.setStyle('Fusion');app.setStyleSheet(STYLE.replace('Microsoft YaHei UI','Noto Sans CJK SC'))
    app.setApplicationName(SPEC['name']);app.setOrganizationName(SPEC['developer'])
    window=Window();window.show()
    if not any(flag in sys.argv for flag in ['--smoke','--verify-batch']):
        QTimer.singleShot(400,window.maybe_show_guide)
    if '--verify-batch' in sys.argv:
        import argparse
        parser=argparse.ArgumentParser()
        parser.add_argument('--verify-batch',nargs='+');parser.add_argument('--verify-output',required=True);parser.add_argument('--verify-target',type=int)
        args=parser.parse_args()
        folder=Path(args.verify_output);folder.mkdir(parents=True,exist_ok=True)
        window.output_dir=str(folder);window.location.setCurrentIndex(1)
        if args.verify_target:
            window.target_mode.setChecked(True);window.unit.setCurrentText('KB');window.target.setValue(args.verify_target/1024)
        phase=['import']
        timer=QTimer(window)
        def poll():
            if window.busy():return
            if phase[0]=='import':
                phase[0]='estimates';window.estimate_sizes();return
            if phase[0]=='estimates':
                phase[0]='compress';window.compress();return
            timer.stop()
            report=[{'file':p,'status':c.status.text(),'output':c.output,'estimates':{str(q):r.after for q,r in c.estimates.items()}} for p,c in window.cards.items()]
            (folder/'exe_ui_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            window.grab().save(str(folder/'exe_ui.png'));window.close()
        QTimer.singleShot(100,lambda:window.add(args.verify_batch));timer.timeout.connect(poll);timer.start(500)
    if '--smoke' in sys.argv:
        QTimer.singleShot(2000,lambda:window.grab().save(str(Path.cwd()/'output'/'windows_smoke.png')))
        QTimer.singleShot(3000,window.close)
    sys.exit(app.exec())

if __name__=='__main__':main()
