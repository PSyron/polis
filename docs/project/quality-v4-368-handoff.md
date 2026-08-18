# Handoff jakości v4 do #368

Ten dokument jest maszynowo używalnym handoffem z #367 do #368. Nie jest
kanonicznym dowodem jakości: nie zawiera wyników clean-SHA, zatwierdzonej
propozycji ani comparison. Nie wolno traktować go jako zgody na implementację
reguły.

## Aktualny stan

- #367 dostarcza tooling porównania v4, ale canonical baseline/result musi
  zostać zmierzony z jednego czystego SHA oraz koła z tym samym SHA.
- Proposal pozostaje `pending_maintainer_approval` do czasu niezależnej decyzji
  maintenera dla każdego gate'u.
- Rzeczywisty konflikt nadal blokuje morphology profile i musi pozostać
  fail-closed; nie jest to zgoda na zmianę runtime'u w #367.
- Nie publikuj ani nie twórz zastępczych canonical JSON przed clean-SHA runs.

## Obecne luki i identyfikatory przypadków

| gap_id | profile | case_ids | disposition |
| --- | --- | --- | --- |
| `runtime-conflict-control` | morphology | `v4_control_conflict_agreement` | runtime blocker; review-only, fail-closed |
| `canonical-clean-sha-evidence` | default, morphology | `v4_agreement_positive_01` … `v4_syntax_negative_16` | missing until clean wheel measurements |
| `maintainer-gate-decisions` | default, morphology | `aggregate:*`, `category:*`, `stratum:*`, `source:exact-ordered-59-parity`, `control:*`, `performance:*` | pending approval; no comparison authorization |

`v4_control_abstain_01`, `v4_control_abstain_02` i
`v4_control_abstain_03` pozostają kontrolowanymi abstencjami. Nie są
równoznaczne z konfliktem i nie uzasadniają sugestii.

## Dozwolona reprodukcja po clean-SHA

Po wykonaniu pomiarów i podaniu prawdziwych digestów artefaktów:

```bash
python scripts/validate_runtime_performance_v2.py \
  --artifact /tmp/polis-367-performance/runtime-performance-v2-current-default.json \
  --profile default --role current \
  --dataset-id polis_v4_quality_development \
  --dataset-sha256 DATASET_SHA256 --manifest-sha256 MANIFEST_SHA256 \
  --source-sha CLEAN_COMMIT_SHA --wheel-sha256 WHEEL_SHA256 \
  --protocol-sha256 PROTOCOL_FILE_SHA256 --worker-sha256 WORKER_FILE_SHA256
```

Następnie użyj kompletnej literalnej komendy `propose` z
`docs/project/quality-development-v4.md`. Każdy placeholder w tej komendzie
jest wartością wejściową do zastąpienia rzeczywistym digestem lub zmierzonym
progiem; żaden placeholder nie może trafić do artefaktu.
