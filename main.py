import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from settings import settings
from config.targets import TARGETS
from handlers.menu import start_handler

# ایمپورت توابع منطقی از فایل email_gen
from handlers.email_gen import (
    target_selection_handler, 
    ask_data_handler, 
    receive_custom_data_handler
)

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=settings.LOG_LEVEL
)

# هندلر دکمه بازگشت (پاکسازی وضعیت کاربر)
async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # پاک کردن حافظه موقت کاربر (State)
    context.user_data.clear()
    await start_handler(update, context)

if __name__ == '__main__':
    # بررسی وجود توکن
    if not settings.TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN is missing in .env file.")
        exit(1)

    print("🚀 Bot is starting...")
    
    # ساخت اپلیکیشن
    application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()

    # 1. هندلر دستور استارت (/start)
    application.add_handler(CommandHandler('start', start_handler))
    
    # 2. هندلر دکمه بازگشت (اولویت بالا)
    application.add_handler(CallbackQueryHandler(back_handler, pattern="^BACK_TO_MENU$"))

    # 3. هندلر انتخاب Yes/No (برای افزودن جزئیات)
    application.add_handler(CallbackQueryHandler(ask_data_handler, pattern="^ADD_DATA_(YES|NO)$"))

    # 4. هندلر انتخاب هدف (سازمان‌ها)
    # پترنی می‌سازیم که فقط کلیدهای موجود در TARGETS را قبول کند
    keys_pattern = "^(" + "|".join(TARGETS.keys()) + ")$"
    application.add_handler(CallbackQueryHandler(target_selection_handler, pattern=keys_pattern))

    # 5. هندلر دریافت متن (وقتی کاربر Yes زده و تایپ می‌کند)
    # این هندلر فقط متن‌ها را می‌گیرد (نه دستورات) و به تابع receive_custom_data_handler می‌دهد
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_data_handler))

    print("✅ Bot is running. Press Ctrl+C to stop.")
    application.run_polling()


    #poetry run python main.py
    """git add .
git commit -m "Prepare for Railway deployment"
git push"""