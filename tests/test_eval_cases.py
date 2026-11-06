import json
from pathlib import Path

import pytest

from app import pipeline
from eval.run_eval import actual_view, score

ROOT = Path(__file__).resolve().parents[1] / "eval"
CASES = sorted(p for d in ("cases", "holdout") if (ROOT / d).exists() for p in (ROOT / d).iterdir() if p.is_dir())


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_case(case):
    r = pipeline.run((case / "bank.csv").read_text(), (case / "ledger.csv").read_text(), use_llm=False)
    s = score(json.loads((case / "expected.json").read_text()), actual_view(r))
    assert s["pass"], s
