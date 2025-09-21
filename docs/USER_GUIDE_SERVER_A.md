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
- **پاسخ موفق (202 Accepted):**
  ```json
  {
    "status": "accepted",
    "tracking_id": "abc123xyz"
  }
  ```
  در این پاسخ، مقدار `tracking_id` برای پیگیری وضعیت پیام در مراحل بعدی استفاده می‌شود.

- **پاسخ خطا (نمونه UNAUTHORIZED):**
  ```json
  {
    "detail": "کلید API نامعتبر است."
  }
  ```
  این پاسخ زمانی برگردانده می‌شود که کلید ارائه‌شده نادرست باشد یا در سیستم ثبت نشده باشد.
