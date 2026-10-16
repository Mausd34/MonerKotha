cd D:\MonerKotha# মনেরকথা — MonerKotha

বাংলা-প্রথম, মোবাইল-প্রথম, নামহীন অনুভূতি ও গল্প ভাগ করে নেওয়ার একটি মডারেশন-সহ Django প্ল্যাটফর্ম।

> **নাম নয়, অনুভূতিই আসল পরিচয়।**

## কী আছে

- Django 5.2, Python 3.12+, SQLite স্থানীয় উন্নয়নে; PostgreSQL ও Redis production-এ।
- গল্প জমা দিতে কোনো public name, account, email বা phone লাগে না। প্রতিটি নতুন story model-level-এ `pending`; অনুমোদিত না হওয়া পর্যন্ত public feed/detail/share-card-এ দেখানো হয় না।
- মডারেটর queue, story approve/reject/remove, moderation audit log, report/deletion-request queue এবং staff-only aggregate dashboard।
- Category, latest/popular feed, escaped text search, reaction, abuse reporting, author deletion request, daily prompt, Facebook link ও Pillow PNG share-card।
- CSRF, server-side form validation, contact-data rejection, honeypot, shared Redis rate limits, CSRF/session cookie security, strict `ALLOWED_HOSTS`, HTTPS/HSTS, secure headers, WhiteNoise static serving।
- বাংলা accessible form/error/empty/loading feedback, mobile bottom navigation, reduced-motion support, light theme default এবং optional dark theme।

এই সাইট **সম্পূর্ণ anonymity-এর নিশ্চয়তা দেয় না**। অ্যাপ কাঁচা IP database-এ রাখে না; rate-limit/একবারের reaction-এর জন্য secret-key-ভিত্তিক HMAC pseudonym cache/record-এ ব্যবহৃত হয়। Hosting/network provider ও server access logs-এর নিজস্ব metadata/retention থাকতে পারে। অনুগ্রহ করে গল্পে নিজের বা অন্যের পরিচয় প্রকাশ করবেন না।

## ফাইল বিন্যাস

```text
config/                 settings, URL config, WSGI/ASGI
stories/                models, forms, moderation services, views, admin
  migrations/           schema ও built-in category seed
  management/commands/  seed_demo, purge_retained_data
  tests/                model, form, view, moderation ও security tests
templates/              Bengali Django templates ও error states
static/css/             responsive design system
static/js/              small vanilla JS enhancements
static/images/          favicon
static/fonts/            licensed Noto Sans Bengali + OFL notice
manage.py
requirements.txt
render.yaml              example Render web/PostgreSQL/Redis Blueprint
Procfile
```

## স্থানীয় Windows সেটআপ

PowerShell:

```powershell
cd D:\MonerKotha
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`-এ development-এর জন্য `DEBUG=True`, একটি ব্যক্তিগত development-only `SECRET_KEY`, এবং `ALLOWED_HOSTS=localhost,127.0.0.1` রাখুন। `DATABASE_URL` ফাঁকা রাখলে SQLite `db.sqlite3` ব্যবহৃত হবে। `.env` Git-এ উপেক্ষিত।

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

এরপর `http://127.0.0.1:8000/` খুলুন। Demo command কেবল স্পষ্টভাবে কাল্পনিক Bengali sample story তৈরি করে, সবগুলো **pending** রাখে। এগুলো প্রকাশ করতে `/django-admin/`-এ staff দিয়ে সাইন ইন করে গল্পগুলো অনুমোদন করুন। প্রতিটি public গল্পের detail পাতায় report, delete-request, reaction ও share-card দেখা যায়।

### পরীক্ষা ও Django checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test stories.tests
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

## Environment configuration

Production-এ environment/secret manager-এ **অবশ্যই** আলাদা, random `SECRET_KEY`, `DEBUG=False`, নির্দিষ্ট `ALLOWED_HOSTS`, production `DATABASE_URL`, production `REDIS_URL`, `CSRF_TRUSTED_ORIGINS=https://your-domain.example`, `SECURE_SSL_REDIRECT=True` এবং প্রয়োজনে `SUPPORT_EMAIL` দিন। `ALLOWED_HOSTS=*` নিষিদ্ধ; production-এ Redis অনুপস্থিত হলে startup fail করে, কারণ একাধিক worker-এ rate-limit memory ভাগ হয় না। `DATABASE_URL` না দিলে SQLite fallback আছে—production-এ persistent PostgreSQL URL সেট করুন।

