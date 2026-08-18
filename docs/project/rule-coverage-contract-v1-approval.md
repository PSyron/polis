# Rekord akceptacji kontraktu pokrycia reguł v1

- Issue: #364
- ADR: ADR-0028
- Kontrakt: `polis-conservative-v1-rule-coverage`
- Data: 2026-08-18
- Maintainer: Paweł Cyroń
- Status: approved

Maintainer akceptuje w tym zakresie minima próbkowania oraz politykę bramek:
osobne profile i kategorie, zero-tolerance dla precision i correct-sentence
false alarms, fail-closed dla niepełnych dowodów oraz zakaz wybierania progów
v4 przed zmierzonym baseline'em.

Ta akceptacja nie promuje żadnej reguły do automatic correction, nie zatwierdza
żadnej nowej rodziny ani nie ustala progów jakości v4. Każda z tych decyzji
wymaga własnych dowodów i osobnej akceptacji.
