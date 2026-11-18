import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import time
from PySide6.QtWidgets import QApplication,QScrollArea
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtCore import QEventLoop,QTimer
from PySide6.QtCore import QSettings
from unittest.mock import patch
from app import Window,STYLE

base=Path(__file__).parent
app=QApplication([]);QFontDatabase.addApplicationFont(str(base/'assets/NotoSansCJKsc-Regular.otf'));app.setFont(QFont('Noto Sans CJK SC',10));app.setStyleSheet(STYLE.replace('Microsoft YaHei UI','Noto Sans CJK SC'))
w=Window();w.show();app.processEvents();assert not w.start.isEnabled()
settings_file=base/'output/guide_test.ini'
settings=QSettings(str(settings_file),QSettings.IniFormat);settings.clear()
with patch('app.QSettings',lambda *_:settings):
    w.maybe_show_guide();app.processEvents();assert w.guide and w.guide.index==0
    w.guide.grab().save(str(base/'output/ui_guide.png'))
    for i in range(3):w.guide.advance();assert w.guide.index==i+1
    w.guide.advance();assert w.guide is None;assert settings.value('guide_seen',False,type=bool)
    w.maybe_show_guide();assert w.guide is None
    w.help_button.click();assert w.guide is not None;w.guide.reject();assert w.guide is None
assert w.quality_mode.isChecked() and not w.target.isEnabled() and not w.unit.isEnabled()
w.grab().save(str(base/'output/ui_quality_mode.png'))
src=str(base/'output/fixtures/text.pdf');w.add([src,src]);assert len(w.cards)==1;assert not w.start.isEnabled();assert not w.busy();assert w.estimate_button.isEnabled()
def wait():
    loop=QEventLoop();timer=QTimer();deadline=time.time()+120
    timer.timeout.connect(lambda: loop.quit() if not w.busy() or time.time()>deadline else None)
    timer.start(25);loop.exec();timer.stop();assert not w.busy(),'UI task timeout'
w.estimate_sizes();wait();c=next(iter(w.cards.values()));assert len(c.estimates)==1;assert w.start.isEnabled()
assert c.output_button.isHidden()
with patch('app.QDesktopServices.openUrl',return_value=True) as launch:
    c.open();assert Path(launch.call_args[0][0].toLocalFile())==Path(c.path)
c.quality.setCurrentIndex(3);assert c.q()=='LOW';assert '低品质' in c.info.text()
assert not w.start.isEnabled();w.estimate_sizes();wait();assert w.start.isEnabled()
w.target_mode.setChecked(True);assert not w.start.isEnabled();w.estimate_sizes();wait();assert w.start.isEnabled()
assert w.target.isEnabled() and w.unit.isEnabled() and not w.quality.isEnabled()
w.grab().save(str(base/'output/ui_target_mode.png'))
w.target.setValue(.5);assert not w.start.isEnabled();w.estimate_sizes();wait();assert w.start.isEnabled()
c.check.setChecked(False);assert not w.start.isEnabled();w.select_all();assert w.start.isEnabled()
w.output_dir=str(base/'output/ui_test_outputs');Path(w.output_dir).mkdir(exist_ok=True);w.location.setCurrentIndex(1);w.compress();assert not w.start.isEnabled();wait();assert c.output and Path(c.output).is_file();assert '成功' in c.status.text()
assert not c.output_button.isHidden()
with patch('app.QDesktopServices.openUrl',return_value=True) as launch:
    c.open();assert Path(launch.call_args[0][0].toLocalFile())==Path(c.path)
    c.output_button.click();assert Path(launch.call_args[0][0].toLocalFile())==Path(c.output)
w.grab().save(str(base/'output/ui_open_buttons.png'))
w.resize(1000,650);app.processEvents()
right=[s for s in w.findChildren(QScrollArea) if s.widget() and s.widget().objectName()=='panel'][0]
right.ensureWidgetVisible(w.start);app.processEvents();assert w.start.isVisible();w.grab().save(str(base/'output/ui_small_window.png'))
w.clear();assert not w.cards and not w.start.isEnabled();w.close()
(base/'output/ui_test_report.txt').write_text('PASS: import starts no work; manual quick estimate; mode/quality/target invalidates estimate; independent quality; select/all; repeated submission disabled; actual compression; resize/scroll; clear.',encoding='utf-8')
print('UI integration checks passed')
