# راهنمای کاربری API درگاه پیامک سرور A

## معرفی
این API برای ارسال پیامک‌های ساده طراحی شده است و به شما اجازه می‌دهد پیام‌های متنی را از طریق سرویس درگاه پیامک ارسال کنید. نشانی سرویس در محیط محلی به صورت `http://localhost:8001` در دسترس است.

## احراز هویت
تمام درخواست‌ها باید شامل کلید API باشند. این کلید باید در هدر درخواست با عنوان `API-Key` قرار بگیرد. مقدار `YOUR_API_KEY` را با کلید واقعی خود جایگزین کنید تا دسترسی شما پذیرفته شود.

## ارسال پیامک
- **آدرس فراخوانی (Endpoint):** `POST /api/v1/sms/send`
- **هدرهای لازم:**
  - `Content-Type: application/json`
  - `API-Key`
- **بدنه درخواست (JSON):**
  - `to`: شماره گیرنده در قالب بین‌المللی E.164 مانند `+98912...`
  - `text`: متن پیامکی که می‌خواهید ارسال کنید

## نمونه‌های کد
### نمونه cURL
```bash
curl -X POST http://localhost:8001/api/v1/sms/send \
  -H "Content-Type: application/json" \
  -H "API-Key: YOUR_API_KEY" \
  -d '{
    "to": "+989121234567",
    "text": "سلام! این یک پیام تستی است."
  }'
```

### نمونه Python با کتابخانه requests
```python
import requests

url = "http://localhost:8001/api/v1/sms/send"
headers = {
    "Content-Type": "application/json",
    "API-Key": "YOUR_API_KEY"
}
payload = {
    "to": "+989121234567",
    "text": "سلام! این یک پیام تستی است."
}

response = requests.post(url, json=payload, headers=headers)

print("وضعیت:", response.status_code)
print("پاسخ:", response.json())
```

## پاسخ‌ها
تمام پاسخ‌ها در قالب JSON بازگردانده می‌شوند. برای خطاها ساختار کلی شامل فیلدهای زیر است:

- `error_code`: کد خطا به صورت ثابت (مانند `UNAUTHORIZED` یا `INVALID_PAYLOAD`).
- `message`: توضیح خوانا برای کاربر.
- `details`: (اختیاری) اطلاعات تکمیلی مانند لیست خطاهای اعتبارسنجی.
- `tracking_id`: شناسه یکتا برای ردیابی درخواست (در خطاهایی که پس از اختصاص شناسه رخ می‌دهند).
- `timestamp`: زمان ایجاد پاسخ.

### پاسخ موفق (202 Accepted)
```json
{
  "success": true,
  "message": "Request accepted for processing.",
  "tracking_id": "d5f6a83a-1d25-4a83-8875-9472fbcb68c6"
}
```
در این حالت پیامک برای پردازش در صف قرار می‌گیرد. مقدار `tracking_id` را برای پیگیری وضعیت و لاگ‌ها ذخیره کنید.

### خطاهای متداول
- **401 UNAUTHORIZED** – زمانی که هدر `API-Key` وجود نداشته باشد یا مقدار آن معتبر نباشد:
  ```json
  {
    "error_code": "UNAUTHORIZED",
    "message": "Invalid API key",
    "timestamp": "2024-01-01T12:00:00.000000"
  }
  ```
  اگر هدر ارسال نشود پیام خطا `API-Key header missing` خواهد بود.

- **422 INVALID_PAYLOAD** – زمانی که بدنه درخواست ناقص باشد یا شماره مقصد معتبر نباشد:
  ```json
  {
    "error_code": "INVALID_PAYLOAD",
    "message": "Phone must be +989xxxxxxxxx, 09xxxxxxxxx, or 9xxxxxxxxx.",
    "tracking_id": "f1c8b84a-6f0a-4c2a-9d5d-6b679ddf3c1b",
    "timestamp": "2024-01-01T12:00:01.000000"
  }
  ```
  در صورت نبودن فیلدهای ضروری، پاسخ شامل فیلد `details.errors` با فهرست خطاهای اعتبارسنجی خواهد بود.

- **422 UNKNOWN_PROVIDER** – زمانی که نام ارائه‌دهنده ارسالی در پیکربندی موجود نباشد:
  ```json
  {
    "error_code": "UNKNOWN_PROVIDER",
    "message": "Unknown provider(s): foo. Allowed providers are: bar, baz.",
    "tracking_id": "4d0c9e60-2455-438e-85b2-36f5751f4d9a",
    "timestamp": "2024-01-01T12:00:02.000000"
  }
  ```

- **409 PROVIDER_DISABLED / ALL_PROVIDERS_DISABLED** – زمانی که تنها ارائه‌دهنده انتخاب‌شده غیر فعال باشد یا تمام گزینه‌های لیست شده قابل استفاده نباشند:
  ```json
  {
    "error_code": "PROVIDER_DISABLED",
    "message": "Provider 'bar' is currently disabled or not operational.",
    "tracking_id": "8d5b80c7-5a92-4cc7-9f07-9d8f52d0f2b1",
    "timestamp": "2024-01-01T12:00:03.000000"
  }
  ```

- **429 TOO_MANY_REQUESTS** – در صورت عبور از سقف سهمیه روزانه تعریف‌شده برای کلید API:
  ```json
  {
    "error_code": "TOO_MANY_REQUESTS",
    "message": "Daily SMS quota exceeded.",
    "tracking_id": "0cdb4c0b-9a63-4a53-bf1e-4e65305512bb",
    "timestamp": "2024-01-01T12:00:04.000000"
  }
  ```

- **503 NO_PROVIDER_AVAILABLE** – وقتی هیچ ارائه‌دهنده فعالی برای ارسال هوشمند وجود نداشته باشد:
  ```json
  {
    "error_code": "NO_PROVIDER_AVAILABLE",
    "message": "No SMS providers are currently available.",
    "tracking_id": "6f1abec8-81c8-46d6-9ab6-f0cbbcf87c34",
    "timestamp": "2024-01-01T12:00:05.000000"
  }
  ```

- **500 INTERNAL_ERROR** – در خطاهای غیرمنتظره سمت سرور:
  ```json
  {
    "error_code": "INTERNAL_ERROR",
    "message": "An internal server error occurred.",
    "tracking_id": "b9d513aa-3a2c-4b55-8ffd-4b1b1a6b4b03",
    "timestamp": "2024-01-01T12:00:06.000000"
  }
  ```
  در این حالت پیام در سیستم ثبت نمی‌شود و نیاز به بررسی لاگ‌های سرور خواهد بود.
