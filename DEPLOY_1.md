# نشر «تيّار» على GitHub ثم Railway

---

## ١. تجهيز المشروع محلياً (خطوة إلزامية)

ملفات الـ migrations **ليست** في المشروع، ولا بد أن تُنشأ عندك وتُرفع مع الكود،
وإلا فشل `migrate` على الخادم ولن تُنشأ أي جداول.

```bash
python -m venv .venv && source .venv/bin/activate    # ويندوز: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # فقط للتجربة المحلية

python manage.py makemigrations accounts catalog inventory purchasing orders
```

تأكد أن الملفات ظهرت داخل `apps/*/migrations/` قبل المتابعة.

---

## ٢. الرفع على GitHub

```bash
git init
git add .
git commit -m "متجر تيّار: نسخة أولى جاهزة للنشر"
git branch -M main
git remote add origin https://github.com/USERNAME/tayyar-store.git
git push -u origin main
```

> `.gitignore` يستثني `.env` و`media/` و`staticfiles/` — تأكد ألّا يُرفع ملف `.env` أبداً.
> لو ظهرت رسالة `authentication failed`، أنشئ **Personal Access Token** من
> GitHub → Settings → Developer settings → Tokens، واستخدمه بدل كلمة المرور.

---

## ٣. النشر على Railway

### أ) أنشئ المشروع
1. ادخل [railway.app](https://railway.app) وسجّل بحساب GitHub.
2. **New Project → Deploy from GitHub repo** واختر المستودع.
3. سيبدأ Railway البناء تلقائياً (سيفشل الآن — طبيعي، لا توجد قاعدة بيانات بعد).

### ب) أضف قاعدة البيانات
داخل نفس المشروع: **+ New → Database → Add PostgreSQL**.

### ج) اربط القاعدة بالتطبيق
افتح خدمة التطبيق ← **Variables** ← أضف:

| المتغير | القيمة |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `SECRET_KEY` | مفتاح عشوائي طويل (انظر أدناه) |
| `DEBUG` | `False` |
| `TIME_ZONE` | `Asia/Riyadh` |

لتوليد مفتاح آمن:
```bash
python -c "import secrets; print(secrets.token_urlsafe(60))"
```

بقية المتغيرات الاختيارية (Stripe، البريد، الضريبة…) في ملف `.env.railway.example`.

> الدومين ونطاق CSRF يُلتقطان تلقائياً من `RAILWAY_PUBLIC_DOMAIN`، فلا حاجة لكتابتهما.

### د) فعّل الدومين
**Settings → Networking → Generate Domain**، وستحصل على رابط مثل
`https://tayyar-store-production.up.railway.app`.

### هـ) أعد النشر
**Deployments → Redeploy**. الأمر `migrate` يعمل تلقائياً قبل تشغيل الخادم.

---

## ٤. إنشاء حساب المشرف

ثبّت الـ CLI ثم:

```bash
npm i -g @railway/cli
railway login
railway link                       # اختر المشروع
railway run python manage.py createsuperuser
```

أو لتعبئة بيانات تجريبية:
```bash
railway run python manage.py seed_demo
```

---

## ٥. صور المنتجات (مهم جداً)

قرص Railway **مؤقت**: كل نشر جديد يمسح مجلد `media/` وتضيع صور المنتجات.
اختر أحد الحلين:

**الأسهل — Volume:**
خدمة التطبيق ← **Settings → Volumes → Add Volume** ← Mount path: `/app/media`.
الإعدادات تلتقط المسار تلقائياً من `RAILWAY_VOLUME_MOUNT_PATH`.

**الأفضل للإنتاج — تخزين سحابي:**
```bash
pip install django-storages boto3
```
ثم في `settings.py` وجّه `STORAGES["default"]` إلى S3 أو Cloudflare R2.

---

## ٦. بعد النشر

- **Stripe Webhook**: أضف في لوحة Stripe رابط
  `https://your-domain.up.railway.app/cart/payment/webhook/`
  لحدث `checkout.session.completed`، وضع سرّه في `STRIPE_WEBHOOK_SECRET`.
- **الترقية**: أي `git push` إلى `main` ينشر تلقائياً.
- **السجلّات**: تبويب **Deployments → View Logs** لتتبّع الأخطاء.

---

## ٧. حلّ المشاكل الشائعة

| الخطأ | السبب والحل |
|---|---|
| `no such table` أو `relation does not exist` | لم ترفع ملفات migrations. نفّذ `makemigrations` محلياً واعمل commit وpush. |
| `DisallowedHost` | أضف الدومين في متغير `ALLOWED_HOSTS`. |
| `CSRF verification failed` | أضف `CSRF_TRUSTED_ORIGINS=https://your-domain` بالبروتوكول. |
| صفحة بلا تنسيق (CSS مفقود) | فشل `collectstatic`. راجع سجلّ البناء، وتأكد من وجود مجلد `static/`. |
| `Missing staticfiles manifest entry` | نفّذ `collectstatic` — موجود أصلاً في `buildCommand`. |
| توقف الخادم فوراً | تأكد أن أمر التشغيل يستخدم `$PORT` وليس منفذاً ثابتاً. |
| الصور تختفي بعد كل نشر | اربط Volume أو تخزيناً سحابياً (القسم ٥). |
