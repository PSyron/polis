from __future__ import annotations

import unittest

from scripts import bootstrap_github


class EventualIssueListingTests(unittest.TestCase):
    def test_retries_until_all_expected_issue_titles_are_visible(self) -> None:
        expected = {f"M4-0{index} outcome" for index in range(1, 5)}
        responses = [
            [{"title": "M4-01 outcome"}],
            [{"title": title} for title in sorted(expected)],
        ]
        pauses: list[float] = []

        def fetch() -> list[dict[str, str]]:
            return responses.pop(0)

        result = bootstrap_github.wait_for_expected_issues(
            fetch,
            expected,
            attempts=3,
            sleeper=pauses.append,
        )

        self.assertEqual({item["title"] for item in result}, expected)
        self.assertEqual(pauses, [1.0])
        self.assertEqual(responses, [])


if __name__ == "__main__":
    unittest.main()
