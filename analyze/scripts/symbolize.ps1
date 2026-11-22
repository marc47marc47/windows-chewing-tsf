$ErrorActionPreference='Stop'
$analysis=Split-Path $PSScriptRoot -Parent
$env:JAVA_HOME='C:\git-sdk-64\tools\ghidra\jdk'
$env:APPDATA=Join-Path $analysis appdata
$env:LOCALAPPDATA=Join-Path $analysis localappdata
New-Item -ItemType Directory -Force $env:LOCALAPPDATA | Out-Null
$manifest=Get-Content "$analysis/symbols/manifest.json" -Raw | ConvertFrom-Json
$results=@()
foreach($entry in ($manifest | Sort-Object @{e={if($_.module -eq 'IMTCCORE.DLL'){0}elseif($_.module -eq 'IMTCTIP.dll'){1}else{2}}},module)) {
    if($entry.status -ne 'downloaded'){throw "Missing symbols for $($entry.module)"}
    $project='IMETC_'+[IO.Path]::GetFileNameWithoutExtension($entry.module)
    & 'C:/git-sdk-64/tools/ghidra/support/analyzeHeadless.bat' "$analysis/project" $project -process $entry.module -noanalysis -scriptPath $PSScriptRoot -postScript ApplySymbols.java $entry.path -postScript ExportImetc.java "$analysis/modules-symbolized" -log "$analysis/logs/$($entry.module).symbols.log" -scriptlog "$analysis/logs/$($entry.module).symbols.script.log"
    $results += [pscustomobject]@{Module=$entry.module;ExitCode=$LASTEXITCODE;Exported=(Test-Path "$analysis/modules-symbolized/$($entry.module)/all-references.csv")}
    $results | Export-Csv "$analysis/symbols/summary.csv" -NoTypeInformation
}
