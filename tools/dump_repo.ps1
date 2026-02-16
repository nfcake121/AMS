<#
Usage:
  powershell -ExecutionPolicy Bypass -File tools/dump_repo.ps1

Creates in repository root:
  - repo_dump.txt
  - repo_dump_index.txt

Key excluded directories (any level):
  .git, __pycache__, .venv, venv, out, models, data/cache,
  .mypy_cache, .pytest_cache, .ruff_cache, node_modules,
  dist, build, .next, .idea, .vscode, .vs, logs, tmp, temp, .cache
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:MaxFileSizeBytes = 2MB
$script:IncludedExtensions = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
@('.py', '.ps1', '.md', '.txt', '.json', '.yml', '.yaml', '.toml', '.ini') | ForEach-Object {
    [void]$script:IncludedExtensions.Add($_)
}

$script:IncludedExactNames = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
@('requirements.txt', 'pyproject.toml', 'README.md') | ForEach-Object {
    [void]$script:IncludedExactNames.Add($_)
}

$script:ExcludedDirNames = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
@(
    '.git', '__pycache__', '.venv', 'venv', 'out', 'models',
    '.mypy_cache', '.pytest_cache', '.ruff_cache', 'node_modules',
    'dist', 'build', '.next', '.idea', '.vscode', '.vs',
    'logs', 'tmp', 'temp', '.cache'
) | ForEach-Object {
    [void]$script:ExcludedDirNames.Add($_)
}

$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Resolve-RepoRoot {
    param(
        [string]$StartPath = (Get-Location).Path
    )

    $startItem = Get-Item -LiteralPath $StartPath -Force -ErrorAction SilentlyContinue
    if ($null -eq $startItem) {
        return (Get-Location).Path
    }

    $initialDir = if ($startItem.PSIsContainer) {
        $startItem.FullName
    } else {
        Split-Path -LiteralPath $startItem.FullName -Parent
    }
    $currentPath = $initialDir

    while ($true) {
        if (Test-Path -LiteralPath (Join-Path -Path $currentPath -ChildPath '.git')) {
            return $currentPath
        }

        $parent = [System.IO.Directory]::GetParent($currentPath)
        if ($null -eq $parent) {
            return $initialDir
        }

        $currentPath = $parent.FullName
    }
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $baseResolved = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $BasePath -ErrorAction Stop).Path).TrimEnd('\', '/')
    $pathResolved = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path)

    if ($pathResolved.Equals($baseResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        return '.'
    }

    $basePrefix = $baseResolved + '\'
    if ($pathResolved.StartsWith($basePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return ($pathResolved.Substring($basePrefix.Length) -replace '\\', '/')
    }

    $baseUriText = 'file:///' + (($baseResolved -replace '\\', '/').TrimStart('/')) + '/'
    $pathUriText = 'file:///' + (($pathResolved -replace '\\', '/').TrimStart('/'))
    $baseUri = New-Object System.Uri($baseUriText)
    $pathUri = New-Object System.Uri($pathUriText)
    $relative = [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString())
    return ($relative -replace '\\', '/')
}

function Is-ExcludedDir {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$DirPath
    )

    $relative = Get-RelativePath -BasePath $RepoRoot -Path $DirPath
    if ($relative -eq '.') {
        return $false
    }

    $parts = @($relative -split '/' | Where-Object { $_ -ne '' })

    foreach ($part in $parts) {
        if ($script:ExcludedDirNames.Contains($part)) {
            return $true
        }
    }

    for ($i = 0; $i -lt ($parts.Count - 1); $i++) {
        if ($parts[$i].Equals('data', [System.StringComparison]::OrdinalIgnoreCase) -and
            $parts[$i + 1].Equals('cache', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $false
}

function Is-IncludedFile {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileInfo]$File
    )

    if ($script:IncludedExactNames.Contains($File.Name)) {
        return $true
    }

    if ($script:IncludedExtensions.Contains($File.Extension)) {
        return $true
    }

    return $false
}

function Is-BinaryFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $buffer = New-Object byte[] 4096
            $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
            for ($i = 0; $i -lt $bytesRead; $i++) {
                if ($buffer[$i] -eq 0) {
                    return $true
                }
            }
            return $false
        } finally {
            $stream.Dispose()
        }
    } catch {
        return $true
    }
}

