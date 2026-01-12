import logging
import os
import threading
import urllib.parse
from flask import Flask, request

# کتابخانه‌های تلگرام
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)

# ایمپورت‌های پروژه خودت
from settings import settings
from config.targets import TARGETS
from handlers.menu import start_handler
from handlers.email_gen import (
    target_selection_handler, 
    ask_data_handler, 
    receive_custom_data_handler
)

# ----------------------------------------------------------------
# بخش 1: تنظیمات وب‌سرور (Flask) برای باز کردن ایمیل
# ----------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/email-redirect')
def email_redirect():
    # دریافت پارامترها
    to = request.args.get('to', '')
    subject = request.args.get('subject', '')
    body = request.args.get('body', '')

    # ساخت لینک ایمیل امن
    safe_subject = urllib.parse.quote(subject)
    safe_body = urllib.parse.quote(body)
    mailto_link = f"mailto:{to}?subject={safe_subject}&body={safe_body}"

    # صفحه HTML واسط برای باز کردن ایمیل
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
            window.location.href = "{mailto_link}";
        </script>
    </body>
    </html>
    """
    return html_content

# تابعی برای اجرای Flask در یک رشته (Thread) جداگانه
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    # use_reloader=False مهم است تا در Thread تداخل ایجاد نکند
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# ----------------------------------------------------------------
# بخش 2: تنظیمات بات تلگرام (کد اصلی خودت)
# ----------------------------------------------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=settings.LOG_LEVEL
)

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start_handler(update, context)

if __name__ == '__main__':
    # بررسی توکن
    if not settings.TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN is missing.")
        exit(1)

    print("🚀 Starting Flask Server in background...")
    # اجرای وب‌سرور در پس‌زمینه (بدون اینکه جلوی بات را بگیرد)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("🚀 Starting Telegram Bot...")
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()

    # هندلرها
    application.add_handler(CommandHandler('start', start_handler))
    application.add_handler(CallbackQueryHandler(back_handler, pattern="^BACK_TO_MENU$"))
    application.add_handler(CallbackQueryHandler(ask_data_handler, pattern="^ADD_DATA_(YES|NO)$"))
    
    keys_pattern = "^(" + "|".join(TARGETS.keys()) + ")$"
    application.add_handler(CallbackQueryHandler(target_selection_handler, pattern=keys_pattern))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_data_handler))

    print("✅ Bot and Server are running.")
    application.run_polling()