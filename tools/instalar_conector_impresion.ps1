[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "venv\Scripts\pythonw.exe"
$connector = Join-Path $PSScriptRoot "novaerp_print_connector.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encontró $python. Active o cree primero el entorno virtual del proyecto."
}
if (-not (Test-Path -LiteralPath $connector)) {
    throw "No se encontró el archivo del conector: $connector"
}

$installed = $false
try {
    $action = New-ScheduledTaskAction -Execute $python -Argument ('"{0}"' -f $connector)
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName "NovaERP Print Connector" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName "NovaERP Print Connector"
    $installed = $true
} catch {
    # Algunos equipos corporativos bloquean CIM/Programador de tareas. El
    # acceso Inicio del usuario ofrece el mismo resultado sin privilegios.
    $startup = [Environment]::GetFolderPath("Startup")
    $shortcutPath = Join-Path $startup "NovaERP Print Connector.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $python
    $shortcut.Arguments = ('"{0}"' -f $connector)
    $shortcut.WorkingDirectory = $root
    $shortcut.WindowStyle = 7
    $shortcut.Description = "Conector local de impresión NovaERP"
    $shortcut.Save()
    $installed = $true
    Write-Host "El Programador de tareas está bloqueado; se instaló el inicio automático en la carpeta Inicio de Windows." -ForegroundColor Yellow
}

if ($installed) {
    Start-Process -FilePath $python -ArgumentList ('"{0}"' -f $connector) -WindowStyle Hidden
}
Write-Host "Listo. El conector inicia automáticamente al iniciar sesión en Windows." -ForegroundColor Green
Write-Host "Puede cerrar esta ventana. No necesita ejecutar ningún .bat cada día."
