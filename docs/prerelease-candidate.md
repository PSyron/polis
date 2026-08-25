# Kandydat do wydania

Następnym zamierzonym wydaniem runtime'u jest `0.3.0`. Jest to wydanie minor,
ponieważ od `0.2.0` przybyły kompatybilne funkcje deterministycznego runtime'u
i publiczne zachowania; nie jest to wyłącznie zestaw poprawek patch. Wersja w
`pyproject.toml` pozostaje `0.2.0` do chwili rozpoczęcia osobnego wykonania
wydania.

Poniższe polecenia stają się właściwą ścieżką kandydata dopiero po osobnej
zmianie wykonującej wydanie, która ustawi spójną wersję `0.3.0` w metadanych
źródła, artefaktach i manifeście. Na obecnym `main` z wersją `0.2.0` służą
wyłącznie jako opis bramki i nie wolno ich używać do utworzenia kandydata
`0.3.0`.

Kandydat v1 dotyczy wyłącznie deterministycznego runtime'u offline. Przed
publikacją uruchom:

```console
uv run --locked --extra dev pytest
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
uv run --locked --extra dev python scripts/prepare_build_wheelhouse.py \
  --lock uv.lock --output build-wheelhouse \
  --manifest build-wheelhouse-manifest.json
uv run --locked --extra dev python -m build --no-isolation --outdir dist
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py \
  --dist dist
mkdir build-smoke-cwd
uv run --locked --extra dev python scripts/verify_distribution_install.py \
  --dist dist --wheelhouse build-wheelhouse \
  --wheelhouse-manifest build-wheelhouse-manifest.json \
  --smoke-cwd build-smoke-cwd
uv run --locked --extra dev python scripts/verify_prerelease_candidate.py \
  --dist dist --wheelhouse build-wheelhouse \
  --wheelhouse-manifest build-wheelhouse-manifest.json \
  --source-commit "$(git rev-parse HEAD)"
```

Potwierdź zgodność wersji, skróty artefaktów, test instalacji offline i stan
publicznego API. Wydanie nie zależy od uruchomienia badań ani od otwierania
zamrożonych danych. Opcjonalne badania nad modelem nigdy nie blokują wydania
runtime'u. Ścieżka wydania runtime'u nie wymaga modelu, procesu Java, usługi
sieciowej, korpusu badawczego ani zużytego holdoutu. Szczegóły zawiera
[weryfikacja dystrybucji](distribution-verification.md).

Plik `docs/regression-threshold-proposal-v1.json` pozostaje odroczoną,
niewymuszoną propozycją, niezależną od `0.3.0` i oczekującą na odrębną decyzję
maintainera. Historyczny `quality-threshold-proposal-v1.json` jest wyłącznie
niezmiennym aliasem zgodności.
Nie kwalifikuje żadnego zachowania review-only do automatycznej korekty. Także
opcjonalna kwalifikacja morfologii, praca modelowa, kalibracja i holdouty nie
wchodzą do krytycznej ścieżki tego wydania.

`--source-commit` musi być dokładnym SHA bieżącego `HEAD`, a worktree musi być
czysty jeszcze przed uruchomieniem testów, budowy i tworzenia manifestu.
Workflow może najpierw wykonać jedyną budowę do katalogu tymczasowego, a potem
wywołać ten sam publiczny weryfikator z `--verify-existing`. Ta flaga pomija
wyłącznie ponowną budowę; nadal uruchamia kontrole jakości, artefaktów,
instalacji offline i zapis manifestu.

## Tożsamość i manifest wydania

Obecne polecenie `release_identity.py candidate --state candidate-absent`
kwalifikuje pierwszy upload projektu i wymaga braku całej nazwy projektu na
PyPI. Nie jest właściwą kontrolą kolejnej wersji istniejącego projektu, dlatego
nie wolno użyć go dla `0.3.0`. Osobne issue wykonujące wydanie musi najpierw
dodać i przetestować wersjoświadomą kontrolę nieobecności dokładnej wersji
`0.3.0`, zachowując weryfikację zdalnego tagu i GitHub Release. Dopiero ten
kontrakt może dostarczyć wykonywalne polecenie kandydata i później związać
adnotowany tag `v0.3.0` z dokładnym `--source-commit`.

Manifest zawiera wyłącznie wersję schematu, tożsamość oraz nazwę, rozmiar i
SHA-256 wheela i sdist. Sprawdź go przed przekazaniem dalej:

```console
uv run --locked --extra dev python scripts/release_identity.py verify-manifest \
  --manifest dist/release-manifest.json --dist dist \
  --source-commit "$(git rev-parse HEAD)"
uv run --locked --extra dev python scripts/release_identity.py verify-policy
```

`docs/project/release-policy.json` wiąże niezmienny digest zaakceptowanego
planu. Żaden argument wywołania ani przyszły receipt nie może zastąpić tego
digestu.

Receipt bramki jest osobnym plikiem JSON ze ściśle wymaganymi polami: wersją
schematu, commitem źródłowym, digestami obu manifestów, dodatnim identyfikatorem
kwalifikacji, digestem planu, czterema akceptacjami `P1`–`P4`, potwierdzeniem
`okay` i czasem zapisu. Utwórz go z plików manifestów; `--plan` może wskazywać
plan albo jego dokładny skrót SHA-256. Ścieżka przechodzi tylko, gdy jej hash
jest zgodny z policy; poniżej użyto zatwierdzonego skrótu. Walidator nie pozwala
zmienić tego kontraktu. `recorded_at` ma wyłącznie kanoniczny format UTC
`YYYY-MM-DDTHH:MM:SSZ`; create zapisuje pełne sekundy, a ułamki sekund i offsety
nie są dozwolone:

```console
uv run --locked --extra dev python scripts/validate_release_gate_receipt.py \
  create --source-commit "$(git rev-parse HEAD)" \
  --release-manifest dist/release-manifest.json \
  --wheelhouse-manifest build-wheelhouse-manifest.json \
  --qualify-run-id 17 --plan "$(uv run --locked --extra dev python scripts/release_identity.py verify-policy | cut -d= -f2)" \
  --release-policy docs/project/release-policy.json \
  --p1 APPROVE --p2 APPROVE --p3 APPROVE --p4 APPROVE \
  --user-approval okay --output dist/release-gate-receipt.json
```

Przed użyciem receiptu w kolejnym kroku ponownie podaj te same wiążące wejścia.
Walidator rehashuje manifesty i odrzuca różnicę pola, pliku, planu, policy,
akceptacji, commitu albo run ID:

```console
uv run --locked --extra dev python scripts/validate_release_gate_receipt.py \
  validate --receipt dist/release-gate-receipt.json \
  --source-commit "$(git rev-parse HEAD)" \
  --release-manifest dist/release-manifest.json \
  --wheelhouse-manifest build-wheelhouse-manifest.json \
  --qualify-run-id 17 --plan "$(uv run --locked --extra dev python scripts/release_identity.py verify-policy | cut -d= -f2)" \
  --release-policy docs/project/release-policy.json \
  --p1 APPROVE --p2 APPROVE --p3 APPROVE --p4 APPROVE \
  --user-approval okay
```
