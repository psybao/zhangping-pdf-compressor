Option Explicit
Dim fso, sh, appdir, title, file, regbase
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
appdir = fso.GetParentFolderName(WScript.ScriptFullName)
title = "张平PDF压缩器"
If MsgBox("卸载" & title & "？请先关闭程序。不会删除任何PDF文件。", vbYesNo + vbQuestion, title) <> vbYes Then WScript.Quit 0
On Error Resume Next
For Each file In Array("ZhangPingPDF.exe", "NOTICES.txt")
    If fso.FileExists(appdir & "\" & file) Then fso.DeleteFile appdir & "\" & file, True
Next
If fso.FileExists(sh.SpecialFolders("Desktop") & "\" & title & ".lnk") Then fso.DeleteFile sh.SpecialFolders("Desktop") & "\" & title & ".lnk", True
If fso.FileExists(sh.SpecialFolders("Programs") & "\" & title & ".lnk") Then fso.DeleteFile sh.SpecialFolders("Programs") & "\" & title & ".lnk", True
regbase = "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\ZhangPingPDF\"
For Each file In Array("DisplayName", "DisplayVersion", "Publisher", "DisplayIcon", "InstallLocation", "UninstallString")
    sh.RegDelete regbase & file
Next
sh.RegDelete regbase
Err.Clear
If fso.FileExists(appdir & "\ZhangPingPDF.exe") Then
    MsgBox "程序可能正在运行，请关闭后重新卸载。", vbExclamation, title
    WScript.Quit 1
End If
MsgBox "程序文件已卸载。用户PDF和日志保留。", vbInformation, title
fso.DeleteFile WScript.ScriptFullName, True
