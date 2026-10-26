$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run the README setup steps first.' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'models\model.onnx'))) { throw 'Run setup_model.py first.' }
& $python (Join-Path $root 'app.py')
