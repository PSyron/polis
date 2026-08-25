# Utwardzenie protokołu WikEd holdoutu — plan implementacji

> **Dla agentów:** wykonuj zadania kolejno, test-first, z kontrolą po każdym
> zadaniu. Nie otwieraj, nie czytaj ani nie uruchamiaj rzeczywistego holdoutu.

**Cel:** Zamknąć luki bezpieczeństwa wykryte w PR #443: wymusić nieprzezroczysty
dowód pełnej autoryzacji, ochronić niezmienne artefakty publikacji, ujednolicić
blokadę między workspace'ami oraz usunąć wyścigi ścieżek i sprzątania.

**Architektura:** `SecureHoldoutWorkspace` otrzyma zweryfikowany dowód admission
utworzony z pełnego `ExternalAdmission`; secure boundary porówna go z własnym
configiem, manifestem i evidence. Workspace zapisze oczekiwane digesty outputów,
a jedna blokada procesowa obejmie sprawdzenie stanu awarii i całą publikację.
Generic reservation będzie otwierać rodziców przez bezpieczny spacer deskryptorów;
niepewne sprzątanie pozostawi stan fail-closed zamiast usuwać niezweryfikowaną
ścieżkę.

**Technologie:** Python 3.13+, `dataclasses`, deskryptory POSIX/macOS,
`pytest`, `ruff`, `mypy`, `uv`.

**Spec:** wymagania użytkownika z PR #443 oraz `PROMPT.md` i
`docs/evaluation-dataset.md`.

## Ograniczenia globalne

- Wszystkie testy używają wyłącznie syntetycznych katalogów tymczasowych.
- Analizowany ani zapieczętowany holdout nie może zostać otwarty ani odczytany.
- Pełna tożsamość admission obejmuje config, source, dataset, merge commit oraz
  `verified`, `reason` i digest payloadu weryfikacji.
- Zmiana publicznego kontraktu wymaga aktualizacji wszystkich callerów i testów.
- Przed commitem przejdą testy właściwe, `ruff check .`, `ruff format --check .`,
  `mypy .` oraz pełny odpowiedni `pytest`.

---

### Zadanie 1: Zablokowanie caller-controlled admission

**Pliki:**

- Modyfikuj: `src/polis/evaluation/holdout_secure_io.py`,
  `src/polis/evaluation/holdout_execution.py`.
- Testuj: `tests/test_holdout_secure_io.py`,
  `tests/test_holdout_secure_io_adversarial.py`.

1. Dodaj test, który przekazuje forged `ExternalAdmission`/proof z poprawnym
   digestem datasetu, ale błędnym config/source/merge/evidence i oczekuje
   `HoldoutAdmissionError` bez utworzenia markera.
2. Uruchom ten test samodzielnie i potwierdź RED.
3. Zmień `reserve_dataset`, aby przyjmował pełny zweryfikowany admission proof,
   a secure boundary porównał wszystkie pola evidence z własnym configiem,
   manifestem i `merge-verification.json`; `run-authorization.json` pozostaje
   weryfikowany przez `load_external_admission` przed wejściem do tej granicy.
4. Usuń caller-controlled `JsonObject` z autoryzacyjnego API; identity markera
   wyprowadź wyłącznie ze zweryfikowanego admission.
5. Uruchom test admission oraz istniejące testy workspace i potwierdź GREEN.

### Zadanie 2: Integralność outputów workspace

**Pliki:**

- Modyfikuj: `src/polis/evaluation/holdout_secure_io.py`.
- Testuj: `tests/test_holdout_secure_io_adversarial.py`.

1. Dodaj test mutacji markeru i raportu po publikacji; odczyt musi zakończyć się
   `HoldoutAdmissionError`, a trusted output nie może zostać zaakceptowany.
2. Uruchom test i potwierdź RED.
3. Rejestruj digest oraz oczekiwany stan każdego outputu utworzonego przez bieżący
   workspace i wymagaj zgodności przy `read_output`, `output_exists` oraz odczycie
   markeru używanym przez wykonanie.
4. Zachowaj istniejące odrzucanie symlinków, hardlinków, zmian inode/metadata i
   mutacji w trakcie odczytu; po każdej zmianie uruchom testy focused.

### Zadanie 3: Globalna publikacja i fail-closed cleanup

**Pliki:**

- Modyfikuj: `src/polis/evaluation/holdout_secure_io.py`.
- Testuj: `tests/test_holdout_secure_io_adversarial.py`.

1. Dodaj deterministyczny test dwóch workspace'ów publikujących równolegle przy
   istniejącym `holdout.publication.failed`; drugi nie może opublikować outputu.
2. Dodaj test podmiany tymczasowej nazwy po weryfikacji ownership; cleanup ma
   pozostawić błąd permanentny i nie usuwać obcego pliku.
3. Uruchom oba testy i potwierdź RED.
4. Wprowadź process-global lock obejmujący failure-state check, publikację,
   unlink tymczasowego hardlinku i końcowy fsync. Przy niepewnym ownership nie
   wykonuj unlink po nazwie; przejdź do permanent failure.
5. Uruchom focused suite i potwierdź GREEN.

### Zadanie 4: Bezpieczne generic reservation i typowanie

**Pliki:**

- Modyfikuj: `src/polis/evaluation/holdout_reservation.py`.
- Testuj: `tests/test_holdout_reservation.py`.

1. Dodaj test nested symlink oraz podmiany rodzica między walidacją a otwarciem;
   marker nie może trafić poza zweryfikowaną ścieżkę.
2. Uruchom testy i potwierdź RED.
3. Otwieraj ścieżkę komponent po komponencie przez `dir_fd` i `O_NOFOLLOW`,
   zachowując dozwolone canonical paths na macOS; użyj otwartego deskryptora
   rodzica do exclusive create i fsync.
4. Zaktualizuj testowe implementacje `DurabilityFilesystem` do pełnych adnotacji
   zgodnych z nowym API i napraw wszystkie błędy `mypy .`.
5. Uruchom reservation suite oraz `mypy .` i potwierdź GREEN.

### Zadanie 5: Pełna weryfikacja, commit i push

**Pliki:** wszystkie zmienione w zadaniach 1–4.

1. Uruchom focused suite bez realnego holdoutu.
2. Uruchom `ruff check .`, `ruff format --check .`, `mypy .` oraz pełny
   odpowiedni `pytest` bez runnera realnego holdoutu.
3. Przejrzyj diff, status i zakres plików; pozostaw `.omo/` nietknięte.
4. Utwórz jeden skupiony commit odnoszący się do `#427`.
5. Wypchnij branch PR #443 i potwierdź zdalny SHA.
