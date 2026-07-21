# Fine-tuning dataset architecture

Issue: #62

## Decision

Polis keeps fine-tuning data separate from correction corpus v3. The dataset is
project-authored, licensed under CC0-1.0, generated deterministically from a
small registry of reviewed linguistic transformations, and committed as JSONL.
Corpus v3 remains evaluation-only.

The dataset has two disjoint splits:

- `train`: 1,200 records, 300 per category;
- `validation`: 240 records, 60 per category.

The categories are `inflection`, `syntax`, `punctuation`, and `no_change`.
Inflection records use the finite-candidate protocol. The other categories use
the corrected-text specialist protocol. Each record retains the source text,
structured target, prompt messages, official Bielik ChatML serialization,
transformation identity, entity spans, provenance, and transformation review
state.

## Safety and isolation

Generation and loading fail closed when records are duplicated, malformed,
unbalanced, incorrectly licensed, model-authored, or unsafe. Positive examples
must make a minimal category-appropriate change. No-change examples must remain
unchanged and collectively cover correct inflection, proper names, marked word
order, punctuation, numbers, URLs, and quotations.

The existing corpus-v3 isolation gate rejects exact and normalized text,
normalized template, and entity-combination overlap across both evaluation
splits. Train and validation additionally use disjoint transformation templates
and entity identities.

## Chat formatting

Messages use the selected specialist contracts and serialize with the official
Bielik 1.5B v3 ChatML template:

```text
<s><|im_start|>system
...<|im_end|>
<|im_start|>user
...<|im_end|>
<|im_start|>assistant
...<|im_end|>
```

The stored ChatML string is an audit artifact. Training integrations should
prefer the structured `messages` field and the tokenizer's
`apply_chat_template` implementation.

Reference implementation and tokenizer contract:

- [Bielik-1.5B-v3.0-Instruct model card](https://huggingface.co/speakleash/Bielik-1.5B-v3.0-Instruct)
- [official tokenizer configuration](https://huggingface.co/speakleash/Bielik-1.5B-v3.0-Instruct/blob/main/tokenizer_config.json)

## Alternatives rejected

- Reusing corpus v3 would invalidate evaluation and violates its training-use
  policy.
- Treating model output as gold would make the target unreviewed and circular.
- Storing only rendered ChatML would discard the structured prompt contract and
  make validation brittle.
