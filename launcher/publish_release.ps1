param([Parameter(Mandatory=$true)][string]$Tag)
$ErrorActionPreference = "Stop"
if ($Tag -notmatch '^v\d+\.\d+\.\d+$') { throw "Use a stable semantic-version tag, for example v0.3.0." }
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  $versionSource = Get-Content (Join-Path $root "lyra\version.py") -Raw
  if ($versionSource -notmatch 'LYRA_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
    throw "Could not read LYRA_VERSION from lyra/version.py"
  }
  if ($Tag -ne "v$($Matches[1])") { throw "Tag $Tag does not match installed application version $($Matches[1])." }
  if (git status --porcelain) { throw "Commit or stash all changes before publishing a release." }

  $branch = (git branch --show-current).Trim()
  if (-not $branch) { throw "Release publishing requires a named branch, not detached HEAD." }
  git tag $Tag
  if ($LASTEXITCODE -ne 0) { throw "Could not create tag $Tag." }
  git push origin $branch
  if ($LASTEXITCODE -ne 0) { throw "Could not push branch $branch." }
  git push origin $Tag
  if ($LASTEXITCODE -ne 0) { throw "Could not push release tag $Tag." }

  $temp = Join-Path ([System.IO.Path]::GetTempPath()) ("lyra-release-" + [guid]::NewGuid())
  New-Item -ItemType Directory -Path $temp | Out-Null
  try {
    $archive = Join-Path $temp "lyra-app.zip"
    $checksum = Join-Path $temp "lyra-app.zip.sha256"
    git archive --format=zip --output=$archive $Tag
    if ($LASTEXITCODE -ne 0) { throw "Could not build the application archive." }
    $hash = (Get-FileHash -Algorithm SHA256 $archive).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText($checksum, "$hash  lyra-app.zip`n", [System.Text.Encoding]::ASCII)
    gh release create $Tag $archive $checksum --title "LYRA $Tag" --generate-notes
    if ($LASTEXITCODE -ne 0) { throw "GitHub Release creation failed. The tag was pushed; retry gh release create after resolving the issue." }
  }
  finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
finally {
  Pop-Location
}
