# Jednorazowy holdout A+B

Ten katalog zamraża prerejestrację eksperymentu `polis-a-b-one-shot-v1` przed
ujawnieniem zapieczętowanego zbioru. Pierwszy pull request zawiera wyłącznie
kontrakt, runner, testy i metadane. Nie zawiera tekstu przypadków, odpowiedzi
wzorcowych, markera konsumpcji ani raportów wyniku.

Runner i `python -m polis.evaluation` są narzędziami wyłącznie repozytoryjnymi.
Wheel i sdist produktu wykluczają `evaluation/__main__.py`, wszystkie moduły
`evaluation/holdout_*.py` oraz katalog eksperymentu; instalacja pakietu nie
udostępnia tego polecenia.

Plik `config.json` ustala jedyną dozwoloną komendę, taksonomię, metryki, progi,
20 dokładnych tożsamości źródeł oraz politykę bez ponowień. Plik
`dataset.manifest.json` opisuje niezależnie sprawdzony zbiór CC0 tylko za pomocą
agregatów i skrótów SHA-256. Wiąże rolę
`independent-dataset-reviewer`, werdykt `APPROVE`, pokrycie 52/52 oraz skróty
zatwierdzonego manifestu i payloadu review. Runner sprawdza te metadane przed
rezerwacją. `preregistration.json` zapisuje zatwierdzone decyzje i wymóg osobnej
autoryzacji po podpisanym scaleniu pierwszego PR-a.

Po scaleniu niezależny operator umieszcza poza śledzonym drzewem repozytorium
`cases.json`, `merge-verification.json` i `run-authorization.json` w katalogu
`.omo/sealed/a-b-one-shot-v1/`. Konfiguracja zamraża te ścieżki i schematy,
lecz nie zgaduje przyszłego SHA scalenia ani payloadu weryfikacji. Brak,
niezgodność lub nieaktualność któregokolwiek dowodu zatrzymuje CLI przed
rezerwacją i przed dostępem do datasetu.

`merge-verification.json` jest atestacją operatora zmaterializowaną po
sprawdzeniu live odpowiedzi GitHub API i musi zachować surowe pola podpisu oraz
payloadu. Runner niezależnie wykonuje offline `git verify-commit` dla dokładnego
SHA. `run-authorization.json` zachowuje pełną tożsamość nowego komentarza issue
#243 o całkowitym identyfikatorze ściśle większym niż `5228447541`. Runner
konstruuje z niego dokładny URL, wymaga autora `PSyron`, czasu późniejszego od
pełnego preflightu, dokładnego ciała z trzema wiązaniami digestów oraz digestu
całej atestacji. Te pola i ich samodzielnie obliczony skrót nie ustanawiają
autoryzacji. Operator zapisuje odłączony podpis SSH ED25519 w
`.omo/sealed/a-b-one-shot-v1/run-authorization.sig`. Runner weryfikuje podpis
nad dokładnymi kanonicznymi bajtami `run-authorization.json`: UTF-8, klucze sortowane,
zapis zwarty i końcowy LF. Następnie wykonuje lokalnie `ssh-keygen -Y verify`
dla tożsamości `PSyron`, przestrzeni nazw `polis-holdout-authorization-v1` i
zaufanego klucza o odcisku
`SHA256:JvdjEgHYEQPsrsthSO5GnrM7saNvsanY5uJl89B0lQk`. Brak lub niezgodność
podpisu zatrzymuje wykonanie przed rezerwacją i dostępem do datasetu. Runner nie
wykonuje zapytań sieciowych.

Runner nie wyszukuje `ssh-keygen` przez `PATH`. Ten jednorazowy eksperyment jest
zamrożony wyłącznie dla hosta `Darwin`/`arm64` i binarki
`/usr/bin/ssh-keygen`; nie deklaruje obsługi wykonania badawczego na Linux ani
Windows. Zwykła zgodność produktu Polis z innymi platformami pozostaje bez zmian.
Po preflighcie
`run-authorization.json` wiąże wybraną ścieżkę i SHA-256 binarki. Runtime
otwiera ją bez podążania za symlinkami, sprawdza zwykły plik, właściciela,
uprawnienia, stabilność tożsamości oraz skrót, a następnie uruchamia dokładnie
tę binarkę z oczyszczonym środowiskiem i zamkniętymi deskryptorami pobocznymi.

Wszystkie wrażliwe pliki są otwierane względem utrzymywanych deskryptorów
katalogów z zakazem podążania za symlinkami. Marker i raporty są tworzone
wyłącznie względem zweryfikowanego katalogu eksperymentu.

Do czasu zakończenia ostatniego preflightu i opublikowania zgody powiązanej z
SHA nie wolno wykonywać komendy `run-holdout`. Każda utworzona rezerwacja jest
trwała: przerwanie, błąd lub częściowy wynik zużywają jedyną próbę.

## Wynik jedynej próby

Autoryzowana próba dla merge SHA
`b22e389cb5309ee17f35f1884b90b4cbaa7efd34` zakończyła się werdyktem
`fail_threshold`. Komenda została wykonana dokładnie raz, zakończyła się kodem
`0`, a trwały marker uniemożliwia ponowienie.

Agregaty jakości wyniosły: precision, recall i F1
`0.9473684210526315`, exact-span accuracy `0.9473684210526315`,
exact-correction accuracy `1.0` oraz correct-sentence false-alarm rate
`0.037037037037037035`. Spośród 20 dokładnych tożsamości 12 otrzymało `pass`,
jedna `fail_threshold`, a siedem `insufficient_evidence`. Wynik nie uruchamia
strojenia ani ponownego pomiaru. Każda tożsamość bez `pass` pozostaje
review-only; ewentualna promocja tożsamości z `pass` wymaga osobnego issue i
dokładnego klucza polityki.

`normalized-report.json` został odbudowany byte-for-byte z raportu surowego.
`result.manifest.json` wiąże marker, oba raporty, źródło, konfigurację, dataset
i payload weryfikacji merge. Raporty nie zawierają tekstów przypadków, goldów,
sugestii ani prywatnych ścieżek.
