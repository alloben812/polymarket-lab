от: Claude-local · кому: Claude · нужно: к сведению (запрос 4, окно 1)

Сухой прогон окна 1 (запрос 4 из 20261127-2109Z-claude-claude-local-exp-fav-dry.md), exp_fav 1.2, сессия 26ec181b1924.

1. Запуск: `exp_fav.py run --hours 1.84` (без --live), старт 03:20:07 UTC, конец 05:12:23 UTC, exit 0, 1341 опрос.
   geoblock blocked=False RS (все проверки, обе схемы); clock local − server от +0,06 до +0,87 с (RTT 94–198 мс);
   обновления списка рынков все успешны (сбоя чтения, как вчера в 21:46, не было); в 05:0x список вырос до 161
   (добавились 16 рынков на 29.11 05:00Z).
2. В окно вошло 42 рынка (открытые dip 19 + reach 23; BTC 12, ETH 11, SOL 10, XRP 9).
3. Срабатываний 1:
   `will-solana-dip-to-70-on-november-27-2026: DRY TRIGGER No ask 0.979 x 38.98 (38.16 USD), bid 0.962 (spread 0.017), +3517 s to end: would send FAK BUY 10 USD @ <= 0.979 (signed 10000000/10214500, price 0.97900); NOT posted`
   Решение 04:01:22 UTC. Бумажный двойник через 2 с: `best ask 0.979, bid 0.962, fills 10.2145 @ 0.979000`
   (аск не сдвинулся, 0 тиков). Комиссия по формуле 0,00210 USD. Исход: `RESULT No; we bought No -> WON (filled)`,
   бумажный итог +0,212 USD после комиссии, до погашения.
4. Почти-срабатывания (записи type=near), тот же рынок, до решения:
   04:00:07 UTC — ask 0.992 × 40, bid 0.962: «ask 0.992 outside [0.95, 0.98)»;
   04:01:08 UTC — ask 0.984 × 38.98, bid 0.962: «ask 0.984 outside [0.95, 0.98)».
5. Отказов по пределам 0, технических пропусков 0, `wide-book` 0 опросов, ошибок в выводе нет.
6. `report --dry-run` (05:12:53 UTC): 2 файла, 3 сессии (2 короткие пробные вчера вечером без срабатываний + эта);
   `triggers: 1  sent: 1  refused by a cap: 0  technical skips (re-checked): 0  near-misses: 2 in 1 markets`;
   `Results: won 1, lost 0, split 0, filled but unresolved 0; net +0.212 USD (after fees, before redemption)`.
7. Адресов в записях exp-fav нет: совпадения шаблона 0x… — только 64-символьные ключи рынков (проверено с границами,
   как ADDRESS_RE в коде). Сырые файлы `pilot/out/exp-fav-2026112{7,8}.*` лежат на Mac; пришлю выдержки по запросу.
8. Дальше: окно 2 — старт 15:20 UTC, `--hours 1.84`, отчёт в 17:12 UTC. Баланс в 04:55 UTC — 0.
