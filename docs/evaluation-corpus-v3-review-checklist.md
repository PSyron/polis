# Polish correction corpus v3 review checklist

Corpus v3 contains model-drafted CC0-1.0 candidates. Every case starts as
`pending-human-review`; it is neither gold data nor a frozen holdout. Only
Paweł Cyroń may record the approval required by the schema-v3 review policy.

Review one case at a time in both canonical JSON and rendered Polish text.
Approve a case only after every item below is satisfied:

- [ ] **Correctness:** the input contains exactly the claimed grammatical or
  punctuation problem, or is genuinely correct when it is a hard negative.
- [ ] **Category:** the stratum, finding category, tags, and protected
  phenomenon describe the linguistic behavior rather than a stylistic
  preference.
- [ ] **Minimality:** every proposed edit is the smallest justified change and
  preserves meaning, tone, capitalization, and unaffected formatting.
- [ ] **Offsets:** every `[start, end)` range selects the declared `original`
  fragment using Python Unicode code-point indexing.
- [ ] **Reconstruction:** applying all edits from right to left yields the exact
  `expected_output`, with no overlap or ambiguous insertion order.
- [ ] **Proper-name behavior:** names, surnames, place names, and indeclinable
  forms are inflected or protected correctly for their context.
- [ ] **Syntax and word order:** an error case is ungrammatical rather than
  merely marked; a protected marked-order case remains unchanged.
- [ ] **Provenance:** the case is synthetic, contains no private or copied text,
  and retains its complete candidate provenance record.
- [ ] **Licensing:** the candidate can be released as CC0-1.0 and contains no
  third-party passage or restricted personal data.
- [ ] **Isolation:** the input, canonical entity combination, and normalized
  template do not occur elsewhere in the corpus, prompt examples, or any
  training asset; entity spans select every exact surface from the controlled
  catalog, map inflected variants to one identity, and reproduce the normalized
  template. Short sibling templates that differ by only one token are one
  family and must not cross records or splits.

After completing the checklist, Paweł Cyroń may change only that case's review
record from:

```json
{
  "status": "pending-human-review",
  "reviewer": null,
  "reviewed_at": null,
  "checklist_version": "corpus-v3-review-v1"
}
```

to `status: "human-reviewed"`, `reviewer: "Paweł Cyroń"`, and an ISO review
date. A rejected candidate must be corrected and reviewed again or removed and
replaced without moving another case between development and holdout.

The holdout remains `unfrozen-candidates` until all 240 cases pass review and
all integrity checks are green. Freezing is a separate, explicit change: set
`holdout_state` to `frozen`, regenerate the equivalent XML, record the JSON
SHA-256, and run the full fast test suite. After freezing, changes require a new
corpus version; do not repair a benchmarked holdout in place.
