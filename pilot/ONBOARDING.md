# От нуля до первой заявки: Polymarket с Mac (Сербия), пилот 20-50 USD

Всё ниже прочитано **2026-11-27** в официальных источниках: docs.polymarket.com, help.polymarket.com,
github.com/Polymarket/polymarket-cli. Чего источники не говорят, помечено **«не подтверждено»**.
Вы ничего не создаёте и не вводите, пока не прочли шаги. Ключ никогда не отправляйте в чат, в git, в облако.

## Рекомендация

1. Пилот: **путь A** — счёт на polymarket.com, пополнение там же, торговля из официального Python SDK
   (`polymarket-client`, он уже в `pilot/`). Это меньше всего шагов: сайт сам создаёт кошелёк и пополняет его.
2. Официальный **CLI для этого пути не берите**: его README знает типы `proxy`, `eoa`, `gnosis-safe`, а Deposit Wallet
   (тип всех счетов с 4 мая 2026) не упоминает; `approve set` требует MATIC; последний релиз v0.1.5 (10 марта, год не виден).
3. Ключ подписи нужен и в пилоте (владелец счёта). Риск ограничен суммой: держите на счёте 20-50 USD, не 200.
4. Для робота «всегда включён» — **Session Key** (шаг A5): отдельный ключ только для торговли, вывести деньги им нельзя, срок 180 дней.
5. Путь B (свой кошелёк EOA) — больше шагов и нужен POL на газ; для пилота не нужен.

## Что такое официальный CLI (вопрос 1)

- Репозиторий https://github.com/Polymarket/polymarket-cli, MIT. README открывается словами: «early, experimental
  software ... do not use with large amounts of funds». API и команды могут меняться без предупреждения.
- Установка на macOS: `brew tap Polymarket/polymarket-cli https://github.com/Polymarket/polymarket-cli` и
  `brew install polymarket`. Есть ещё `curl ... install.sh | sh` и `cargo install --path .` из исходников
  (curl в shell запускает чужой скрипт, берите Homebrew). Обновление: `polymarket upgrade`.
- Кошелёк: `polymarket wallet create`, `wallet import 0xKEY`, `wallet address`, `wallet show`, `wallet reset`.
  Ключ ищется по порядку: `--private-key`, `POLYMARKET_PRIVATE_KEY`, `~/.config/polymarket/config.json`
  (ключ лежит в этом файле открытым текстом).
- Баланс: `clob balance --asset-type collateral`. Разрешения: `approve check`, `approve set` (в цепочке, нужен MATIC).
- Заявки: `clob create-order --token ID --side buy --price 0.50 --size 10` (есть `--post-only`), `clob market-order
  --token ID --side buy --amount 5`. Отмена: `clob cancel ID`, `cancel-orders`, `cancel-market`, `cancel-all`.
- JSON для скриптов: да, `-o json` у каждой команды; ошибки в JSON уходят в stdout как `{"error": ...}`, выход не ноль.
- Типы подписи: `proxy` (по умолчанию), `eoa`, `gnosis-safe` (`--signature-type`). Deposit Wallet и V2 в README нет.
  Это значит: с новым счётом сайта CLI может не заработать. **Не подтверждено**, работает ли он с Deposit Wallet.
- Свежесть: pUSD в README есть (разрешения), релизных заметок про pUSD/V2 нет.
- Источники: https://raw.githubusercontent.com/Polymarket/polymarket-cli/main/README.md,
  https://github.com/Polymarket/polymarket-cli/releases (оба 2026-11-27).

## Путь A. Счёт на сайте + SDK (пилот)

