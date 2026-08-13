# Screener Inversione Large Cap — Guida rapida

App Streamlit che scansiona FTSE MIB, Nasdaq 100 e S&P 500 cercando titoli **large cap in forte ribasso** (drawdown >=40% dal massimo, configurabile) la cui discesa sta **decelerando**, che stanno **formando una base** vicino al POC, e propone il segnale solo alla **rottura della base con volume in conferma** e **R:R >= soglia minima (default 1:4)**.

## Logica della strategia (in ordine di applicazione)

1. **Large cap**: solo titoli appartenenti a FTSE MIB / Nasdaq 100 / S&P 500 (large cap per costruzione dell'indice)
2. **Drawdown**: il prezzo deve essere sceso di almeno X% (default 40%) dal massimo dell'ultimo anno di borsa
3. **Decelerazione**: il tasso di discesa recente (ultimi 20gg) deve essere meno negativo di quello dei 20gg precedenti — la caduta sta rallentando
4. **POC sotto il prezzo**: l'area di massimo volume scambiato (accumulo) deve trovarsi sotto il prezzo attuale
5. **Base/consolidamento**: negli ultimi ~25gg il prezzo deve essersi mosso in un range stretto (default max 15% di ampiezza) — segno di lateralizzazione/pattern di inversione
6. **Rottura**: il prezzo chiude sopra il massimo della base, con volume >= 1,5x la media 20gg
7. **Filtro R:R**: il segnale diventa operativo (CONFERMATO) solo se esiste un target (resistenza storica o proiezione a misura di pattern) che garantisce R:R >= soglia minima (default 1:4) rispetto allo stop (minimo della base / ATR)

## Cosa contiene

| File | Funzione |
|---|---|
| `indicators.py` | POC (volume profile), drawdown, decelerazione, rilevamento base, ATR |
| `screener.py` | Applica tutti i criteri della strategia e genera i segnali |
| `data_fetch.py` | Liste componenti indici (da Wikipedia, aggiornate automaticamente) + storico prezzi + prezzo quasi real-time |
| `backtest.py` | Motore di backtest — **da eseguire prima di usare i segnali con capitale reale** |
| `telegram_alerts.py` | Invio alert al bot Telegram esistente |
| `app.py` | App Streamlit (screener live + backtest) |

## Nota sui prezzi "in tempo reale"

L'app usa `yfinance`, che fornisce prezzi con un ritardo tipico di pochi minuti durante l'orario di mercato — non è un feed a livello di millisecondo come un terminale professionale a pagamento. È lo stesso ordine di grandezza dei dati gratuiti che già vedi su TradingView/Scalable. La casella "Aggiorna con prezzo quasi real-time" nella sidebar sostituisce l'ultima chiusura giornaliera con l'ultimo prezzo scambiato disponibile, così i criteri vengono valutati su un prezzo aggiornato anche a mercato aperto, non solo sulla chiusura del giorno prima.

## Nota sulla scansione di centinaia di titoli

Scansionare tutti e tre gli indici insieme (FTSE MIB + Nasdaq 100 + S&P 500 = ~650 titoli) richiede diversi minuti per il download dei dati storici. È normale — vedrai una barra di avanzamento. Se vuoi risultati più veloci, seleziona un solo indice alla volta dalla sidebar.

## 1. Test in locale (5 minuti)

```bash
pip install streamlit yfinance pandas numpy requests
streamlit run app.py
```

Si apre in automatico nel browser su `localhost:8501`.

## 2. Deploy gratuito su Streamlit Community Cloud (stesso hosting di dashboard_sfida.py)

1. Crea un repo GitHub con questi file + un `requirements.txt`:
   ```
   streamlit
   yfinance
   pandas
   numpy
   requests
   ```
2. Vai su [share.streamlit.io](https://share.streamlit.io), collega il repo GitHub
3. Seleziona `app.py` come file principale → Deploy
4. L'app è live gratis su un URL tipo `tuonome-app.streamlit.app`

## 3. Prima di usarlo per operare davvero

**Passo obbligatorio:** vai sulla tab "Backtest", esegui su almeno 2-3 anni di dati sull'universo che ti interessa (FTSE MIB, poi aggiungi S&P500/Nasdaq100/Stoxx600), e guarda:
- Win rate
- Expectancy media (deve essere positiva)
- Distribuzione esiti (quanti STOP vs TP1 vs TP2 vs TIMEOUT)

Se l'expectancy resta negativa anche con i filtri attivi, il problema non sono i parametri ma il metodo POC breakout stesso in quel regime di mercato — vale la pena saperlo prima, non dopo.

## 4. Estendere l'universo di ticker

`data_fetch.py` contiene solo una lista di esempio FTSE MIB. Per S&P 500 / Nasdaq 100 / Stoxx 600, il modo più robusto è:
- Scaricare la lista componenti da fonte ufficiale (es. pagina Wikipedia dell'indice, o file CSV holdings dell'ETF che già usi per il look-through)
- Salvarla come lista Python o CSV separato
- Passarla a `fetch_universe()` in `app.py`

## 5. Integrazione col bot Telegram esistente

In `telegram_alerts.py` trovi `send_signals(results_df, bot_token, chat_id)`. Basta richiamarla dopo `scan_universe()` usando lo stesso `bot_token`/`chat_id` che hai già configurato per le morning briefing, e schedularla (es. cron job su Railway/Fly.io) per girare dopo la chiusura di mercato — coerente col criterio "conferma su chiusura, non intraday" della spec.

## Note

- I filtri sono tutti parametrici (soglie volume, ADX, R:R minimo) e modificabili dalla sidebar dell'app senza toccare il codice
- Il backtest è vettorializzato per ticker singolo — su universi grandi (500+ titoli, anni di storico) può richiedere qualche minuto: normale
- yfinance a volte ha rate-limit o buchi nei dati per titoli meno liquidi; se noti dati mancanti, valuta una fonte a pagamento più affidabile (Twelve Data, Polygon.io) solo se il progetto scala
