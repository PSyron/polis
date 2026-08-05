# Zgodność `polis.evaluation` i archiwum danych

W linii 0.x `polis.evaluation` zachowuje importy `load_dataset` i
`validate_dataset`, zgodnie z
[ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md).
Ta zgodność nie poszerza obietnicy korekty runtime'u v1 ani nie ustanawia
bramki jakości produktu.

Korpusy, wyniki i metodologia historycznych badań pozostają niezmienne. Ich
pełny stan sprzed porządkowania jest dostępny wyłącznie przez SHA i lokalizację
opisaną w [manifeście archiwum v2](project/v2-research-archive-manifest.md).
Nie uruchamiaj ponownie zużytych holdoutów i nie dostrajaj na podstawie
zamrożonych dowodów.
