# ==========================================
# BOTUKA - Architecture Audit
# ==========================================

Clear-Host

$root = "D:\www\Botuka"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " BOTUKA - ARCHITECTURE AUDIT " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Raiz do projeto: $root" -ForegroundColor Green
Write-Host ""

$projects = Get-ChildItem $root -Directory |
Where-Object { $_.Name -like "botuka_*" } |
Sort-Object Name

$result = foreach ($project in $projects) {

    $manage = Test-Path "$($project.FullName)\manage.py"

    $apps = Get-ChildItem $project.FullName -Directory -ErrorAction SilentlyContinue |
    Where-Object {
        Test-Path "$($_.FullName)\apps.py"
    }

    [PSCustomObject]@{
        Projeto      = $project.Name
        ManagePy     = if ($manage) { "SIM" } else { "NÃO" }
        Apps         = $apps.Count
        Templates    = if (Test-Path "$($project.FullName)\templates") { "SIM" } else { "NÃO" }
        Static       = if (Test-Path "$($project.FullName)\static") { "SIM" } else { "NÃO" }
        Media        = if (Test-Path "$($project.FullName)\media") { "SIM" } else { "NÃO" }
        Locale       = if (Test-Path "$($project.FullName)\locale") { "SIM" } else { "NÃO" }
        Requirements = if (Test-Path "$($project.FullName)\requirements") { "SIM" } else { "NÃO" }
        Scripts      = if (Test-Path "$($project.FullName)\scripts") { "SIM" } else { "NÃO" }
    }
}

$result | Format-Table -AutoSize

Write-Host ""
Write-Host "Resumo:" -ForegroundColor Green
Write-Host "Projetos encontrados: $($projects.Count)"
Write-Host "Projetos Django validos: $(($result | Where-Object { $_.ManagePy -eq 'SIM' }).Count)"
Write-Host "Projetos sem manage.py: $(($result | Where-Object { $_.ManagePy -eq 'NÃO' }).Count)"
Write-Host ""

Write-Host "Virtualenv:" -ForegroundColor Green
if (Test-Path "$root\.venv") {
    Write-Host "OK - .venv encontrada" -ForegroundColor Green
} else {
    Write-Host "ERRO - .venv nao encontrada" -ForegroundColor Red
}

Write-Host ""
Write-Host "Pastas globais:" -ForegroundColor Green

$globalFolders = @("docs", "infra", "scripts", "shared", "backups")

foreach ($folder in $globalFolders) {
    if (Test-Path "$root\$folder") {
        Write-Host "OK - $folder" -ForegroundColor Green
    } else {
        Write-Host "FALTANDO - $folder" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Portas em uso na faixa BOTUKA 7700-7799:" -ForegroundColor Green

$ports = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
Where-Object { $_.LocalPort -ge 7700 -and $_.LocalPort -le 7799 } |
Sort-Object LocalPort

if ($ports) {
    $ports |
    ForEach-Object {
        $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        [PSCustomObject]@{
            Porta    = $_.LocalPort
            Processo = $proc.ProcessName
            PID      = $_.OwningProcess
        }
    } | Format-Table -AutoSize
} else {
    Write-Host "Nenhuma porta BOTUKA em uso." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " FIM DO RELATORIO "
Write-Host "==========================================" -ForegroundColor Cyan