PNG-তে বাংলা আঁকার জন্য SIL Open Font License-এ প্রকাশিত Noto Sans Bengali-এর regular ও bold font `static/fonts/`-এ bundle করা আছে; Pillow এগুলো সরাসরি ব্যবহার করে। Custom font চাইলে `SHARE_CARD_FONT` path সেট করুন। License-টি `static/fonts/OFL.txt`-এ আছে।

ওয়েব পেজে Noto Sans Bengali local static asset হিসেবে serve হয়; font fetch-এর জন্য third-party request হয় না।

## Database, migrations, static assets

Schema বদলালে:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations stories
.\.venv\Scripts\python.exe manage.py migrate
```

Release/deploy-এ আগে migration চালান, এরপর:

```powershell
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Production static assets WhiteNoise-এর compressed manifest storage দিয়ে পরিবেশিত হয়। Upload/media file নেই; stories plain text।

## JSON API

Existing Django models and migrations use the same database as the website (SQLite locally, PostgreSQL when `DATABASE_URL` is set). Apply schema changes with `manage.py migrate`; no separate API database or extra framework dependency is needed.

Public JSON endpoints:

- `GET /api/categories/` — active categories.
- `GET /api/stories/?category=life&q=অনুভূতি&sort=latest&page=1` — approved stories, 12 per page. `sort` accepts `latest` or `popular`.
- `GET /api/stories/<public-uuid>/` — one approved story.
- `POST /api/stories/create/` — submit a story for moderation. JSON fields: `category` (category database ID), `content`, and `consent_given: true`.
- `POST /api/stories/<public-uuid>/reactions/` — JSON `{"kind":"heart"}`, where kind is `heart`, `hug`, or `light`.
- `POST /api/stories/<public-uuid>/reports/` — JSON `{"reason":"personal","details":"..."}`. Valid reasons: `personal`, `harassment`, `intimate`, `false`, `other`.
- `POST /api/stories/<public-uuid>/deletion-requests/` — JSON `{"reason":"..."}`.

Write endpoints require `Content-Type: application/json`, use the same form validation and rate limits as the website, and retain Django CSRF protection. They are intended for same-origin clients; cross-origin access is not enabled. Validation failures return HTTP 400 with an `error.fields` object; rate limits return HTTP 429. Only approved stories are exposed by read endpoints, and new submissions always enter the pending moderation queue.

## Moderation & abuse response

`/community/moderation/` এবং `/community/analytics/` staff-only. Admin UI `/django-admin/`-এও approval/rejection bulk actions moderation log লেখে। Public pages কেবল `approved` story নেয়। Policy-তে doxxing, threats, targeted harassment, non-consensual intimate content, এবং targeted unverified harmful allegations নিষিদ্ধ; রিপোর্টে moderator `গল্প সরান` বা review করেছেন চিহ্নিত করতে পারেন। Automated regex কেবল contact details (email, URL, Bangladesh mobile format)-এর একটি subset আটকায়; এটি human review-এর বিকল্প নয়।

Honeypot spam signal আছে; CAPTCHA provider integration is not wired and no third-party CAPTCHA data is sent.

## Retention policy ও প্রয়োগ

নীতির schedule: rejected story ৩০ দিন পর purge; removed story-র content অবিলম্বে মুছে ফেলা হয়; reactions ৯০ দিন পর; resolved report/deletion request resolution-এর ১৮০ দিন পর এবং moderation log তৈরির ১৮০ দিন পর purge। Approved story ৩৬৫ দিনে staff analytics dashboard-এ মানবিক review-এর জন্য দেখায়, **স্বয়ংক্রিয়ভাবে মুছে না**; review-তে সরালে content সঙ্গে সঙ্গে scrub হয়। Audit metadata story মুছে গেলেও তার random public UUID-সহ retention মেয়াদ পর্যন্ত থাকে। অপরিশোধিত pending story প্রতিদিন review করুন। Backups ৩০ দিনের মধ্যে expire করুন। Hosting access logs/provider log retention আলাদাভাবে যাচাই ও সীমিত করুন।

Destructive cleanup command প্রথমে `--execute` ছাড়া কাজ করবে না:

