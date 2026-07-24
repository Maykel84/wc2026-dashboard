# WC2026 Ćwierćfinały — interaktywny dashboard (Streamlit)

Panel taktyczno-statystyczny na bazie zestawu danych WC2026 (4 ćwierćfinały, 21 tabel CSV per mecz). Zbudowany na `Streamlit` + `mplsoccer` (mapy strzałów, heatmapy, mapy podań w pole karne) + `Plotly` (xG, momentum, fazy gry).

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
streamlit run app.py
```

Aplikacja otworzy się w przeglądarce pod `http://localhost:8501`.

## Struktura

- `app.py` — główna aplikacja: nawigacja boczna (podsumowanie turnieju / 4 mecze), 7 zakładek na stronie meczu (Informacje i składy, Statystyki ogólne, Mapa strzałów i xG, Momenty meczu, Fazy gry i pressing, Heatmapy, Wejścia w pole karne) i 6 zakładek zbiorczych na stronie startowej.
- `data_loader.py` — wczytywanie i cache'owanie 21 tabel × 4 mecze (`st.cache_data`).
- `pitch_charts.py` — funkcje rysujące na boisku (mplsoccer): `shot_map`, `heatmap`, `pass_map`.
- `data/` — 84 pliki CSV (4 mecze × 21 tabel).
- `previews/` — przykładowe zrzuty wygenerowanych wizualizacji.

## Wdrożenie na konkurs (publiczny link, bez instalacji dla oceniających)

**Opcja A — Streamlit Community Cloud (zalecane, darmowe):**
1. Wrzuć całą zawartość tego folderu (`app.py`, `data_loader.py`, `pitch_charts.py`, `requirements.txt`, `data/`) do publicznego repozytorium na GitHub.
2. Wejdź na [share.streamlit.io](https://share.streamlit.io), zaloguj się kontem GitHub, kliknij "New app", wskaż repo i plik `app.py`.
3. Po chwili dostajesz publiczny URL (np. `twoja-nazwa.streamlit.app`) — to jest link do przekazania na konkurs.

**Opcja B — Hugging Face Spaces:** podobny proces, wybierz szablon "Streamlit" przy tworzeniu nowego Space, wgraj te same pliki.

## Metodologia danych (do pokazania w prezentacji konkursowej)

Każdy wiersz w każdej z 21 tabel ma flagę `data_source`: `REAL`, `REAL_EVENT_MODELED_XG`, `REAL_OUTCOME_CORRECTED`, `MODELED`, `MODELED_PLACEHOLDER`. Metryka "Realne/zakotwiczone dane" widoczna na górze każdej strony meczu pokazuje ten % wprost — to jest główny wyróżnik tej analizy na tle typowych, czysto statystycznych zestawień: każda liczba jest oznaczona pod kątem tego, czy pochodzi z realnego źródła, czy jest dosyntetyzowana i przeskalowana pod realne agregaty końcowe (xG, strzały, gole, zmiany).
