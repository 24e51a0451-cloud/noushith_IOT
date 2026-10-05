$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\GALATICX\masterhub_iot_noushith\artifacts\temporal_research'
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
try {
    $document = $wordApp.Documents.Open("$taskRoot\MasterHub_Temporal_Window_Research.docx")
    $document.Repaginate()
    $document.SaveAs2("$taskRoot\MasterHub_Temporal_Window_Research.doc", 0)
    $document.ExportAsFixedFormat("$taskRoot\qa.pdf", 17)
    Write-Output "Pages: $($document.ComputeStatistics(2))"
    $document.Close(0)
} finally {
    $wordApp.Quit()
}
