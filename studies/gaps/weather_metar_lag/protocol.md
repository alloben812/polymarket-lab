# Weather: METAR publication -> Polymarket price lag (protocol written 2026-11-27 BEFORE running; variant W1)

Question: when a routine METAR that sets a new daily maximum appears at the official resolution source
(aviationweather.gov, `receiptTime`), how long do the now-impossible buckets keep a non-zero price, and is
anything demonstrably tradable at the stale price after publication?

- Universe: closed gamma events `highest-temperature-in-<city>-on-<date>` with observation dates 2026-11-21 ..
  2026-11-26 (1-minute price history is kept >= 7 days), buckets in whole degrees C only, as many cities as
  gamma returns (cap 150 events).
- Truth: the event's own `resolutionSource` URL (station id, `date`, `hours`), fetched as `format=json` to get
  `obsTime`, `receiptTime`, `rawOb`. Routine reports only (no SPECI). Qualifying value = T-group tenths if present,
  else body temperature; rounded half-up to whole C. Observation day = [date-27h, date-3h) UTC (rule inferred
  from two events; VALIDATED per event: my computed daily maximum bucket must equal the resolved winner, otherwise
  the event is dropped and counted).
- Kill event: a routine observation whose rounded value exceeds the running maximum of the day. Dead bucket = the
  bucket that contained the previous running maximum (skipped if the new value is in the same bucket).
  Kept only if the dead bucket's last price before `obsTime` was >= 0.05.
- Measure (prices-history, 60 s buckets): dead-bucket Yes price at receipt -5, -1, 0, +1, +2, +5, +10, +30 min
  (last point at or before the offset). Report n, median, share still >= 0.02 and >= 0.05 at each offset. Same
  for the price relative to `obsTime` (the observation is made ~3-5 min before the source shows it).
- Tradability: tape of the dead market for [receipt, receipt+600 s]: taker SELLs at price >= 0.02 (someone hit a
  stale bid: gain = price - fee) and taker BUYs (someone still buying a dead bucket: a resting ask would have
  earned price). Block-time stamps are 2-3 s late. Fee 0.01*p*(1-p).
- End-of-day: at the receipt of the day's last routine observation the winner is certain. Winner's price at that
  receipt and +5, +15, +60 min; share below 0.99 / 0.97.
- Unit = event (city-day). One variant planned; any extra variant is counted and reported.
- Known limits before running: prices-history is not the book (meaning of the point - mid or last trade - must be
  checked); no depth; six days; the aviationweather `receiptTime` is when NOAA got the report, other channels
  (national met services, airport feeds) may be earlier or later.
