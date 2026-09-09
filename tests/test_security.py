import importlib.util
from pathlib import Path

def test_endpoint_scanner():
    spec=importlib.util.spec_from_file_location('scan',Path(__file__).parents[1]/'scripts/security_scan.py')
    scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
    for noun in ('ord'+'ers','pos'+'itions'):
        assert scanner.forbidden_endpoints('https://example.test/v2/'+noun+'?limit=10')
    assert not scanner.forbidden_endpoints('/api/v1/chart/SPY')
