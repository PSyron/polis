from __future__ import annotations

import importlib.util
from typing import Literal

import pytest

from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationContractError,
    CalibrationDataset,
    ExpectedFinding,
)

if importlib.util.find_spec("polis.evaluation.calibration_overlap") is None:

    def test_planned_independent_dataset_overlap_is_absent() -> None:
        pytest.fail("planned independent dataset overlap contract is absent")

else:
    from polis.evaluation.calibration_overlap import (
        build_keyed_overlap,
        scan_dataset_pii,
    )

    def _dataset(
        identifier: str, text: str, suggestion: str = "Inny"
    ) -> CalibrationDataset:
        finding = ExpectedFinding("rule:x", "test", 0, len(text), text, suggestion)
        case = CalibrationCase(
            f"{identifier}-case", "error", "rule:x", text, (finding,)
        )
        return CalibrationDataset(identifier, (case,), "1" * 64)

    def _dataset_with_channel_value(
        channel: Literal["text", "original", "suggestion"], value: str
    ) -> CalibrationDataset:
        safe_text = "syntetyczny bezpieczny tekst"
        text = value if channel == "text" else safe_text
        original = value if channel == "original" else text
        suggestion = value if channel == "suggestion" else "inna forma"
        finding = ExpectedFinding("rule:x", "test", 0, len(text), original, suggestion)
        case = CalibrationCase("pii-case", "error", "rule:x", text, (finding,))
        return CalibrationDataset("pii", (case,), "1" * 64)

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize(
        "sensitive_value",
        [
            "kontakt test@example.com",
            "adres https://example.com",
            "telefon +48 501 234 567",
            "PESEL 44051401458",
            "NIP 8567346215",
            "REGON 192598184",
            "karta 4111111111111111",
            "dane [PERSON]",
        ],
    )
    def test_pii_scan_rejects_every_sensitive_plaintext_channel(
        channel: Literal["text", "original", "suggestion"], sensitive_value: str
    ) -> None:
        with pytest.raises(CalibrationContractError):
            scan_dataset_pii(_dataset_with_channel_value(channel, sensitive_value))

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize(
        "separator", ["\u00a0", "\u202f", "\u2009", "\u2011", "\u2013", "\u2212"]
    )
    @pytest.mark.parametrize(
        "sensitive_template",
        [
            "telefon +48{separator}501{separator}234{separator}567",
            "PESEL 440514{separator}01458",
            "NIP 856{separator}734{separator}6215",
            "REGON 192{separator}598{separator}184",
            "karta 4111{separator}1111{separator}1111{separator}1111",
        ],
    )
    def test_pii_scan_rejects_unicode_separated_sensitive_values_in_every_channel(
        channel: Literal["text", "original", "suggestion"],
        separator: str,
        sensitive_template: str,
    ) -> None:
        sensitive_value = sensitive_template.format(separator=separator)
        with pytest.raises(CalibrationContractError):
            scan_dataset_pii(_dataset_with_channel_value(channel, sensitive_value))

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize("separator", ["\u00a0", "\u202f", "\u2011", "\u2013"])
    @pytest.mark.parametrize(
        "invalid_template",
        [
            "PESEL 440514{separator}01459",
            "NIP 856{separator}734{separator}6216",
        ],
    )
    def test_pii_scan_preserves_checksum_rejection_after_unicode_normalization(
        channel: Literal["text", "original", "suggestion"],
        separator: str,
        invalid_template: str,
    ) -> None:
        value = invalid_template.format(separator=separator)
        result = scan_dataset_pii(_dataset_with_channel_value(channel, value))
        assert result.verdict == "APPROVE"

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize(
        "separator",
        [
            "\u200b",
            "\u2060",
            "\u200c",
            "\u0301",
            "\u20dd",
            "\u2022",
            "_",
            "\u2764\ufe0f",
            "\U0001f7e2",
        ],
    )
    @pytest.mark.parametrize(
        "sensitive_template",
        [
            "PESEL 440514{separator}01458",
            "NIP 856{separator}734{separator}6215",
            "REGON 192{separator}598{separator}184",
            "karta 4111{separator}1111{separator}1111{separator}1111",
        ],
    )
    def test_pii_scan_rejects_non_alphanumeric_obfuscation_in_every_channel(
        channel: Literal["text", "original", "suggestion"],
        separator: str,
        sensitive_template: str,
    ) -> None:
        value = sensitive_template.format(separator=separator)
        with pytest.raises(CalibrationContractError):
            scan_dataset_pii(_dataset_with_channel_value(channel, value))

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize(
        "separator", ["\u200b", "\u2060", "\u0301", "\u2764\ufe0f"]
    )
    @pytest.mark.parametrize(
        "invalid_template",
        [
            "PESEL 440514{separator}01459",
            "NIP 856{separator}734{separator}6216",
        ],
    )
    def test_pii_scan_keeps_invalid_checksums_clean_across_unicode_categories(
        channel: Literal["text", "original", "suggestion"],
        separator: str,
        invalid_template: str,
    ) -> None:
        value = invalid_template.format(separator=separator)
        result = scan_dataset_pii(_dataset_with_channel_value(channel, value))
        assert result.verdict == "APPROVE"

    @pytest.mark.parametrize("text", ["za\u200cżółć", "z\u0307wykłe zdanie", "znak ❤️"])
    def test_pii_scan_preserves_legitimate_text_with_unicode_marks(text: str) -> None:
        assert scan_dataset_pii(_dataset("cal", text)).verdict == "APPROVE"

    def test_pii_scan_does_not_join_digits_across_letters() -> None:
        text = "PESEL 440514x01458"
        assert scan_dataset_pii(_dataset("cal", text)).verdict == "APPROVE"

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize("separator", ["•", "\u200b", "\u0301", "❤️", "_"])
    @pytest.mark.parametrize("separator_count", [5, 64, 512])
    def test_pii_scan_joins_digits_across_any_bounded_input_separator_run(
        channel: Literal["text", "original", "suggestion"],
        separator: str,
        separator_count: int,
    ) -> None:
        value = f"PESEL 440514{separator * separator_count}01458"
        with pytest.raises(CalibrationContractError):
            scan_dataset_pii(_dataset_with_channel_value(channel, value))

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    @pytest.mark.parametrize(
        "invalid_template",
        [
            "PESEL 440514{separator}01459",
            "NIP 856{separator}734{separator}6216",
        ],
    )
    def test_pii_scan_keeps_invalid_checksums_clean_across_long_separator_runs(
        channel: Literal["text", "original", "suggestion"],
        invalid_template: str,
    ) -> None:
        value = invalid_template.format(separator="•" * 512)
        result = scan_dataset_pii(_dataset_with_channel_value(channel, value))
        assert result.verdict == "APPROVE"

    @pytest.mark.parametrize("channel", ["text", "original", "suggestion"])
    def test_pii_scan_rejects_plaintext_channel_above_frozen_length_bound(
        channel: Literal["text", "original", "suggestion"],
    ) -> None:
        with pytest.raises(CalibrationContractError):
            scan_dataset_pii(_dataset_with_channel_value(channel, "a" * 4097))

    def test_pii_scan_accepts_plaintext_at_frozen_length_bound() -> None:
        assert scan_dataset_pii(_dataset("cal", "a" * 4096)).verdict == "APPROVE"

    @pytest.mark.parametrize(
        "invalid_identifier",
        ["PESEL 44051401459", "NIP 8567346216"],
    )
    def test_pii_scan_uses_national_identifier_checksums(
        invalid_identifier: str,
    ) -> None:
        result = scan_dataset_pii(_dataset("cal", invalid_identifier))
        assert result.verdict == "APPROVE"

    def test_clean_pii_scan_is_aggregate_only() -> None:
        result = scan_dataset_pii(_dataset("cal", "syntetyczne zdanie"))
        assert result.verdict == "APPROVE"
        assert (
            sum(
                (
                    result.email_count,
                    result.url_count,
                    result.phone_count,
                    result.national_id_count,
                    result.payment_card_count,
                )
            )
            == 0
        )
        assert "syntetyczne zdanie" not in repr(result)

    @pytest.mark.parametrize(
        ("collision_class", "left", "right"),
        [
            ("exact", "ZAŻÓŁĆ   gęślą", "zażółć gęślą"),
            ("near", "abcdefghijklmnopqrstuvwxy", "abcdefghijklmnopqrstuvwxz"),
        ],
    )
    def test_distinct_new_dataset_cases_block_exact_and_near_collisions(
        collision_class: Literal["exact", "near"], left: str, right: str
    ) -> None:
        result = build_keyed_overlap(
            _dataset("cal", left, "Korekta kalibracyjna."),
            _dataset("hold", right, "Korekta holdoutowa."),
            (),
            b"k" * 32,
        )

        assert result.verdict == "BLOCK"
        assert result.exact_collisions == (collision_class == "exact")
        assert result.near_collisions == (collision_class == "near")

    @pytest.mark.parametrize(
        ("collision_class", "text", "suggestion"),
        [
            ("exact", "A  B", "A B"),
            ("near", "abcdefghijklmnopqrstuvwxy", "abcdefghijklmnopqrstuvwxz"),
        ],
    )
    def test_same_case_input_and_corrected_channels_are_not_compared(
        collision_class: Literal["exact", "near"], text: str, suggestion: str
    ) -> None:
        result = build_keyed_overlap(
            _dataset("cal", text, suggestion),
            _dataset("hold", "zupełnie odrębna kontrola", "osobna korekta"),
            (),
            b"k" * 32,
        )

        assert result.verdict == "APPROVE", collision_class
        assert (result.exact_collisions, result.near_collisions) == (0, 0)
