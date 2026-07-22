# Sentence safety corpus v1 review checklist

`polis_polish_correction_safety_corpus_v1` contains project-authored synthetic
CC0-1.0 cases. Paweł Cyroń completed the required owner review on 2026-07-22,
after correction and re-review of 49 rejected candidates. The corpus is now
`frozen`; issue #114 does not access or score its holdout.

Review all 240 cases one at a time in canonical JSON and rendered Polish. Mark
a case as approved only after every item below is satisfied:

- [x] **Correctness:** the input contains exactly the claimed objective problem,
  or is genuinely correct when it is a protected hard negative.
- [x] **Category:** the stratum, edit category, tags, and protected phenomenon
  describe the linguistic behavior rather than a stylistic preference.
- [x] **Minimality:** the edit is the smallest justified change and preserves
  meaning, tone, capitalization, and unaffected formatting.
- [x] **Offsets:** each half-open `[start, end)` range selects the declared
  original fragment using Python Unicode code-point indexing.
- [x] **Reconstruction:** applying edits from right to left yields the exact
  `expected_output`, without overlap or ambiguous insertion order.
- [x] **Proper-name behavior:** personal and place names are correctly inflected
  or protected; every controlled surface has one exact span and canonical ID.
- [x] **Syntax and word order:** positive syntax cases are ungrammatical rather
  than merely marked, while protected marked-order cases remain unchanged.
- [x] **Provenance:** the sentence is newly project-authored, synthetic, contains
  no private or copied text, and retains the issue #114 provenance record.
- [x] **Licensing:** the case can be released under CC0-1.0 and contains no
  third-party passage, confidential material, or restricted personal data.
- [x] **Isolation:** the input, entity combination, normalized template, and
  near-duplicate family are independent across splits and from corpus v3,
  fine-tuning data, prompt examples, and E2E fixtures.

After completing the checklist, Paweł Cyroń may change only that case's review
record from:

```json
{
  "status": "pending-human-review",
  "reviewer": null,
  "reviewed_at": null,
  "checklist_version": "safety-corpus-review-v1"
}
```

to `status: "human-reviewed"`, `reviewer: "Paweł Cyroń"`, and the actual ISO
review date. A rejected case must be corrected or replaced and reviewed again;
do not move another case between development and holdout.

The holdout stays `unfrozen-candidates` until every case passes review and all
integrity and leakage checks are green. Freezing is a separate final step:
record the owner, date, `all-cases` scope, candidate digest, and frozen digest
in the separate approval manifest. The generator verifies that manifest,
applies the review metadata, checks every reserved asset for leakage, and only
then writes frozen JSON and XML. Issue #114 must produce no holdout score.
After the first quality-gate access, corrections require a new corpus version.

## Freeze record

- Owner reviewer: Paweł Cyroń
- Review date: 2026-07-22
- Frozen state: `frozen`
- Canonical JSON SHA-256:
  `2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982`
- Holdout score produced by issue #114: no
