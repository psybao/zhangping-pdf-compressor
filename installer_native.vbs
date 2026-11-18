Option Explicit
Dim fso, sh, here, appdir, title, testdir, isTest, link, regbase
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
title = "张平PDF压缩器"
testdir = sh.Environment("PROCESS")("ZHANGPING_INSTALL_TEST_DIR")
isTest = (Len(testdir) > 0)
If isTest Then
    appdir = testdir
Else
    appdir = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\ZhangPingPDF"
    If MsgBox("将为当前用户安装" & title & "。开发者：可达包。继续？", vbYesNo + vbQuestion, title) <> vbYes Then WScript.Quit 0
End If
On Error Resume Next
EnsureFolder appdir
If Err.Number <> 0 Then Fail "无法创建安装目录：" & Err.Description
Err.Clear
fso.CopyFile here & "\App.exe", appdir & "\ZhangPingPDF.exe", True
If Err.Number <> 0 Then Fail "程序写入失败（可能正在运行）：" & Err.Description
fso.CopyFile here & "\uninstall.vbs", appdir & "\uninstall.vbs", True
fso.CopyFile here & "\NOTICES.txt", appdir & "\NOTICES.txt", True
If Err.Number <> 0 Then Fail "安装文件写入失败：" & Err.Description
If Not isTest Then
    Set link = sh.CreateShortcut(sh.SpecialFolders("Desktop") & "\" & title & ".lnk")
    link.TargetPath = appdir & "\ZhangPingPDF.exe"
    link.WorkingDirectory = appdir
    link.Save
    Set link = sh.CreateShortcut(sh.SpecialFolders("Programs") & "\" & title & ".lnk")
    link.TargetPath = appdir & "\ZhangPingPDF.exe"
    link.WorkingDirectory = appdir
    link.Save
    regbase = "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ZhangPingPDF\"
    sh.RegWrite regbase & "DisplayName", title, "REG_SZ"
    sh.RegWrite regbase & "DisplayVersion", "1.0.0", "REG_SZ"
    sh.RegWrite regbase & "Publisher", "可达包", "REG_SZ"
    sh.RegWrite regbase & "DisplayIcon", appdir & "\ZhangPingPDF.exe", "REG_SZ"
    sh.RegWrite regbase & "InstallLocation", appdir, "REG_SZ"
    sh.RegWrite regbase & "UninstallString", "wscript.exe " & Chr(34) & appdir & "\uninstall.vbs" & Chr(34), "REG_SZ"
    If Err.Number <> 0 Then Fail "程序已复制，但快捷方式/卸载信息写入失败：" & Err.Description
    MsgBox "安装完成。可从桌面或开始菜单打开。", vbInformation, title
Else
    Dim log
    Set log = fso.CreateTextFile(appdir & "\install_test.txt", True, True)
    log.WriteLine "PASS: isolated installer copied application, uninstaller and notices. No shortcuts or registry changes in test mode."
    log.Close
End If
WScript.Quit 0
Sub EnsureFolder(path)
    If Not fso.FolderExists(path) Then
        EnsureFolder fso.GetParentFolderName(path)
        fso.CreateFolder path
    End If
End Sub
Sub Fail(message)
    If Not isTest Then MsgBox message, vbCritical, title
    WScript.Quit 1
End Sub
