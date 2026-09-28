param([Parameter(Mandatory=$true)][string]$InstallDir)
$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
$shortcutTarget = $python
$arguments = "-m lyra.launcher"
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\LYRA"
New-Item -ItemType Directory -Force -Path $programs | Out-Null
$wsh = New-Object -ComObject WScript.Shell
foreach ($path in @((Join-Path $desktop "LYRA.lnk"), (Join-Path $programs "LYRA.lnk"))) {
  $shortcut = $wsh.CreateShortcut($path)
  $shortcut.TargetPath = $shortcutTarget
  $shortcut.Arguments = $arguments
  $shortcut.WorkingDirectory = $InstallDir
  $shortcut.Description = "Launch LYRA local AI assistant"
  $shortcut.Save()
}
