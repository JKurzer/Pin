# psh - pinned shell. Replays context pins, then runs your command.
$pinPy = $env:PIN_PY; if (-not $pinPy) { $pinPy = 'pin.py' }
python $pinPy wrap -- @args
exit $LASTEXITCODE
