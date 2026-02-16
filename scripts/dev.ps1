# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -U pytest
pytest -q
prcopilot --help
