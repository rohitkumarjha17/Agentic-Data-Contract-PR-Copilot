from pathlib import Path
import json

from prcopilot.services.contract_runner import run_contract


def test_contract_passes_on_sample_data():
    report = run_contract(Path("contracts/orders_contract.yaml"), Path("examples/data/orders.csv"))
    assert report.failed_checks == 0
    assert report.total_checks > 0
