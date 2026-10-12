# Джерела дослідження

Виміряні результати, заявлені умови та мій досвід мають різні рівні доказів. Дати перевірки, цитати й обмеження зберігаю разом із відповідними даними. Нижче — покажчик джерел; висновки й результати кожної картки — на [сторінці дослідження](../index.html).

## Публічні докази

| Матеріал | Дані й походження |
| --- | --- |
| Контрольна покупка за 158 ₴ | [Вимірювання й SHA-256](../data/measurements.json): початкові баланси й транзакції, квитанція Trustee, пізніші завершені екрани OKX / Bybit та історія активів Bybit |
| Історичні платежі та кешбек | [Історичні тести](../data/historical.json): USD-платежі OKX, Kolo, Solid, Simple та Bybit; попередня виплата Kolo зі сумою двох покупок |
| Поповнення й виведення | [Тести маршрутів](../data/funding-tests.json): скріни, точні токенові суми, gas і межі ончейн-перевірки; котирування відділені від виконаних операцій |
| Умови з застосунків | [Маніфест доказів і транскрипції](../data/terms-evidence.json): Prime, Bybit, COCA й WhiteBIT; екран апгрейду не підтверджує активний tier |
| Зображення карток | [Маніфест](../data/card-art.json): дев’ять очищених зображень із моїх гаманців і застосунків; це ілюстрації, а не докази тарифів |
| Внутрішні розрахунки Solid / Keyone | [Ончейн-зноска](../data/onchain-summary.json): токени WEUR / WUSD та валюти внутрішнього розрахунку |

До початкових 27 скрінів контрольної покупки додав інші докази; публічний набір тепер містить 125 доказових PNG, включно з підтвердженням зарахування WhiteBIT-кешбеку від 12.10.2026. Очищені файли в `screenshots/` доступні зі сторінки й маніфестів. Оригінали скріншотів видалив після фінальної перевірки 11.10.2026. [Очищення й приватність](privacy.md).

## Умови та сценарії

- [Кешбек і базовий / наступний tier](../data/cashback-tiers.json): офіційні правила, посилання й дата перевірки.
- [Earning](../data/earning.json): ставки з застосунків і довідок, активи, доступність для оплати та обмеження. Скріни Earning були лише для аналізу; їх не публікую. Збережені транскрипції не є виміряним річним доходом.
- [Емітенти](../data/card-issuers.json): публічні умови програм, мої уточнення й допоміжні BIN-результати. BIN-база не замінює індивідуальну угоду. Суперечності OKX та WhiteBIT і відмінність публічної програми Kolo залишаються невирішеними.
- [Посилання на картки](../data/card-links.json): офіційні сторінки без реферальних кодів, мої реферальні посилання й умови запрошень. Бонуси за реєстрацію не включені в рейтинг.
- [Бюджет і підписки](../data/budget-scenario.json): мій сценарій 1 000 USDT/міс. та надані ціни; це не перевірені рахунки.
- [Мої підтвердження](../data/participant-confirmations.json): Share Card Kolo, попередні виплати, доступність USDG, статуси й інші уточнення, які відділяю від незалежних доказів.
- [Trustee Points](../data/trustee-points-terms.json): наданий текст FAQ про внутрішні бонуси; поточна грошова конвертація не підтверджена.

Для Bybit загальна та AU-програми описують різні caps; активну програму мого акаунта ще уточнюю. Для COCA рекламне no lockup суперечить детальним умовам staking / cooldown; для APY є суперечність unlimited / невказаного tier cap. Для WhiteBIT використав ставки й категорії саме мого застосунку. USDG-кешбек недоступний у моєму OKX-акаунті; офіційна стаття окремо виключає Україну з USDG Rewards. Не переношу регіональні умови на всіх користувачів.

## Курси

Збережені відповіді [НБУ USD](../data/nbu-usd-2026-10-09.json) та [НБУ EUR](../data/nbu-eur-2026-10-09.json) за 09.10.2026 — лише орієнтир для порівняння. Вони не є курсом продажу USDT чи підтвердженим курсом карткової мережі.

[Курс Coinbase BTC/USD](../data/btc-usd-valuation-2026-10-09.json) — $82 976.035, відповідь 09.10.2026 о 14:56:42 UTC. Використовую його як спільну фіксовану оцінку показаного BTC-кешбеку, а не курс покупки чи майбутнього зарахування.

## Офіційні посилання

- [НБУ USD 09.10.2026](https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&date=20261009&json)
- [НБУ EUR 09.10.2026](https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=EUR&date=20261009&json)
- [Solid Rewards](https://support.solid.xyz/en/articles/15587319-how-does-solid-rewards-work)
- [COCA Cards](https://www.coca.xyz/cards)
- [WhiteBIT USD terms](https://help.whitebit.com/hc/en-gb/articles/38453058545949-N%C3%B3va-USD-Card-Issuer-and-Terms)
- [публічний запит](https://api.coinbase.com/v2/prices/BTC-USD/spot?date=2026-10-09)
- [Bybit загальна програма](https://www.bybit.com/en/pay-rewards/promo/rewards-details/)
- [AU-сторінка](https://www.bybitcard.com/aus)
- [VIP](https://www.bybit.com/en/VIPProgram/intro/)
- [COCA Tier T&C](https://help.coca.xyz/support/solutions/articles/205000042710-tier-system-terms-conditions)
- [маркетингового no lockup](https://www.coca.xyz/card-cashback)
- [OKX AU Cashback T&C](https://www.okx.com/help/okx-card-cashback-program-terms-and-conditions-au)
- [Kolo Cashback Program](https://help.kolo.xyz/en/articles/13623113-cashback-program)
- [Nóva USD Cashback](https://help.whitebit.com/hc/en-gb/articles/38461998477981-N%C3%B3va-USD-Card-Cashback-Categories-and-MCC-List)
- [Simple T&C](https://simple.app/terms-and-conditions/)
- [KeyOne Fees](https://www.keyone.help/fees)
- [Офіційна сторінка](https://trustee.io/ua/referral-program/?r=ojNqqBbp66b)
- [How to Claim APY](https://help.coca.xyz/support/solutions/articles/205000059634-how-to-claim-apy)
- [5% Balance APY](https://docs.coca.xyz/coca/membership-and-rewards/5-balance-apy)
- [OKX USDG Rewards](https://www.okx.com/ua/learn/usdg)

## Межі відтворення

Публічні PNG, SHA-256, транскрипції та розрахунки дозволяють перевірити показані суми. Прямі ончейн-посилання, адреси, хеші, персональні ID, сирі API / RPC і повні логи не публікую. Тому ончейн-зноски описують мою перевірку й не дозволяють незалежно повторити її лише з публічного набору.

Округлена USD-оцінка балансу не доводить утримання токенів. Показаний gas мережі не завжди сплачений мною; заявлені строки залежать від блоків і обробки сервісом. Успішне використання моєї картки не доводить доступність її випуску для всіх резидентів України. [Формули й припущення](methodology.md) · [Що ще не підтверджено](data-needed.md).
