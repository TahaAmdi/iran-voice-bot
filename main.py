import logging
import os
import asyncio
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

# تنظیمات و فایل‌های خودت
from settings import settings
from config.targets import TARGETS
from handlers.menu import start_handler
from handlers.email_gen import (
    target_selection_handler, 
    ask_data_handler, 
    receive_custom_data_handler
)

# ----------------------------------------------------------------
# 1. تنظیمات وب‌سایت (Flask)
# ----------------------------------------------------------------
app = Flask(__name__)

# خواندن آدرس سایت از تنظیمات
BASE_URL = os.getenv("PUBLIC_URL", "http://127.0.0.1:5000")

@app.route('/')
def home():
    return "✅ Server is running! Bot is active."

@app.route('/email-redirect')
def email_redirect():
    to = request.args.get('to', '')
    subject = request.args.get('subject', '')
    body = request.args.get('body', '')

    safe_subject = urllib.parse.quote(subject)
    safe_body = urllib.parse.quote(body)
    mailto_link = f"mailto:{to}?subject={safe_subject}&body={safe_body}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting...</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #f0f2f5; }}
            .btn {{ display: inline-block; background-color: #0088cc; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h3>🚀 در حال باز کردن ایمیل...</h3>
        <p>اگر برنامه ایمیل باز نشد، دکمه زیر را بزنید:</p>
        <a class="btn" href="{mailto_link}">باز کردن ایمیل</a>
        <script>window.location.href = "{mailto_link}";</script>
    </body>
    </html>
    """
    return html_content

# ----------------------------------------------------------------
# 2. تنظیمات بات تلگرام (اجرا در پس‌زمینه)
# ----------------------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=settings.LOG_LEVEL
)

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await start_handler(update, context)

async def run_bot_async():
    if not settings.TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN missing")
        return

    print("🚀 Starting Telegram Bot in background...")
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()

    # اضافه کردن هندلرها
    application.add_handler(CommandHandler('start', start_handler))
    application.add_handler(CallbackQueryHandler(back_handler, pattern="^BACK_TO_MENU$"))
    application.add_handler(CallbackQueryHandler(ask_data_handler, pattern="^ADD_DATA_(YES|NO)$"))
    keys_pattern = "^(" + "|".join(TARGETS.keys()) + ")$"
    application.add_handler(CallbackQueryHandler(target_selection_handler, pattern=keys_pattern))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_data_handler))

    # --- بخش مهم و اصلاح شده ---
    # 1. اول باید initialize کنیم
    await application.initialize()
    
    # 2. بعد start کنیم
    await application.start()
    
    # 3. و در نهایت polling را شروع کنیم
    print("✅ Bot Initialized. Starting Polling...")
    await application.updater.start_polling(drop_pending_updates=True)
    
    # حلقه بی‌نهایت برای زنده نگه داشتن بات
    while True:
        await asyncio.sleep(3600)

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot_async())

# ----------------------------------------------------------------
# 3. بخش اصلی اجرا
# ----------------------------------------------------------------
if __name__ == '__main__':
    # اجرای بات در ترد جداگانه
    bot_thread = threading.Thread(target=start_bot_thread)
    bot_thread.daemon = True
    bot_thread.start()

    # اجرای Flask در ترد اصلی
    port = int(os.environ.get("PORT", 5000))
    print(f"🌍 Starting Web Server on port {port}...")
    app.run(host='0.0.0.0', port=port)