# Zgodność `polis.evaluation` i archiwum danych

W linii 0.x `polis.evaluation` zachowuje importy `load_dataset` i
`validate_dataset`, zgodnie z
[ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md).
[ADR-0023](architecture/decisions/0023-evaluation-namespace-1-0.md) rozszerza
ten zapis do dokładnej 18-elementowej powierzchni importów przez wydanie 1.0,
obejmującej lekkie moduły danych, metryk i walidacji wysyłane w wheel oraz
sdist. Ta zgodność nie poszerza obietnicy korekty runtime'u v1 ani nie
ustanawia bramki jakości produktu: aktywną bramką pozostaje konserwatywny
korpus dziesięciu reguł z bliskimi negatywami i trzema wstrzymaniami.

Korpusy, wyniki i metodologia historycznych badań pozostają niezmienne. Ich
pełny stan sprzed porządkowania jest dostępny wyłącznie przez SHA i lokalizację
opisaną w [manifeście archiwum v2](project/v2-research-archive-manifest.md).
Nie uruchamiaj ponownie zużytych holdoutów i nie dostrajaj na podstawie
zamrożonych dowodów.
