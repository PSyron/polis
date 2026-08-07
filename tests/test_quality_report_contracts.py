from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.quality_report_helpers import _proposal_payload, _result, _write_proposal

from polis.evaluation.quality_report import (
    QualityReportError,
    load_quality_report,
    load_threshold_proposal,
    write_quality_report,
)


@pytest.mark.parametrize("artifact", ("baseline", "proposal"))
def test_json_contracts_reject_unknown_fields(tmp_path: Path, artifact: str) -> None:
    baseline = tmp_path / "baseline.json"
    write_quality_report(_result(), baseline)
    payload = (
        json.loads(baseline.read_text(encoding="utf-8"))
        if artifact == "baseline"
        else _proposal_payload(baseline)
    )
    payload["unexpected"] = True
    path = tmp_path / f"{artifact}-invalid.json"
    _write_proposal(path, payload)

    with pytest.raises(QualityReportError, match="unexpected fields"):
        if artifact == "baseline":
            load_quality_report(path)
        else:
            load_threshold_proposal(path)
