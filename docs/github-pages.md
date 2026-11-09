# Публікація дослідження на GitHub Pages

Сайт містить 22 статичні HTML-сторінки. Головна, рейтинг і дев’ять сторінок карток мають українську та англійську версії. Початковий порядок карток на головній визначає скоринг. JavaScript перемикає сортування й розгортає інтерактивні схеми. Картки розташовані у три колонки від 1080 px, у дві від 680 px та в одну на вужчих екранах. Докази відкриваються через браузерні popover-вікна з керуванням кнопкою, Escape та натисканням поза вікном. Відносні посилання підтримують GitHub Pages project path.

## Увімкнення

1. Створити публічний GitHub-репозиторій і завантажити публічні файли з гілки `main`. Оригінали скріншотів видалені; інші приватні матеріали зберігаю поза репозиторієм; `private/`, `cards_samples/` та `_site/` також виключені з Git.
2. У GitHub відкрити **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Запустити **Actions → Publish research to GitHub Pages → Run workflow**, або зробити наступний push у `main`.
4. URL опублікованої сторінки з’явиться у deployment `github-pages` та в Settings → Pages.

Workflow `.github/workflows/pages.yml` перебудовує HTML зі збережених публічних даних, перевіряє їх і формує `_site/` лише з `index.html`, `sitemap.xml`, `.nojekyll`, `LICENSE`, `data/`, `docs/`, `screenshots/`, `assets/` та `en/`. Шаблон і приватні файли не потрапляють до deployment artifact. Збірка на GitHub використовує стандартну бібліотеку Python й не потребує оригіналів. Node.js використовується лише для перевірки перемикача.

Push у `main` після увімкнення Pages автоматично оновлює публічну сторінку. Workflow також можна запускати вручну.

## Оновлення

Після зміни публічних даних або `scripts/report-template.html`:

```sh
python3 scripts/build.py
python3 scripts/check.py
node scripts/check-sort.cjs
node scripts/check-analytics.cjs
```

`build.py` створює українську `index.html` та англійську `en/index.html` зі спільних даних і шаблону. Окремої дубльованої копії звіту немає. Нові зображення додаю лише після очищення персональних даних, видалення метаданих і перевірки SHA-256.

Вигляд карток береться з очищених `assets/cards/*.png`; усі дев’ять мають розмір 960 × 600. Оригінали видалені; публічні зображення й перевірки залишаються в репозиторії.

Адреса дослідження: https://0k-lab.github.io/crypto-card-for-ukraine-research/.

## Прев’ю посилання

Кожна сторінка має локалізовані Open Graph і Twitter/X metadata. Головна та рейтинг використовують зображення дослідження 1200 × 630 з `assets/social/`. Сторінки карток використовують відповідні очищені зображення 960 × 600 з `assets/cards/`. Розміри та описи у metadata відповідають файлам. Редаговані SVG загального прев’ю зберігаються у `scripts/social-preview-uk.svg` та `scripts/social-preview-en.svg`.

Workflow отримує актуальну базову адресу з `configure-pages` перед збіркою. Вона використовується для абсолютних `og:image`, `twitter:image`, `og:url` і canonical, включно з project path або налаштованим власним доменом. Для локальної збірки з публічною адресою:

```sh
SITE_URL=https://0k-lab.github.io/crypto-card-for-ukraine-research python3 scripts/build.py
SITE_URL=https://0k-lab.github.io/crypto-card-for-ukraine-research python3 scripts/check.py
```

Без `SITE_URL` збірка використовує налаштовану адресу з `data/research.json`. Явний `SITE_URL=` залишає відносні посилання на прев’ю, вимикає canonical, структуровані дані й sitemap для локальної перевірки. Прев’ю перевіряю після публікації; месенджери можуть кешувати попередній вигляд.


## Пошук і AI-відповіді

`data/research.json` зберігає моє публічне ім’я, мій GitHub, адресу сайту й дату змістовного оновлення. При зміні результатів або тексту оновлюю `updated_on`; він використовується у видимій даті, `Article.dateModified` і `sitemap.xml`. Дата тесту береться з вимірювань. Дату публікації наперед не заявляю.

Усі 22 сторінки мають унікальні локалізовані title та description, canonical і взаємні `hreflang` для `uk`, `en` та `x-default`. Посилання між сторінками використовують адреси каталогів із завершальним слешем. Sitemap містить усі 22 адреси з датою оновлення та мовними альтернативами. Workflow враховує project path і власний домен.

