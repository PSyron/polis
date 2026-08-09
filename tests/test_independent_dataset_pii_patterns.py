from __future__ import annotations

from typing import Literal

import pytest

from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationContractError,
    CalibrationDataset,
    ExpectedFinding,
)
from polis.evaluation.calibration_overlap import scan_dataset_pii


def _dataset_with_channel(
    channel: Literal["text", "original", "suggestion"], value: str
) -> CalibrationDataset:
    safe = "syntetyczny bezpieczny tekst"
    text = value if channel == "text" else safe
    original = value if channel == "original" else text
    suggestion = value if channel == "suggestion" else "inna forma"
    finding = ExpectedFinding("rule:x", "test", 0, len(text), original, suggestion)
    case = CalibrationCase("pii-case", "error", "rule:x", text, (finding,))
    return CalibrationDataset("pii", (case,), "1" * 64)


@pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
@pytest.mark.parametrize(
    "phone",
    [
        "501234567",
        "501 234 567",
        "+48501234567",
        "+48 501 234 567",
        "0048501234567",
        "0048 501 234 567",
        "501\u200b234\u2060567",
        "501•••••234•••••567",
        "+48•••••501•••••234•••••567",
        "0048•••••501•••••234•••••567",
    ],
)
def test_phone_scan_blocks_polish_forms_in_every_channel(
    channel: Literal["text", "original", "suggestion"], phone: str
) -> None:
    with pytest.raises(CalibrationContractError):
        scan_dataset_pii(_dataset_with_channel(channel, phone))


@pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
@pytest.mark.parametrize(
    "value",
    [
        "test\u200b@example.com",
        "https:\u2060//example.com",
        "[PER\u200bSON]",
        "te\u0301st@example.com",
        "https:\u20dd//example.com",
    ],
)
def test_pattern_scan_blocks_invisible_unicode_obfuscation_in_every_channel(
    channel: Literal["text", "original", "suggestion"], value: str
) -> None:
    with pytest.raises(CalibrationContractError):
        scan_dataset_pii(_dataset_with_channel(channel, value))


@pytest.mark.parametrize("value", ["12345678", "501x234567"])
def test_phone_scan_preserves_defensible_non_phone_boundaries(value: str) -> None:
    result = scan_dataset_pii(_dataset_with_channel("text", value))
    assert result.verdict == "APPROVE"
