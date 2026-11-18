from pathlib import Path
import json,hashlib,zipfile,datetime
ROOT=Path(__file__).parent;OUT=ROOT/'output';DIST=ROOT/'dist'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def report():
    windows=json.loads((OUT/'windows_test_results.json').read_text(encoding='utf-8-sig'))
    android=json.loads((OUT/'android_test_results.json').read_text(encoding='utf-8-sig'))
    assert windows['passed'] and android['passed']
    for filename in ['exe_quality_test/exe_ui_results.json','exe_target_test/exe_ui_results.json','exe_release_check/exe_ui_results.json']:
        rows=json.loads((OUT/filename).read_text(encoding='utf-8-sig'))
        assert all(row['status'].startswith('成功') and Path(row['output']).exists() for row in rows)
    assert 'PASS' in (OUT/'android_ui_batch_test.txt').read_text(encoding='utf-8-sig')
    assert 'passed' in (OUT/'ui_tests.log').read_text(encoding='utf-8-sig').lower()
    assert 'Error' not in (OUT/'ui_tests.log').read_text(encoding='utf-8-sig')
    assert 'OK (3 tests)' in (OUT/'android_sync_tests.log').read_text(encoding='utf-8-sig')
    assert 'OK (1 test)' in (OUT/'android_onboarding_tests.log').read_text(encoding='utf-8-sig')
    assert 'OK (2 tests)' in (OUT/'android_open_buttons_tests.log').read_text(encoding='utf-8-sig')
    install_log=(OUT/'native_installer_test.log').read_text(encoding='utf-8-sig')
    assert 'Installer process exit: 0' in install_log and 'Installed EXE smoke exit: 0' in install_log
    assert digest(OUT/'native_installer_e2e'/'ZhangPingPDF.exe')==digest(DIST/'张平PDF压缩器.exe')
    assert (DIST/'张平PDF压缩器-安装程序.exe').is_file()
    assert json.loads((OUT/'target_cap_tests.json').read_text(encoding='utf-8'))['passed']
    parallel_rows=json.loads((OUT/'exe_parallel_test/exe_ui_results.json').read_text(encoding='utf-8'))
    assert all(row['status'].startswith('成功') for row in parallel_rows)
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    limitations='''未完成/限制（不可视为全部原始需求验收通过）：
1. Inno Setup 编译器下载并静默安装的命令被自动审批拒绝，返回 blocked by policy；未安装或绕过。改用 Windows 自带 IExpress + Windows Script Host 生成当前用户安装包，保留 installer.iss。替代安装包在项目隔离目录实际安装并启动成功；未对用户真实桌面/开始菜单/卸载注册表执行安装测试。若系统策略禁用 Windows Script Host，请使用独立EXE/便携版或自行编译Inno脚本。
2. Android 通用 SAF 仅支持另存副本，不覆盖原文件。单文件 URI 不授予父目录权限，默认保存应用私有结果目录，可打开/分享；写到公共目录需用户选择目录。为了保护原件，未实现不具原子保证的覆盖。
3. Android APK 为可安装 Debug 签名，不是商店正式签名。release 产物为 app-release-unsigned.apk，不可直接安装；正式签名配置见 README_ANDROID.md。Windows EXE 未进行商业 Authenticode 签名。
4. 已测系统：Windows 11 x64 22631、Android 15/API35 x86_64 模拟器（托管代码兼容 ARM64，无需原生 PDF 库）。Android 13 ARM64 真机的两次安装均返回 User rejected permissions，未执行实机测试；不改变手机安全设置。Android 8/12/14/16、Windows10 均未实测。
5. 未收到提及的两张截图，界面按文字规范实现，不能宣称像素级复现。
6. Android 对透明蒙版、ICC、特殊解码以及超过2400万像素的图片保守跳过。无法达到目标会明确未达标，且不写入输出。不同引擎实际编码与压缩率有差异。
7. Android 后台协程在进程存活期间运行；系统杀进程后恢复队列并提示中断，不自动续传。私有输入保留至移除卡片。SAF 写新副本时杀进程可能留下不完整的新副本，原件不修改。
8. Windows 取消在当前底层 PDF 操作完成后生效。普通错误使用临时文件/安全替换保护原件，但不能对断电或第三方在最终哈希检查后同时修改文件给出绝对保证，重要文档建议使用副本模式。
9. 测试样本为本项目生成的确定性样本，不代表所有复杂 PDF 的视觉等价性或压缩质量认证。磁盘不足与文件占用失败恢复采用故障注入测试，未对用户磁盘制造实际满盘。
'''
    common=f'''张平PDF压缩器 — 双端构建与验证报告
开发者：可达包
版本：1.0.0（2026-11-18 双端快速预估与引导修订版）
时间：{now}
根目录：D:\\PDFCompressor（本次明确指定的新软件项目，不属于历史论文路径迁移）
状态：Windows EXE、便携版和 Android Debug APK 已构建，现有环境测试通过；仍有下述未完成验收项。

已实现：
Windows: PySide6 蓝白1450×820界面、可缩放和滚动参数面板、添加/拖放/批量列表、重复路径检测、选择/全选/清空/删除/排序、单文件品质、手动快速近似预估、品质压缩、逐份目标体积最多12轮搜索、绿色成功/红色具体失败、打开文件/文件夹、批次统计、后台串行执行、取消未开始任务、禁用重复提交、副本唯一命名和验证后原子覆盖。
Android: Kotlin Compose Material3手机布局、SAF多选和持久读取权限、目录选择、手动快速近似预估、单文件品质、逐份目标搜索、选择/全选/清空/删除、后台协程、进度/取消、私有副本及共享目录输出读回验证、打开/分享/保存位置、队列持久化与进程中断提示。
本次按用户最新要求，两端均取消导入后的自动三档完整压缩预估。流程统一为：导入文件→压缩设置→点击预估尺寸/预览→开始压缩。预估只分析有限对象的图像尺寸、长度和编码，不解码图像、不执行完整压缩，不生成候选PDF；给出带“约/仅供参考”的启发式大小和范围，不保证精确或达标。改变模式、品质或目标后重新预估。正式压缩仍按实际输出验证和发布。
体积模式最新修正：填写值为每份PDF的硬上限。2MB=2,097,152字节，预估值和参考范围上限均不超过目标，明确标注“目标内参考，实际达标待验证”。保存前再次按实际文件字节数检查，超限不发布。Windows通过3份PDF的2MB真实输出及预估边界测试、极小目标拒绝和缓存异常变大拒绝；Android通过2MB批次实际保存及预估上限测试。
两端均有清晰单选框，未选模式输入框置灰并禁用；预估按钮位于开始压缩上方；首次启动显示添加PDF/压缩设置/预览/开始压缩四步引导，关闭后记住状态，右上角“？”可重开。
文件卡片“打开”始终打开源文件；成功后新增“压缩后文件”按钮，仅打开输出结果。帮助按钮改为32像素/32dp的小圆形、浅蓝背景和居中半角?。Windows测试拦截打开路径验证前后一致及输出按钮独立；Android Compose实际按钮点击拦截ACTION_VIEW Intent验证源URI/输出URI分离，帮助重开测试通过。
两端均只优化嵌入图像，保留文字/字体/矢量/页面结构。不使用在线压缩API、不进行整页栅格化。加密或带签名字段的文件明确拒绝，避免移除密码或破坏签名。
共享配置 product.json：HIGH200dpi/JPEG85，MEDIUM150dpi/JPEG75，LOW96dpi/JPEG60；Windows pdf-diet采用对应0.85/0.75/0.60的自适应质量阈值，不声称等价固定JPEG质量。KB=1024，MB=1048576。

实际测试：
Windows引擎：{len(windows['rows'])}个真实压缩用例，耗时{windows['seconds']}秒，全部通过。
覆盖7类普通样本×3品质+500KB/1MB；另含加密/空/损坏/签名字段拒绝。页面数/MediaBox、流解析、文字提取逐字符一致、21份渲染预览；人工检查混合页和透明页。副本、同名冲突、覆盖、源文件变化拒绝、过小目标、取消、缓存复用及错误恢复验证通过。
Windows EXE实际运行：历史品质模式与500KB模式基线，以及本次最终构建的2份PDF手动快速预估后500KB正式输出验证。运行记录与截图在 output/exe_quality_test、exe_target_test、exe_release_check。源码UI集成测试覆盖导入不启动任务、手动预估、参数失效、独立品质、选中状态、提交锁定、真实输出、缩放和滚动面板、首次引导状态及帮助重开。便携版及隔离安装后的EXE在仅含Windows目录的PATH下启动退出码0。
Android：{len(android['rows'])}个真实引擎用例通过；包含页数与页面框、PDFBox文字提取一致、Android PdfRenderer实际打开与渲染、加密/空/损坏/签名字段拒绝、极小目标及单位转换。本次Compose Activity测试覆盖首次引导状态、四步与帮助重开、导入不自动预估、手动快速预览、模式变化后需重新预估、预估不产生候选PDF、两份文件逐份2MB上限输出并验证文字；另有49个元数据快速预估用例。Android实际无障碍点击测试走完四步、完成后关闭、右上角帮助重开、再次启动不自动弹出，通过。详见 output/android_sync_tests.log、android_onboarding_tests.log 和 android_quick_estimate.txt。APK签名验证通过。
Windows扫描样本：12,806,133字节→品质MEDIUM1,658,118字节；500KB目标→414,321字节，确实<=512,000字节。
Android同一扫描样本：MEDIUM517,343字节；500KB目标→300,738字节。差异来自独立编码策略。

已修复的测试问题：
打包PATH污染导致错误ICU DLL：清理PATH并重建后EXE实际批量测试通过。
Android只检查已有签名字典会漏掉签名字段：增加signatureFields检查后完整测试通过。
Qt事件方法名称冲突：取消令牌曾命名event，现改为cancel_event；UI测试无事件分派错误。
缩小窗口参数面板超高：改为可滚动固定宽度面板，1000×650验证通过。
IExpress安装包占位符错误：本机IExpress会执行PostInstallCmd中的<None>或空字符串，现改为系统cmd.exe /d /c exit 0空操作，并显式配置正常/静默安装命令；修正版隔离安装与已安装EXE启动验证通过。

{limitations}
交付位置：
Windows：D:\\PDFCompressor\\dist\\张平PDF压缩器.exe
便携版：D:\\PDFCompressor\\dist\\张平PDF压缩器-便携版\\张平PDF压缩器-便携版.exe（需保留整个目录）
Android：D:\\PDFCompressor\\dist\\张平PDF压缩器-Android-debug.apk
原始APK：D:\\PDFCompressor\\android\\app\\build\\outputs\\apk\\debug\\app-debug.apk
源码：D:\\PDFCompressor\\dist\\张平PDF压缩器-完整源码.zip，以及根目录源码和android子目录
安装程序：D:\\PDFCompressor\\dist\\张平PDF压缩器-安装程序.exe（Windows 自带IExpress构建；非Inno产物）
Inno脚本：D:\\PDFCompressor\\installer.iss（未使用Inno编译验证）
正式Android Release：未签名，不能将unsigned文件冒充app-release.apk。

第三方许可证：
pdf-diet Apache-2.0；pikepdf MPL-2.0（未修改）；内置qpdf12.4.2 Apache-2.0；Pillow MIT-CMU/HPND；PySide6/Qt6 LGPL-3.0动态库，提供替换和重建方式、许可文本及对应源码链接；Noto字体SIL OFL1.1；PdfBox-Android Apache-2.0；Kotlin/AndroidX/Compose/Coroutines Apache-2.0；BouncyCastle MIT；pdf-tools MIT仅参考架构/复用标准Gradle脚手架。未复制AGPL业务代码。完整清单见THIRD_PARTY_NOTICES.md、licenses、output/python_components.json、output/android_dependencies.txt与open_source_review.txt。
'''
    push=OUT/'push_result.json'
    quick=json.loads((OUT/'quick_estimate_test.json').read_text(encoding='utf-8'))
    assert quick['passed']
    common+=f"\nWindows快速预估{quick['cases']}个用例耗时：{quick['seconds']:.4f}秒；测试禁止调用完整压缩、PDF保存和全文件哈希，并验证预估及范围<=目标。此为本机样本结果，不保证任意PDF的同等耗时。\n"
    before=json.loads((OUT/'performance_before.json').read_text(encoding='utf-8'))
    after=json.loads((OUT/'performance_after.json').read_text(encoding='utf-8'))
    multi=json.loads((OUT/'performance_parallel.json').read_text(encoding='utf-8'))
    common+='\nWindows运行速度核查（相同样本、冷候选缓存；启用Python性能剖析，两版口径一致）：\n'
    for old,new in zip(before,after):
        assert old['bytes']==new['bytes'] and old['met']==new['met']
        common+=f"{old['file']} 目标{old['target']}: {old['seconds']:.2f}秒→{new['seconds']:.2f}秒，尝试{old['attempts']}→{new['attempts']}，输出{new['bytes']}字节（与原版字节数相同）。\n"
    common+=f"多图片品质模式：{multi[0]['seconds']:.2f}秒→{multi[1]['seconds']:.2f}秒，图片进程1→{multi[1]['workers']}，输出字节数相同。最终独立EXE实际启用2个图片进程并完成4页PDF，保留文字。\n"
    common+='主要瓶颈为原体积模式固定12轮、重复搜索JPEG/JPEG2000编码；图像编码远高于哈希和校验耗时。优化为中品质起步、相邻品质探测及区间搜索，实际生成并验证候选。仍保留原DPI、质量下限和编码器；未删除安全校验，未栅格化文字。Android同步区间搜索。Windows最多2个图片进程，要求多个图像、总像素400万至2400万、单图不超过1200万，且可用内存至少1.5GiB，否则单进程。单张图片品质模式本次没有明显加速；压缩率和速度取决于文件，搜索结果为已尝试候选中的最接近目标者，不承诺全局最优。\n'
    if push.exists():
        status=json.loads(push.read_text(encoding='utf-8'))
        common+='\nHTTP推送：'+('已发送，HTTP '+str(status.get('http_status')) if status.get('sent') else '发送失败：'+status.get('error_type','unknown'))+'。推送内容明确注明剩余验收限制。\n'
    for name in ['CROSS_PLATFORM_BUILD_REPORT.txt','PDF_COMPRESSOR_BUILD_REPORT.txt','ANDROID_BUILD_REPORT.txt','ANDROID_TEST_REPORT.txt']:
        (OUT/name).write_text(common,encoding='utf-8')
    (ROOT/'BUILD_REPORT.txt').write_text(common,encoding='utf-8')
    for name in ['README.md','README_ANDROID.md','THIRD_PARTY_NOTICES.md','BUILD_REPORT.txt']:
        (DIST/name).write_bytes((ROOT/name).read_bytes())
    for name in ['ANDROID_BUILD_REPORT.txt','ANDROID_TEST_REPORT.txt']:
        (ROOT/'android'/name).write_bytes((OUT/name).read_bytes())
    (ROOT/'android'/'THIRD_PARTY_NOTICES.md').write_bytes((ROOT/'THIRD_PARTY_NOTICES.md').read_bytes())
    archive=DIST/'张平PDF压缩器-完整源码.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in ROOT.iterdir():
            if path.is_file() and path.suffix in ['.py','.json','.md','.txt','.ps1','.iss','.vbs'] or path.name=='.gitignore':z.write(path,path.relative_to(ROOT))
        for folder in ['android','shared','assets','licenses','vendor/pdf-diet']:
            for path in (ROOT/folder).rglob('*'):
                rel=path.relative_to(ROOT)
                if path.is_file() and not any(p in ['build','.gradle','.git','__pycache__'] for p in rel.parts) and path.name!='local.properties':z.write(path,rel)
        for filename in ['windows_test_results.json','android_test_results.json','android_ui_batch_test.txt','ui_test_report.txt','quick_estimate_test.json','target_cap_tests.json','android_quick_estimate.txt','performance_before.json','performance_after.json','performance_parallel.json','engine_before_performance.py','product.json','open_source_review.txt','environment.txt','CROSS_PLATFORM_BUILD_REPORT.txt']:
            z.write(OUT/filename,Path('output')/filename)
    manifest=[]
    for path in DIST.rglob('*'):
        if path.is_file() and path.name!='SHA256SUMS.txt':manifest.append(f'{digest(path)}  {path.relative_to(DIST)}')
    (DIST/'SHA256SUMS.txt').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
    print('Reports, source archive and SHA-256 manifest generated')
if __name__=='__main__':report()