```powershell
.\.venv\Scripts\python.exe manage.py purge_retained_data
.\.venv\Scripts\python.exe manage.py purge_retained_data --execute
```

Production-এ প্রতি মাসে run করুন; rejected content-এর cleanup monthly হলে retention বাস্তবেও সর্বোচ্চ এক মাস অতিরিক্ত হতে পারে। Cleanup command পুরোনো published stories-এর review count দেখায়; বিস্তারিত staff analytics dashboard-এ পাওয়া যায় এবং moderator সিদ্ধান্ত ছাড়া কিছু delete হয় না।

## Backup ও restore

SQLite local backup-এর আগে app বন্ধ করে database ফাইল কপি করুন:

```powershell
Copy-Item .\db.sqlite3 .\db.sqlite3.backup
```

SQLite restore-এ server বন্ধ রেখে backup-টি `db.sqlite3` হিসেবে ফিরিয়ে দিন। PostgreSQL-এ:

```sh
pg_dump --format=custom "$DATABASE_URL" --file=monerkotha.dump
pg_restore --clean --if-exists --dbname="$DATABASE_URL" monerkotha.dump
```

Backup encrypted, access-controlled জায়গায় রাখুন; restore drill চালান এবং retention শেষে backup purge করুন। `dumpdata`/JSON backup production DB-র প্রথম পছন্দ নয়।

## Deployment (উদাহরণ)

Root-এর `render.yaml` Render-এর free web service, PostgreSQL এবং shared Key Value rate-limit cache deploy করার blueprint। Free web service ১৫ মিনিট নিষ্ক্রিয় থাকলে sleep করে; পরের request-এ জাগতে প্রায় এক মিনিট লাগতে পারে এবং local filesystem/database redeploy, restart বা sleep-এর সময় হারিয়ে যায়। Render-এর free PostgreSQL database তৈরির ৩০ দিন পর expire করে; চালু রাখতে upgrade দরকার, নইলে ডেটা অপ্রাপ্য হতে পারে। তাই এই free blueprint শুধু demo/hobby use-এর জন্য—বাস্তব user story-এর durable production storage হিসেবে ব্যবহার করবেন না। Deploy-এর আগে provider-এর বর্তমান free-tier limit ও pricing যাচাই করুন এবং dashboard-এ spending/payment setting পরীক্ষা করুন।

Deploy-এর আগে:

1. Repo deploy করুন এবং domain অনুযায়ী `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` ও `SUPPORT_EMAIL` বদলান।
2. Platform-এ generated secret রাখুন, `DEBUG=False`, HTTPS redirect ও secure cookies/HSTS নিশ্চিত করুন। `.env`, database dump, credentials commit করবেন না।
3. PostgreSQL/Redis URL একই app environment-এ দিন। Redis cache shared না হলে worker rate limits পরস্পর জানবে না।
4. `python manage.py migrate`, `python manage.py createsuperuser`, তারপর `python manage.py collectstatic --noinput` চালান। `Procfile` Gunicorn ব্যবহার করে; `render.yaml` web start-এর আগে migrations চালায়।
5. Admin account-এ MFA/strong password এবং সীমিত moderator access ব্যবহার করুন; moderation queue ও provider logs নিয়মিত পর্যালোচনা করুন।
6. Backup/restore ও retention job scheduler কনফিগার করুন। এই repository কোনো deployment চালায়নি; এখানে production deploy সফল হয়েছে—এমন দাবি করা হচ্ছে না।

## পরিচালনাগত সীমা ও উন্নতির জায়গা

- Contact inbox নিজে থেকে পাঠায় না; `SUPPORT_EMAIL` দিলে contact পাতা mailto দেখায়। Moderation email notification এখনো সংযুক্ত নয়।
- CAPTCHA provider integration, email confirmation/deletion-claim verification, Redis TLS/ACL, external object storage ও automated scheduled retention job deployer-কে পরিবেশ অনুযায়ী স্থাপন করতে হবে।
- Feed প্রতি পাতায় ১২টি গল্প paginate করে। Search হলো escaped plain `icontains`; খুব বড় feed-এ PostgreSQL full-text search যোগ করুন।
- Share images cacheable কিন্তু share-link request প্রতিবার Pillow image বানায়; traffic বাড়লে durable image cache/CDN যোগ করুন।
- Production-এ log access/minimization, Redis private network/password, database TLS, admin MFA এবং incident response review অপরিহার্য।
