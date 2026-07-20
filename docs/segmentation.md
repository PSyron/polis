# Segmentation guarantees

## Purpose

`polis.segmentation` provides stable span objects for paragraph and sentence segmentation.
Each span stores the half-open offsets `[start, end)` into the original input and
an exact `text` slice from that range.

## API

- `segment_paragraphs(text: str) -> tuple[Paragraph, ...]`
- `segment_sentences(text: str) -> tuple[Sentence, ...]`
- `Segment(start: int, end: int, text: str)`
- `Paragraph(start: int, end: int, text: str)`
- `Sentence(start: int, end: int, text: str)`

`text` is expected to be the original UTF-8 decoded Python string. Offsets are
Python index offsets in Unicode code points.

## Parsing behavior

- Paragraphs are split by blank-line boundaries (CRLF and mixed whitespace line
  endings included).
- Sentence boundaries are detected with punctuation (`.`, `?`, `!`) and simple
  closers such as punctuation, quotes, and right brackets.
- Abbreviations in a compact heuristic list (`np`, `itd`, `itp`, `m.in`, `dr`, ...)
  are not split as final sentence boundaries.
- Decimal points (digit dot digit), like `3.14`, are not treated as sentence ends.
- Segment slices are concatenated back to the original input in implementation order.

## Limitations and known caveats

- This is a deterministic heuristic, not a full language model.
- Multi-space and mixed punctuation edge cases should be covered by dedicated
  tests as we extend coverage.
- The heuristic does not promise to resolve every ambiguous sentence break in
  polish prose, only those required for milestone `M1-01`.
