"""Asset hierarchy (levels 1-5) and the shared table engine (hier.js, run with node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from meridian import hierarchy
from meridian.policy import load_policy


def test_every_asset_class_once():
    assert hierarchy.check(load_policy().assets) == []
    assert len(hierarchy.load()["levels"]) == 5


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_engine_balances_level_by_level():
    root = Path(__file__).parent
    tree = json.dumps(yaml.safe_load((root.parent / "config" / "hierarchy.yaml").read_text()))
    out = [json.loads(x) for x in subprocess.run(["node", str(root / "js" / "hier_cases.js"), tree],
                                                 capture_output=True, text=True, check=True).stdout.splitlines()]
    assert out[0] == ["0.3200", "0.0300", "0.000000", []]       # US large +2pp funded by its sibling (US small/mid)
    assert out[1] == ["0.5700", "-0.000000", "2.0000"]           # equity to 57%: mix inside equity kept
    assert out[2] == ["0.5700", "0.4500", "-0.000000", []]       # equity 57% of fund AND international 45% of equity
    assert out[3] == ["0.000000", "0.3100", "0.0500"]           # explicit pair (no balancing) nets to zero
    assert out[4] == ["0.000000", "0.0500", "0.1959"]           # cash +2: other groups give pro rata
    assert out[5] == ["0.000000", "0.0550"]                     # EM +10% of its weight, pro rata across the fund
    assert out[6] == ["0.2100", "0.0900"]                       # a security (level 5) funded by its sibling
