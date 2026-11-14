$ErrorActionPreference = 'Stop'

$docxPath = Join-Path $PSScriptRoot 'SE431_Final_Report.docx'
$word = $null
$document = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.ScreenUpdating = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($docxPath, $false, $false)

    if ($document.TablesOfContents.Count -eq 0) {
        throw 'Word did not recognize the TOC field in the report.'
    }

    $contents = $document.TablesOfContents.Item(1)
    $contents.Update()
    $document.Repaginate()
    $contents.UpdatePageNumbers()

    if ($contents.Range.Text -match 'Updating contents') {
        throw 'Word did not populate the automatic table of contents.'
    }

    $document.Save()
    Write-Output "Updated the automatic contents and page fields in $docxPath"
}
finally {
    if ($document -ne $null) {
        $document.Close($false)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($word -ne $null) {
        $word.Quit()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