function Write-Dump {
    param(
        [Parameter(Mandatory = $true)][array]$Entries,
        [Parameter(Mandatory = $true)][string]$DumpPath
    )

    $includedEntries = @($Entries | Where-Object { $_.Included } | Sort-Object RelativePath)

    $filesFound = $Entries.Count
    $filesWritten = @($Entries | Where-Object { $_.Status -eq 'OK' }).Count
    $filesSkippedLarge = @($Entries | Where-Object { $_.Status -eq 'SKIP_LARGE' }).Count
    $filesSkippedBinary = @($Entries | Where-Object { $_.Status -eq 'SKIP_BINARY' }).Count

    $renderDump = {
        param([long]$OutputBytesValue)

        $sb = New-Object System.Text.StringBuilder

        for ($i = 0; $i -lt $includedEntries.Count; $i++) {
            $entry = $includedEntries[$i]

            if ($i -gt 0) {
                [void]$sb.Append("`r`n`r`n`r`n")
            }

            [void]$sb.Append('===== FILE: ').Append($entry.RelativePath).Append(" =====`r`n")

            if ($entry.Status -eq 'OK') {
                if ($null -ne $entry.Content) {
                    [void]$sb.Append($entry.Content)
                }
            } elseif ($entry.Status -eq 'SKIP_LARGE') {
                [void]$sb.Append('[SKIP: file too large ').Append($entry.SizeBytes).Append(' bytes]')
            } elseif ($entry.Status -eq 'SKIP_BINARY') {
                [void]$sb.Append('[SKIP: unreadable or binary]')
            }
        }

        if ($includedEntries.Count -gt 0) {
            [void]$sb.Append("`r`n`r`n")
        }

        [void]$sb.Append("===== SUMMARY =====`r`n")
        [void]$sb.Append('files_found=').Append($filesFound).Append("`r`n")
        [void]$sb.Append('files_written=').Append($filesWritten).Append("`r`n")
        [void]$sb.Append('files_skipped_large=').Append($filesSkippedLarge).Append("`r`n")
        [void]$sb.Append('files_skipped_binary=').Append($filesSkippedBinary).Append("`r`n")
        [void]$sb.Append('output_bytes=').Append($OutputBytesValue)

        return $sb.ToString()
    }

    $outputBytes = 0L
    $content = ''

    for ($i = 0; $i -lt 8; $i++) {
        $content = & $renderDump $outputBytes
        $calculated = $script:Utf8NoBom.GetByteCount($content)
        if ($calculated -eq $outputBytes) {
            break
        }
        $outputBytes = $calculated
    }

    $content = & $renderDump $outputBytes
    [System.IO.File]::WriteAllText($DumpPath, $content, $script:Utf8NoBom)

    return (Get-Item -LiteralPath $DumpPath -ErrorAction Stop).Length
}

function Write-Index {
    param(
        [Parameter(Mandatory = $true)][array]$Entries,
        [Parameter(Mandatory = $true)][string]$IndexPath
    )

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append("path`tsize_bytes`tstatus`r`n")

    foreach ($entry in $Entries) {
        [void]$sb.Append($entry.RelativePath).Append("`t").Append($entry.SizeBytes).Append("`t").Append($entry.Status).Append("`r`n")
    }

    [System.IO.File]::WriteAllText($IndexPath, $sb.ToString(), $script:Utf8NoBom)

    return ($Entries.Count + 1)
}

$repoRoot = Resolve-RepoRoot
$dumpPath = Join-Path -Path $repoRoot -ChildPath 'repo_dump.txt'
$indexPath = Join-Path -Path $repoRoot -ChildPath 'repo_dump_index.txt'

$allFiles = New-Object System.Collections.Generic.List[System.IO.FileInfo]
$stack = New-Object 'System.Collections.Generic.Stack[string]'
$stack.Push($repoRoot)

while ($stack.Count -gt 0) {
    $currentDir = $stack.Pop()

    try {
        $children = Get-ChildItem -LiteralPath $currentDir -Force -ErrorAction Stop
    } catch {
        continue
    }

    foreach ($child in $children) {
        if ($child.PSIsContainer) {
            if (($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                continue
            }

            if (Is-ExcludedDir -RepoRoot $repoRoot -DirPath $child.FullName) {
                continue
            }

            $stack.Push($child.FullName)
            continue
        }

        $allFiles.Add([System.IO.FileInfo]$child)
    }
}

$entries = @(
    foreach ($file in ($allFiles | Sort-Object { Get-RelativePath -BasePath $repoRoot -Path $_.FullName })) {
        $relativePath = Get-RelativePath -BasePath $repoRoot -Path $file.FullName
        $included = Is-IncludedFile -File $file
        $status = 'SKIP_EXT'
        $content = $null

        if ($included) {
            if ($file.Length -gt $script:MaxFileSizeBytes) {
                $status = 'SKIP_LARGE'
            } elseif (Is-BinaryFile -Path $file.FullName) {
                $status = 'SKIP_BINARY'
            } else {
                try {
                    $content = [System.IO.File]::ReadAllText($file.FullName)
                    $status = 'OK'
                } catch {
                    $status = 'SKIP_BINARY'
                    $content = $null
                }
            }
        }

        [pscustomobject]@{
            RelativePath = $relativePath
            SizeBytes = [long]$file.Length
            Status = $status
            Included = $included
            Content = $content
        }
    }
)

$dumpBytes = Write-Dump -Entries $entries -DumpPath $dumpPath
$indexRows = Write-Index -Entries $entries -IndexPath $indexPath

Write-Output ("Wrote repo_dump.txt (bytes={0})" -f $dumpBytes)
Write-Output ("Wrote repo_dump_index.txt (rows={0})" -f $indexRows)
