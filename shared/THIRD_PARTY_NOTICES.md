# 张平PDF压缩器 — 第三方组件

开发者：可达包。版本 1.0.0。各组件版权归其原作者。本软件没有复制 AGPL 项目代码，没有使用 Ghostscript 或 MuPDF。

|组件|版本|许可证|用途|
|---|---|---|---|
|CPython|3.11.9|PSF-2.0|Windows 嵌入运行时|
|pdf-diet / Pitch Software GmbH|1.3.0，固定源码见 vendor|Apache-2.0|Windows 图像与结构压缩|
|pikepdf|10.18.2|MPL-2.0|PDF 读写及完整性验证|
|qpdf|实际内置版本见 output/environment.txt|Apache-2.0|随 pikepdf wheel 内置的 PDF 引擎|
|Pillow|13.0.0|MIT-CMU / HPND|嵌入图片处理|
|PySide6 / Shiboken6 / Qt6|6.12.0|LGPL-3.0 / GPL-3.0 / 商业多重授权，本项目按 LGPL-3.0 使用|Windows UI、动态库|
|PyInstaller|实际锁定版本见 requirements.txt|GPL-2.0-or-later + bootloader exception|打包工具，生成程序适用例外|
|Noto Sans CJK SC / 思源黑体|noto-cjk main，2026-11-18 下载|SIL OFL-1.1|随 Windows 包分发中文字体|
|PdfBox-Android / Tom Roush|2.0.27.0|Apache-2.0|Android PDF 引擎|
|Apache PDFBox / FontBox|2.0.27 上游移植|Apache-2.0|PdfBox-Android 内含|
|Bouncy Castle|最终解析版本见 output/android_dependencies.txt|MIT|PdfBox-Android 传递依赖|
|Kotlin|2.0.21|Apache-2.0|Android 语言/运行库|
|kotlinx.coroutines|1.9.0|Apache-2.0|后台任务|
|AndroidX Activity|1.9.3|Apache-2.0|Android Activity|
|AndroidX Compose / Material3|BOM 2024.12.01，解析版本见依赖报告|Apache-2.0|Android UI|
|AndroidX Lifecycle|2.8.7|Apache-2.0|ViewModel 与生命周期|
|AndroidX DocumentFile|1.0.1|Apache-2.0|SAF 输出|
|pdf-tools / SammyZi|固定 Git commit 见 output/open_source_review.txt|MIT|审查压缩架构；复用标准 Gradle wrapper 脚手架，未复制业务代码|
|Gradle wrapper|8.9|Apache-2.0|Android 构建工具|
|Android Gradle Plugin|8.7.3|Apache-2.0|Android 构建工具|
|Temurin OpenJDK|17.0.21+9|GPL-2.0 with Classpath Exception|仅构建，不分发进应用|
|Inno Setup|未安装|Inno Setup License|提供安装脚本，编译器安装被自动审批拦截|
|reportlab / pypdf / pypdfium2|见 requirements.txt|BSD / BSD-3-Clause / Apache-2.0 或 BSD-3-Clause（PDFium BSD）|仅测试，不作为应用压缩引擎|

完整 Python 组件元数据、许可文本及上游 NOTICE 位于 licenses/，机器可读版本清单见 output/python_components.json。Android 全部直接和传递依赖见 output/android_dependencies.txt。构建机 SDK/JDK、测试工具不打入应用运行时。

## LGPL 与 MPL 说明

Qt/PySide6 使用未修改的官方动态库，随 EXE 解压加载，未静态链接。完整项目源码、requirements.txt、构建脚本与依赖版本供用户自行重建并替换兼容 Qt/PySide 动态库；便携目录提供可替换的动态库版本。许可证文本包括 LGPL/GPL 及相关 Qt 模块 NOTICE，见 licenses。PySide6 对应源代码：https://download.qt.io/official_releases/QtForPython/ 。Qt 对应源代码：https://download.qt.io/official_releases/qt/6.12/ 。用户可修改 LGPL 组件和为调试此类修改进行逆向工程。

pikepdf 未修改，MPL 对应源码：https://github.com/pikepdf/pikepdf/tree/v10.18.2 。qpdf 对应源码：https://github.com/qpdf/qpdf 。本项目不对第三方组件施加额外使用限制。

## 审查但未集成

minimalpdfcompress、fs-pdf-compressor 只参考公开 README 描述的批量操作与压缩流程；未下载或复制其 AGPL 业务源码。PDF 文件不会发送至这些项目或任何压缩服务。
