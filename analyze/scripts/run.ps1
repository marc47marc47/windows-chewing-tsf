$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$output = Join-Path $root 'analyze'
$env:APPDATA = Join-Path $output 'appdata'
New-Item -ItemType Directory -Force $env:APPDATA | Out-Null
$env:JAVA_HOME = 'C:\git-sdk-64\tools\ghidra\jdk'
$env:JAVA_HOME_OVERRIDE = $env:JAVA_HOME
$headless = 'C:\git-sdk-64\tools\ghidra\support\analyzeHeadless.bat'
New-Item -ItemType Directory -Force "$output/project", "$output/modules", "$output/logs" | Out-Null
$files = Get-ChildItem "$root/IMETC.ref" -Recurse -File | Where-Object Extension -Match '^\.(dll|exe)$' | Sort-Object @{Expression={if($_.Name -eq 'IMTCCORE.DLL'){0}elseif($_.Name -eq 'IMTCTIP.dll'){1}else{2}}},Name
$results = @()
foreach ($file in $files) {
    $before = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    Write-Output "Analyzing $($file.Name)"
    & $headless "$output/project" "IMETC_$($file.BaseName)" -import $file.FullName -overwrite -scriptPath $PSScriptRoot -postScript ExportImetc.java "$output/modules" -log "$output/logs/$($file.Name).log" -scriptlog "$output/logs/$($file.Name).script.log"
    $code = $LASTEXITCODE
    $after = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $results += [pscustomobject]@{File=$file.Name;SHA256=$before;Unchanged=($before -eq $after);ExitCode=$code;Exported=(Test-Path "$output/modules/$($file.Name)/metadata.txt")}
    $results | Export-Csv "$output/summary.csv" -NoTypeInformation -Encoding utf8
}
Get-ChildItem "$output/modules" -Recurse -File | Where-Object Name -Match '^(functions|strings|imports|exports)\.csv$' | Select-String -Pattern 'candidate|rank|sort|phonetic|key|OnKey|選字|候選' | Out-File "$output/selection-index.txt" -Encoding utf8
$results | Format-Table
