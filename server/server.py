from flask import Flask, request
import urllib.parse
import os

app = Flask(__name__)

@app.route('/email-redirect')
def email_redirect():
    # دریافت پارامترها از لینک
    to = request.args.get('to', '')
    subject = request.args.get('subject', '')
    body = request.args.get('body', '')

    # ساخت لینک Mailto استاندارد
    # از quote_plus استفاده می‌کنیم تا فاصله‌ها به + تبدیل شوند که امن‌تر است
    safe_subject = urllib.parse.quote(subject)
    safe_body = urllib.parse.quote(body)
    
    mailto_link = f"mailto:{to}?subject={safe_subject}&body={safe_body}"

    # یک صفحه HTML ساده که جاوااسکریپت آن، ایمیل را باز می‌کند
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>در حال انتقال...</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #f0f2f5; }}
            .btn {{ display: inline-block; background-color: #0088cc; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h3>🚀 در حال باز کردن اپلیکیشن ایمیل...</h3>
        <p>اگر تا چند لحظه دیگر اتفاقی نیفتاد، دکمه زیر را بزنید:</p>
        <a class="btn" href="{mailto_link}">باز کردن ایمیل</a>
        
        <script>
            // تلاش خودکار برای باز کردن ایمیل
            window.location.href = "{mailto_link}";
        </script>
    </body>
    </html>
    """
    return html_content

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' یعنی سرور از بیرون قابل دسترسی باشد
    app.run(host='0.0.0.0', port=port)