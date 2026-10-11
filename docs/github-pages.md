# Публікація дослідження на GitHub Pages

Головна сторінка — `index.html` у корені репозиторію. Це статична HTML-сторінка без framework, API keys або backend; невеликий локальний JavaScript перемикає порядок карток. Без JavaScript залишається початковий порядок за розрахунковою вартістю після врахованого кешбеку. Картки розташовані у 3 колонки від 1080 px, у 2 від 680 px, в одну на вужчих екранах. Докази відкриваються кнопкою через вбудовані браузерні popover-вікна; їх можна закрити кнопкою, Escape або натисканням поза вікном. Відносні посилання працюють під звичайним GitHub Pages project path.

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
```

`build.py` створює українську `index.html` та англійську `en/index.html` зі спільних даних і шаблону. Окремої дубльованої копії звіту немає. Нові зображення додаю лише після очищення персональних даних, видалення метаданих і перевірки SHA-256.

Вигляд карток береться з очищених `assets/cards/*.png`; усі дев’ять мають розмір 960 × 600. Оригінали видалені; публічні зображення й перевірки залишаються в репозиторії.

Адреса дослідження: https://0k-lab.github.io/crypto-card-for-ukraine-research/.

## Прев’ю посилання

У двох мовних версій є Open Graph і Twitter/X metadata, конкретний опис тесту та PNG 1200 × 630 з дев’ятьма картками. PNG — у `assets/social/`, редаговані SVG — у `scripts/social-preview-uk.svg` та `scripts/social-preview-en.svg`; використано лише вже очищені зображення карток. На ілюстрації показані списання до кешбеку, а не місячна модель.

Workflow отримує актуальну базову адресу з `configure-pages` перед збіркою. Вона використовується для абсолютних `og:image`, `twitter:image`, `og:url` і canonical, включно з project path або налаштованим власним доменом. Для локальної збірки з публічною адресою:

```sh
SITE_URL=https://0k-lab.github.io/crypto-card-for-ukraine-research python3 scripts/build.py
SITE_URL=https://0k-lab.github.io/crypto-card-for-ukraine-research python3 scripts/check.py
```

Без `SITE_URL` збірка використовує заплановану адресу з `data/research.json`. Явний `SITE_URL=` залишає відносні посилання на прев’ю, вимикає canonical, структуровані дані й sitemap для локальної перевірки. Прев’ю перевіряю після публікації; месенджери можуть кешувати попередній вигляд.


## Пошук і AI-відповіді

`data/research.json` зберігає публічне ім’я автора, його GitHub, адресу сайту й дату змістовного оновлення. При зміні результатів або тексту оновлюю `updated_on`; він використовується у видимій даті, `Article.dateModified` і `sitemap.xml`. Дата тесту береться з вимірювань. Дату публікації наперед не заявляю.

Обидві сторінки містять локалізовані title й description, canonical та взаємні `hreflang` (`uk`, `en`, `x-default`). Sitemap містить лише дві мовні сторінки з тими самими адресами й датою оновлення. Workflow враховує project path і власний домен.

JSON-LD описує `Article`, автора й `FAQPage`. Запитання та відповіді збігаються з видимим блоком «Короткі відповіді». Основний текст доступний без JavaScript. Доказові PNG завантажуються окремо, зі збереженням якості та `loading="lazy"`; вони не збільшують HTML на десятки мегабайт.

На сторінках немає `noindex`; для великих прев’ю задано `max-image-preview:large`. `robots.txt` для project Pages діє лише за адресою в корені домену, тому файл усередині цього репозиторію не додаю. `llms.txt` не є вимогою пошуку чи гарантією цитування; його також не додаю.

### Після публікації

1. Перевірити, що UA, EN, sitemap і зображення соціального прев’ю відкриваються публічно без авторизації.
2. У [Google Search Console](https://search.google.com/search-console/) додати ресурс **URL prefix**: `https://0k-lab.github.io/crypto-card-for-ukraine-research/`. Для доменної перевірки `github.io` немає доступу до DNS.
3. Обрати перевірку через **HTML tag**. Значення `google-site-verification` можна надати для додавання у спільний шаблон `scripts/report-template.html`; після збірки й розгортання натиснути Verify. Перевірочний тег залишаю після підтвердження власності.
4. Подати `https://0k-lab.github.io/crypto-card-for-ukraine-research/sitemap.xml`, перевірити обидві сторінки через **URL Inspection** і запросити індексацію.
5. Перевірити JSON-LD у [Schema Markup Validator](https://validator.schema.org/) і підтримувані Google типи в [Rich Results Test](https://search.google.com/test/rich-results).

Технічна доступність не гарантує індексації, позицій або згадок в AI-відповідях. FAQ-розмітка цього дослідження не означає право на Google FAQ rich results: вони обмежені відомими авторитетними урядовими й медичними сайтами. Безплатна статична публікація не потребує аналітичних трекерів або платних SEO-сервісів.

## Google Analytics

У спільному шаблоні підключено Google Analytics 4, потік `G-NWFJQ8WLJ7`, для обох мов. Стандартний Google tag реєструє перегляд сторінки; зовнішні переходи й прокручування залежать від увімкненого **Enhanced measurement** у налаштуваннях вебпотоку. Власних подій для кнопок і скріншотів немає.

Перевірка надходження відвідувань: Google Analytics → Reports → Realtime після відкриття сайту. Блокувальники аналітики можуть завадити збору. Measurement ID є публічним і не дає доступу до звітів.
