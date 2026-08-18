# ADR-0029: Utwardzenie validatora kontraktu pokrycia reguł

- Status: Accepted
- Data: 2026-08-18
- Decydent: Paweł Cyroń
- Issue: #364
- Zastępuje: brak; doprecyzowuje wykonywanie ADR-0028

## Kontekst

ADR-0028 jest zaakceptowanym, niezmiennym zapisem decyzji o pokryciu reguł.
Jego maszynowy kontrakt musi jednak odrzucać nie tylko brak pól, ale także
sprzeczne znaczenia: zmienione formuły, profile dostawcy, bramki fail-closed,
minima próbkowania, relacje, tożsamość noty providera oraz parity artefaktów.
Validator jest narzędziem repozytoryjnym, więc nie może rozszerzać powierzchni
runtime'u ani publikowanego pakietu.

## Decyzja

1. ADR-0028 pozostaje bez zmian. Jego znaczenie może zmienić tylko kolejny ADR.
2. Wykonywalne wartości kontraktu są w
   `docs/project/rule-coverage-contract-v1.json`, a validator w
   `scripts/rule_coverage_contract.py`; nie jest to moduł runtime `polis.evaluation`.
3. Kontrakt zapisuje i waliduje kolejność źródeł decyzji: issue z clarifications,
   zaakceptowane ADR-y, `PROMPT.md`, roadmapę, wykaz reguł oraz publiczne
   artefakty jakości i wydajności.
4. Validator wymaga dokładnych pięciu kategorii, dwóch profili, siedmiu relacji,
   wszystkich metryk i ich formuł, zero-denominator, conflict/abstention,
   bramek, minimów, wymaganych strat, wyłączeń i polityki `review-only`.
5. Profil `qualified-morphology` jest związany z `morfeusz2` 1.99.15,
   `pl.sgjp.sgjp-2026.06.01` oraz SHA-256 noty
   `84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393`.
   Drift tożsamości pozostaje abstencją, a nie zgodą na użycie niekwalifikowanego
   providera.
6. Parity obejmuje ordered source snapshot, operation, behavior version,
   utrzymywany wykaz, correction policy i publiczne artefakty jakości. Brak,
   nadmiar, duplikat, reorder lub drift kończy walidację fail-closed.
7. Validator porównuje kanoniczny SHA-256 całego zaakceptowanego JSON-u
   (`a3fa383c35ee97c9af43835b7aeb2ec1dfaaafa3b2f7f970d8881833e699ef8d`),
   więc sprzeczne dopiski do pól decyzyjnych nie mogą zachować ważności.

## Konsekwencje

Zmiany decyzji wymagają nowego ADR-u, natomiast korekty implementacji validatora
muszą zachować ten kontrakt i dostać świeży test, pełny dozwolony gate oraz
niezależny review związany z SHA. Skrypt pozostaje poza runtime'em i nie dodaje
zależności produkcyjnych, danych chronionych, reguł ani progów v4.
