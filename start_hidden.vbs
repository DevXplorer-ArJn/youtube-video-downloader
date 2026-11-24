Set shell = CreateObject("WScript.Shell")
projectFolder = Replace(WScript.ScriptFullName, "\start_hidden.vbs", "")
shell.CurrentDirectory = projectFolder
pythonw = shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python315\pythonw.exe"
shell.Run Chr(34) & pythonw & Chr(34) & " """ & projectFolder & "\desktop_app.py""", 0, False
