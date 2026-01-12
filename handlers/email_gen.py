import urllib.parse
import html
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler


ai_service = AIService()

# --------------------------------------------------------
# ⚙️ تنظیمات سرور Flask
# اگر روی سیستم خودتان تست می‌کنید: http://127.0.0.1:5000
# اگر روی سرور واقعی هستید، آدرس دامنه یا IP سرور را بنویسید (ترجیحاً https)
# --------------------------------------------------------
FLASK_SERVER_URL = os.getenv("PUBLIC_URL", "http://127.0.0.1:5000")


def shorten(text: str, n: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n] + "…"

def clean_for_subject(text: str) -> str:
    """حذف اینتر و فاصله‌های اضافه برای تمیزی موضوع"""
    if not text:
        return ""
    return " ".join(text.split())

# ---------------------------------------------------------
# هندلرهای ورودی (بدون تغییر)
# ---------------------------------------------------------
async def target_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_key = query.data
    target_data = TARGETS.get(target_key)
    if not target_data: return
    context.user_data.clear()
    context.user_data["selected_target"] = target_data
    text = (f"🎯 شما «{target_data['name']}» را انتخاب کردید.\n\n" "📊 آیا می‌خواهید آمار یا جزئیات خاصی به متن اضافه کنید؟")
    keyboard = [[InlineKeyboardButton("✅ بله، می‌نویسم", callback_data="ADD_DATA_YES")], [InlineKeyboardButton("❌ خیر، بساز", callback_data="ADD_DATA_NO")], [InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def ask_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "ADD_DATA_NO": await generate_final_email(update, context)
    elif query.data == "ADD_DATA_YES":
        context.user_data["state"] = "WAITING_FOR_DETAILS"
        await query.message.delete()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✍️ لطفاً متن یا جزئیات موردنظر خود را بنویسید:", reply_markup=ForceReply(input_field_placeholder="مثلاً: قطعی اینترنت..."))

async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "WAITING_FOR_DETAILS": return
    context.user_data["custom_info"] = update.message.text
    context.user_data["state"] = None
    waiting = await update.message.reply_text("⏳ دریافت شد. در حال آماده‌سازی ایمیل…")
    await generate_final_email(update, context, message_object=waiting)

# ---------------------------------------------------------
# تابع اصلی (متصل به سرور Flask)
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get("selected_target")
    custom_info = context.user_data.get("custom_info")

    if not target_data:
        await start_handler(update, context)
        return

    message = (message_object or (update.callback_query.message if update.callback_query else None))
    if not message: return

    try:
        # 1. تولید متن و پاکسازی موضوع
        email_body = await ai_service.generate_email(target_data["topic"], custom_details=custom_info)
        clean_subject = clean_for_subject(target_data["topic"])
        
        # 2. انکود کردن پارامترها برای ارسال به Flask
        # ما متن را تبدیل به فرمت URL می‌کنیم تا به عنوان Query Parameter ارسال شود
        params_subject = urllib.parse.quote(clean_subject)
        params_body = urllib.parse.quote(email_body)

        # 3. ساخت دکمه‌ها
        keyboard = []

        for idx, email in enumerate(target_data["emails"], start=1):
            
            # ساخت لینک واسط به سرور Flask
            # فرمت: http://SERVER/email-redirect?to=EMAIL&subject=SUB&body=TEXT
            redirect_url = (
                f"{FLASK_SERVER_URL}/email-redirect"
                f"?to={email}"
                f"&subject={params_subject}"
                f"&body={params_body}"
            )
            
            # دکمه شیشه‌ای (چون لینک http است، تلگرام ارور نمی‌دهد)
            keyboard.append([
                InlineKeyboardButton(f"🚀 ارسال به گیرنده {idx} (کلیک کنید)", url=redirect_url)
            ])

        # دکمه بازگشت
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")])

        # 4. آماده‌سازی متن‌های نمایشی
        safe_subject_display = html.escape(clean_subject)
        safe_body_display = html.escape(email_body)

        custom_info_line = ""
        if custom_info:
            safe_custom_info = html.escape(shorten(custom_info))
            custom_info_line = f"📌 <b>توضیحات شما:</b> {safe_custom_info}\n"

        final_text = (
            "✅ <b>ایمیل شما آماده است</b>\n\n"
            "روی دکمه‌های زیر بزنید. به صورت خودکار اپلیکیشن ایمیل شما باز می‌شود.\n"
            "(این روش هم روی موبایل و هم کامپیوتر کار می‌کند)\n\n"
            f"{custom_info_line}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

        # ارسال پیام اصلی با دکمه‌ها
        await message.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        # محض احتیاط: ارسال متن‌ها برای کپی (اگر سرور در دسترس نبود یا کاربر خواست دستی بفرستد)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📝 <b>موضوع (نسخه متنی):</b>\n<pre>{safe_subject_display}</pre>",
            parse_mode=ParseMode.HTML
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📄 <b>متن کامل (نسخه متنی):</b>\n<pre>{safe_body_display}</pre>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        print("EMAIL_GENERATION_ERROR:", e)
        try: await message.edit_text(f"❌ خطا: {str(e)}")
        except: pass