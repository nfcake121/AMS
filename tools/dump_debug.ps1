param(
  [int]$MaxFileSizeKB = 500,
  [string]$OutDump = "repo_dump_debug.txt",
  [string]$OutIndex = "repo_dump_debug_index.txt"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path ".").Path

# Список файлов debug-системы (поддерживаемый минимум)
$paths = @(
  "tools/blender/debug_run.py",
  "tools/blender/batch_debug_run.py",
  "tools/blender/DEBUG_USAGE.md",

  "tools/blender/debug/__init__.py",
  "tools/blender/debug/io.py",
  "tools/blender/debug/metrics.py",
  "tools/blender/debug/validators.py",
  "tools/blender/debug/visualize.py",
  "tools/blender/debug/autofix.py",

  # опционально, но часто нужно рядом
  "tools/blender/run_builder_v01.py",
  "tools/blender/run_export_glb.py",
  "tools/blender/slat_lab.py"
)

# нормализация
$files = @()
foreach ($p in $paths) {
  $abs = Join-Path $root $p
  if (Test-Path $abs) { $files += (Get-Item $abs) }
}

# индекс
$idx = @()
$i = 1
foreach ($f in $files) {
  $sizeKB = [math]::Round(($f.Length / 1KB), 2)
  $note = ""
  if ($sizeKB -gt $MaxFileSizeKB) { $note = "skipped_content_over_limit" }

  $idx += [pscustomobject]@{
    id = $i
    path = (Resolve-Path $f.FullName).Path.Substring($root.Length + 1) -replace "\\","/"
    size_kb = $sizeKB
    note = $note
  }
  $i++
}

$idx | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $OutIndex

# дамп (в один текстовый файл)
$sb = New-Object System.Text.StringBuilder
$null = $sb.AppendLine("=== DEBUG DUMP (filtered) ===")
$null = $sb.AppendLine("root: $root")
$null = $sb.AppendLine("max_file_size_kb: $MaxFileSizeKB")
$null = $sb.AppendLine("generated_at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$null = $sb.AppendLine("")

foreach ($item in $idx) {
  $rel = $item.path -replace "/","\"
  $abs = Join-Path $root $rel

  $null = $sb.AppendLine("----- FILE: $($item.path) ($($item.size_kb) KB) -----")

  if ($item.note -eq "skipped_content_over_limit") {
    $null = $sb.AppendLine("[SKIPPED CONTENT: file is larger than MaxFileSizeKB]")
    $null = $sb.AppendLine("")
    continue
  }

  try {
    $content = Get-Content -Raw -Encoding UTF8 $abs
    $null = $sb.AppendLine($content)
  } catch {
    $null = $sb.AppendLine("[FAILED TO READ FILE AS UTF8] $($_.Exception.Message)")
  }

  $null = $sb.AppendLine("")
}

$sb.ToString() | Set-Content -Encoding UTF8 $OutDump

Write-Host "Wrote $OutDump"
Write-Host "Wrote $OutIndex (rows=$($idx.Count))"
