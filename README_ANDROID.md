# 张平PDF压缩器 Android

开发者：可达包。Kotlin、Compose Material 3、Coroutines、PdfBox-Android 2.0.27.0；最低 Android 8.0，目标 Android 15/API35。无互联网或全盘存储权限。纯托管 PDF 引擎兼容 ARM64，无需 JNI PDF 运行库。

系统文件选择器多选 PDF，申请持久读取 URI 权限；复制到私有工作目录后不自动压缩或预估。选择品质/体积模式和参数后点击“预估尺寸”，仅读取有限对象元数据，给出近似大小和范围，不生成压缩候选 PDF；实际结果以正式压缩为准。更改参数后需重新预估，再点击“开始压缩”。未选模式输入框置灰，单选框边界清晰。首次启动显示添加 PDF → 压缩设置 → 预览 → 开始压缩四步引导；右上角“？”可重开。每个文件可跟随全局或独立品质。后台协程串行处理，ViewModel 支持旋转与切后台；系统杀进程时停止任务，下次启动恢复列表并提示中断，可重新预估或压缩。

嵌入图像使用真实页面变换矩阵计算目标 DPI，复用图像按最大显示尺寸保留清晰度；字体、文字流、矢量和页面尺寸保留。透明蒙版、ICC 色彩、特殊解码和超过 2400 万像素的图像保守跳过，避免损伤和移动设备内存不足。这些文件可能无法达到指定体积。最多 12 轮，实际验证大小、页数与页面框，未达标不保存。

目标体积为每份 PDF 的硬上限。输入 2 MB，预估及参考范围均不超过 2 MB；参考预览不承诺一定达标。保存前按实际字节数再次检查，超限不发布。KB=1024 字节，MB=1048576 字节。

体积模式改为中品质起步、相邻品质探测和区间搜索，避免固定跑满12轮；不超过原最大尝试上限。文件卡片“打开”始终使用原始文件 URI；成功后新增“压缩后文件”打开输出 URI。帮助按钮改为小圆形半角 `?`。

默认保存到应用专属结果目录，可通过系统 PDF 阅读器打开和分享；用户可用系统目录选择器选择共享输出目录。SAF 的单文件 URI 不授予其父目录访问权，因此不能自动写回原文件旁边，需显式选择该目录。

为遵守“失败不得破坏原文件”，本版 Android 仅提供副本模式：通用 SAF Provider 不保证原子替换，故未实现原件覆盖。共享目录输出先验证本地 PDF，写入新文件后读回验证，失败删除新文件。进程在写入时被杀可能留下不完整的新副本；原件始终不被截断。下一版可为支持原子移动的特定 Provider 单独提供覆盖策略。

## 构建

JDK17、Gradle8.9、AGP8.7.3、SDK35/build-tools35.0.0。在 local.properties 设置 SDK；执行 `gradlew.bat :app:assembleDebug :app:assembleRelease`。共享配置从根目录 product.json 复制到 shared/product.json，脚本自动同步。

没有正式发布密钥时交付可安装 Debug APK。`app-release-unsigned.apk` 不可直接安装，不冒充正式签名版本。

## 正式签名

自行创建并安全保管 keystore（不要放入源码或 Git）。在用户 Gradle 属性中设置：

```
RELEASE_STORE_FILE=绝对路径/your-release.jks
RELEASE_STORE_PASSWORD=你的密码
RELEASE_KEY_ALIAS=你的别名
RELEASE_KEY_PASSWORD=你的密码
```

执行 `:app:assembleRelease` 后生成正式签名 `app/build/outputs/apk/release/app-release.apk`。不要用 Debug 密钥作为长期商店发布密钥。

## 测试

`gradlew.bat :app:connectedDebugAndroidTest` 执行真实测试 PDF 的完整矩阵，包含 Android PdfRenderer 渲染与 PDFBox 文字提取比对。实机报告区分已测系统与未测系统，不以编译代替实机测试。进程中断恢复保留私有输入，移除卡片/清空列表删除私有工作副本；原始 URI 文件不删除。