JSON-LD пов’язує `WebSite`, `WebPage` або `CollectionPage` та авторський `Article`. Моє ім’я також є у футері з посиланням на GitHub. Картки й рейтинг мають `BreadcrumbList`. Головна та рейтинг містять `ItemList` у видимому порядку карток. Статті про картки посилаються на відповідні офіційні джерела.

`FAQPage` присутній на головній. Запитання та відповіді збігаються з видимим блоком «Короткі відповіді». Основний текст, методика та докази доступні у статичному HTML. PNG доказів завантажуються окремо через `loading="lazy"`.

`scripts/check.py` перевіряє унікальність і довжину metadata, зображення та їхні розміри, зв’язки JSON-LD, порядок карток, canonical, мовні альтернативи й sitemap для всіх сторінок. Перевірка також підтримує власну базову адресу та локальну збірку з `SITE_URL=`.

На сторінках немає `noindex`; для великих прев’ю задано `max-image-preview:large`. `robots.txt` для project Pages діє лише за адресою в корені домену, тому файл усередині цього репозиторію не додаю. `llms.txt` не є вимогою пошуку чи гарантією цитування; його також не додаю.

### Після публікації

1. Перевірити публічну доступність головної, рейтингу, сторінок карток обома мовами, sitemap та зображень прев’ю.
2. У [Google Search Console](https://search.google.com/search-console/) додати ресурс **URL prefix**: `https://0k-lab.github.io/crypto-card-for-ukraine-research/`. Для доменної перевірки `github.io` немає доступу до DNS.
3. Тег `google-site-verification` уже додано у спільний шаблон `scripts/page-template.html`. Для підтвердження ресурсу використати метод **HTML tag** у Search Console після розгортання сайту.
4. Подати `https://0k-lab.github.io/crypto-card-for-ukraine-research/sitemap.xml`, перевірити головну, рейтинг і потрібні сторінки карток через **URL Inspection** та запросити індексацію.
5. Перевірити JSON-LD у [Schema Markup Validator](https://validator.schema.org/) і підтримувані Google типи в [Rich Results Test](https://search.google.com/test/rich-results).

Технічна доступність не гарантує індексації, позицій або згадок в AI-відповідях. FAQ-розмітка описує ті самі відповіді, що видно на сторінці. Google [припинив показ FAQ rich results із 07.05.2026](https://developers.google.com/search/updates#may-2026); сама ця розмітка не дає спеціального розширеного результату чи гарантованих позицій. Безплатна статична публікація не потребує аналітичних трекерів або платних SEO-сервісів.

## Google Analytics

У спільному шаблоні підключено Google Analytics 4, потік `G-NWFJQ8WLJ7`, для обох мов. Стандартний Google tag реєструє перегляд сторінки; зовнішні переходи й прокручування залежать від увімкненого **Enhanced measurement** у налаштуваннях вебпотоку.

`assets/analytics.js` надсилає шість власних подій:

| Подія | Параметри крім спільного `page_language` |
|---|---|
| `sort_change` | `sort_mode`: gross / potential / actual |
| `detail_open` | `card_id`, `section`: purchase / cashback / earning / funding / losses |
| `evidence_open` | `card_id`, `evidence_type`: transactions / prime_terms; `evidence_view`: gallery / original |
| `card_open` | `card_id`, `is_referral` |
| `language_switch` | `target_language` |
| `repository_click` | `placement`: header / footer |

Скрипт не надсилає подій під час початкового налаштування сортування або закриття секцій. Повторне відкриття — нова дія. Рідні toggle-події охоплюють відкриття з клавіатури. Якщо Google tag недоступний, навігація й сортування продовжують працювати. Жодних додаткових мережевих бібліотек, user ID або запису сесій немає.

Для порівняння карток у звичайних звітах створити в GA4 **Admin → Custom definitions → Create custom dimension** визначення з областю **Event** для потрібних параметрів, наприклад `card_id`, `section`, `sort_mode`, `page_language`, `is_referral`. Визначення не відновлюють історичні дані, тож краще створити їх до аналізу. У Realtime можна перевірити назви подій без цього налаштування. Автоматична подія `click` з Enhanced measurement і власна `card_open` описують той самий перехід: їх не потрібно додавати як дві окремі конверсії.

Перевірка надходження відвідувань: Google Analytics → Reports → Realtime після відкриття сайту. Блокувальники аналітики можуть завадити збору. Measurement ID є публічним і не дає доступу до звітів.
