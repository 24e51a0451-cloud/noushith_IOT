$ErrorActionPreference = 'Stop'
$reportRoot = $PSScriptRoot
$inputDoc = Join-Path $reportRoot 'MasterHub_Cortex_Connection_Research.docx'
$outputDoc = Join-Path $reportRoot 'MasterHub_Cortex_Connection_Research.doc'
$outputPdf = Join-Path $reportRoot 'qa/MasterHub_Cortex_Connection_Research.pdf'
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordDoc = $wordApp.Documents.Open($inputDoc, $false, $false)
    $wordDoc.SaveAs2($outputDoc, 0)
    $wordDoc.Close(0)
    $wordDoc = $wordApp.Documents.Open($outputDoc, $false, $true)
    $wordDoc.Repaginate()
    $wordDoc.ExportAsFixedFormat($outputPdf, 17)
    Write-Output ('Rendered pages: ' + $wordDoc.ComputeStatistics(2))
    Write-Output $outputDoc
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
}