1. Откройте polymarket.com без VPN. Сербии нет в списках запрещённых стран, но прямого «разрешено» тоже нет;
   VPN для обхода запрещён условиями (https://help.polymarket.com/en/articles/13364163-geographic-restrictions).
2. Sign Up: Google, или email (шестизначный код на почту при каждом входе), или внешний кошелёк (MetaMask/Rabby/Phantom;
   подпишите два сообщения) (https://help.polymarket.com/en/articles/13369877-how-to-sign-up). Новый счёт — Deposit Wallet
   (https://docs.polymarket.com/trading/wallets-auth.md).
3. Пополнение: Deposit → Transfer Crypto → токен и сеть → скопируйте адрес, сверьте с профилем, отправьте
   (https://help.polymarket.com/en/articles/13369887-how-to-deposit). Деньги приходят как pUSD на адрес кошелька счёта
   (https://docs.polymarket.com/trading/bridge/deposit.md). Минимумы: справка называет Ethereum 20 USD, Solana 3 USD;
   документация API — Polygon USDC 2 USD, Ethereum 7 USD (https://docs.polymarket.com/trading/bridge/supported-assets.md);
   цифры расходятся, смотрите то, что покажет сайт. Не тот токен или сеть — деньги могут пропасть
   (восстановление: recovery.polymarket.com). **Не подтверждено**: есть ли оплата картой и как купить крипту за EUR.
4. Ключ подписи. Для email-счёта справка даёт путь: войти в Polymarket, открыть https://reveal.magic.link/polymarket,
   войти, Export Private Key, сохранить, выйти
   (https://help.polymarket.com/en/articles/13364258-how-do-i-export-my-key). Статья только про email: для Google и для
   внешнего кошелька шагов нет (у внешнего кошелька ключ — ваш собственный, экспорт делает сам кошелёк). **Не подтверждено**,
   что ключ из Magic подходит к новому Deposit Wallet (в документации сказано лишь, что Proxy-кошельки создавались через
   Magic/Google). Проверка: `smoke.py auth --live` покажет адрес подписанта и роль ключа.
5. Сохраните ключ в файл с правами 600 (команды в `pilot/README.md`, раздел «Как хранить ключ»).
6. Адрес кошелька счёта — в меню профиля на сайте; переменная `PM_WALLET`. Это не секрет, но он связан с вами.
7. Подключение в SDK (Python): `AsyncSecureClient.create(private_key=..., wallet=<адрес из профиля>)`; тип кошелька
   определяет SDK (`client.wallet_type`: EOA 0, POLY_PROXY 1, GNOSIS_SAFE 2, DEPOSIT_WALLET 3). Адреса подписанта
   Polymarket показывает в Settings → API Keys → Relayer API Keys (поле Signer Address)
   (https://docs.polymarket.com/trading/wallets-auth.md, https://docs.polymarket.com/trading/quickstart.md).
8. Разрешения (approvals). Документация: заявка сама пытается восстановить недостающие разрешения на бирже, но заранее надёжнее
   `await client.setup_trading_approvals()` (безвозмездно через Relayer, повторный вызов безопасен; нужен ключ Relayer).
   Для рынков negative-risk это не делает разрешения Neg Risk Adapter: их ставят отдельно (`approve_erc20()`,
   `approve_erc1155_for_all()`). **Не подтверждено**, ставит ли сайт разрешения сам.
9. Первая заявка: `pilot/README.md`, шаги 0-5 (`conn_check.py`, `smoke.py auth`, `place`, `status`, `cancel`). Документация
   рекомендует иметь минимум 10 pUSD для первого ордера (https://docs.polymarket.com/trading/quickstart.md).
10. Газ (POL): для Deposit, Proxy и Safe кошельков действия идут через Relayer бесплатно, POL не нужен.

## Путь B. Свой кошелёк, созданный локально (не рекомендую для пилота)

1. Создать ключ: `polymarket wallet create` (CLI) либо свой. Ключ лежит в `~/.config/polymarket/config.json` открытым текстом.
2. Для EOA каждое действие в цепочке (разрешения, переводы, split/merge/redeem) идёт с вашего адреса и **требует POL
   на газ** (https://docs.polymarket.com/trading/wallets-auth.md). Сколько POL нужно, документация не говорит. **Не подтверждено.**
3. Получение pUSD: USDC.e оборачивают в pUSD контрактом CollateralOnramp (сначала `approve` на Onramp, потом
   `wrap(_asset, _to, _amount)`, 6 знаков; контракты и адреса на https://docs.polymarket.com/concepts/pusd.md; вызов
   отклоняется, если USDC.e на паузе). Другой путь: мост `POST /deposit` с адресом кошелька, затем перевод на этот адрес
   (USDC или USDC.e автоматически превращаются в pUSD). Работает ли мост для чистого EOA, **не подтверждено**: документация
   говорит об адресе «Polymarket wallet».
4. `polymarket approve set` (нужен газ), затем `clob create-order` с `--signature-type eoa`. Но с обычным EOA заявки
   на сайте не будут видны так, как у счёта сайта: связь с профилем **не подтверждена**.
5. Минимум для начала: хватит нескольких долларов pUSD и небольшого количества POL; точные суммы **не подтверждены**.

## A5. Session Key для робота (после пилота)

Условия: счёт — Deposit Wallet (Safe и Proxy не поддерживаются); нужны ключ владельца и ключ Relayer (или Builder);
срок строго 180 дней (https://docs.polymarket.com/trading/session-keys.md, 2026-11-27).

1. Создайте ключ Relayer: polymarket.com → Settings → API Keys → Relayer API Keys; запишите API Key и Signer Address.
2. Сгенерируйте новую пару ключей: `session_key = Account.create()` (eth_account); храните только в файле с правами 600.
3. Клиент владельца: `AsyncSecureClient.create(private_key=<ключ владельца>, wallet=<Deposit Wallet>,
   api_key=RelayerApiKey(key=..., address=<Signer Address>))`.
4. `await secure_client.authorize_session_key(address=session_key.address)`; без `scopes` — все площадки, или `scopes=(SessionKeyKnownScope.CLOB,)`.
5. Дождитесь, пока адрес появится в `await secure_client.fetch_session_keys()`; до этого ключ не работает.
6. Клиент робота: `AsyncSecureClient.create(private_key=<ключ сессии>, wallet=<Deposit Wallet>)`, API-ключ не нужен;
   `place_limit_order(asset_id=..., side="BUY", price="0.52", size="10")`.
7. Отмена: ключ сессии отменять не может, это делает клиент владельца (`cancel_wallet_orders()`, `cancel_all_wallet_orders()`).
   Отзыв: `await secure_client.revoke_session_key(address=...)`; доводится несколько минут.

## Кто что: сравнение

| | Шагов | Что может украсть утёкший ключ |
| - | - | - |
| A (сайт + SDK) | меньше всего | ключ владельца: весь счёт, поэтому 20-50 USD |
| B (EOA) | больше, нужен POL | весь кошелёк |
| A + Session Key | A плюс 7 шагов | ключ сессии: только торговля, без вывода; владелец хранится офлайн |

## Не подтверждено

- Работает ли официальный CLI с Deposit Wallet; год релиза v0.1.5 (на странице «10 Mar»).
- Откуда ключ подписи у счёта Google и у нового email-счёта Deposit Wallet; подходит ли ключ Magic к новому кошельку.
- Ставит ли сайт разрешения на торговлю сам; нужен ли ключ Relayer для первой заявки (по документации — для `setup_trading_approvals`).
- Оплата картой и покупка крипты за EUR на сайте; точные минимумы (справка и API расходятся).
- Сколько POL нужно EOA; работает ли мост для EOA.
- Сербия прямо разрешена: нет, её просто нет в списках ограничений; окончательно ответит `conn_check.py`.
