param([string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'selection/runtime-probe.json'))
$ErrorActionPreference='Stop'
$tip='{B115690A-EA02-48D5-A231-E3578D2FDF80}'
$profile='{B2F9C502-1742-11D4-9790-0080C882687E}'
function Read-RegistryValues([string]$Path) {
    if(-not(Test-Path $Path)){return $null}
    $key=Get-Item $Path
    $result=@{}
    foreach($name in $key.GetValueNames()){
        $value=$key.GetValue($name)
        if($value -is [byte[]]){$value=[Convert]::ToBase64String($value)}
        $result[$name]=$value
    }
    return $result
}
$modules=@(); $observations=@()
foreach($process in Get-Process){
    try {
        $list=@($process.Modules)
        foreach($module in $list | Where-Object FileName -Match '(?i)(\\IME\\IMETC\\|\\InputMethod\\CHT\\|\\ChtIME\.exe$)'){
            $modules += [pscustomobject]@{Pid=$process.Id;Process=$process.ProcessName;Path=$module.FileName;Version=$module.FileVersionInfo.FileVersion;SHA256=(Get-FileHash -LiteralPath $module.FileName).Hash}
        }
        if($process.ProcessName -match 'ctfmon|TextInputHost|ChtIME|notepad'){
            $observations += [pscustomobject]@{Pid=$process.Id;Process=$process.ProcessName;ModuleCount=$list.Count;Error=$null}
        }
    }catch{
        if($process.ProcessName -match 'ctfmon|TextInputHost|ChtIME|notepad'){
            $observations += [pscustomobject]@{Pid=$process.Id;Process=$process.ProcessName;ModuleCount=$null;Error=$_.Exception.Message}
        }
    }
}
$report=[ordered]@{
    CapturedUtc=[DateTime]::UtcNow.ToString('o')
    UserProfile=Read-RegistryValues "HKCU:/Software/Microsoft/CTF/TIP/$tip/LanguageProfile/0x00000404/$profile"
    MachineProfile=Read-RegistryValues "HKLM:/Software/Microsoft/CTF/TIP/$tip/LanguageProfile/0x00000404/$profile"
    InProcServer=Read-RegistryValues "HKLM:/SOFTWARE/Classes/CLSID/$tip/InProcServer32"
    LocalServer=Read-RegistryValues "HKLM:/SOFTWARE/Classes/CLSID/$tip/LocalServer32"
    LegacySettings=Read-RegistryValues 'HKCU:/Software/Microsoft/IME/15.0/IMETC'
    CurrentSettings=Read-RegistryValues 'HKCU:/Software/Microsoft/InputMethod/Settings/CHT'
    MatchingModules=$modules
    ProcessObservations=$observations
    Interpretation='Registry enablement is not runtime activation. Zero accessible modules is not evidence that a protected process has no modules.'
}
$report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
$report|ConvertTo-Json -Depth 8
