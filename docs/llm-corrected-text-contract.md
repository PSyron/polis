# Experimental corrected-text response contract

This contract is an evaluation experiment. It is not a production backend
contract and does not authorize automatic application of model output.

The model must return only this JSON object:

```json
{"corrected_text":"minimal corrected Polish text"}
```

The object has exactly one string field. Polis rejects missing or extra fields,
then derives non-overlapping edits against the original input with original
Unicode offsets. A response that shares no meaningful source word with the
input is rejected as a wholesale rewrite. The derived edits remain subject to
the corpus safety gates before any model can be selected.

This format deliberately makes no claim about the category or confidence of a
change. It is used only to determine whether a model can produce a safe,
minimal corrected sentence before a richer production response contract is
considered.
