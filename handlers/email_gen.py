import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler

ai_service = AIService()

MAX_MAILTO_BODY_LEN = 1800  # حد امن برای mailto روی موبایل


def shorten(text: str, n: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n] + "…"


# ---------------------------------------------------------
# مرحله ۱: انتخاب سازمان
# ---------------------------------------------------------
async def target_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_key = query.data
    target_data = TARGETS.get(target_key)
    if not target_data:
        return

    context.user_data.clear()
    context.user_data["selected_target"] = target_data

    text = (
        f"🎯 شما «{target_data['name']}» را انتخاب کردید.\n\n"
        "📊 آیا می‌خواهید آمار یا جزئیات خاصی به متن اضافه کنید؟"
    )

    keyboard = [
        [InlineKeyboardButton("✅ بله، می‌نویسم", callback_data="ADD_DATA_YES")],
        [InlineKeyboardButton("❌ خیر، بساز", callback_data="ADD_DATA_NO")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]
    ]

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


# ---------------------------------------------------------
# مرحله ۲: انتخاب افزودن یا عدم افزودن متن
# ---------------------------------------------------------
async def ask_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ADD_DATA_NO":
        await generate_final_email(update, context)

    elif query.data == "ADD_DATA_YES":
        context.user_data["state"] = "WAITING_FOR_DETAILS"
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✍️ لطفاً متن یا جزئیات موردنظر خود را بنویسید:",
            reply_markup=ForceReply(input_field_placeholder="مثلاً: قطعی اینترنت در تهران...")
        )


# ---------------------------------------------------------
# مرحله ۳: دریافت متن کاربر
# ---------------------------------------------------------
async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "WAITING_FOR_DETAILS":
        try:
            await update.message.delete()
        except:
            pass
        await update.message.reply_text("⛔️ لطفاً فقط از دکمه‌های منو استفاده کنید.")
        return

    context.user_data["custom_info"] = update.message.text
    context.user_data["state"] = None

    waiting = await update.message.reply_text("⏳ دریافت شد. در حال آماده‌سازی ایمیل…")
    await generate_final_email(update, context, message_object=waiting)


# ---------------------------------------------------------
# مرحله ۴: ساخت لینک‌ها و خروجی نهایی
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get("selected_target")
    custom_info = context.user_data.get("custom_info")

    if not target_data:
        await start_handler(update, context)
        return

    message = (
        message_object
        or (update.callback_query.message if update.callback_query else None)
    )
    if not message:
        return

    try:
        # تولید متن ایمیل
        email_body = await ai_service.generate_email(
            target_data["topic"],
            custom_details=custom_info
        )
        email_subject = target_data["topic"]

        # نسخه کوتاه برای mailto
        mailto_body = email_body[:MAX_MAILTO_BODY_LEN]

        safe_subject = urllib.parse.quote(email_subject)
        safe_mailto_body = urllib.parse.quote(mailto_body)
        safe_full_body = urllib.parse.quote(email_body)

        links_section = ""
        for idx, email in enumerate(target_data["emails"], start=1):
            mailto_link = (
                f"mailto:{email}"
                f"?subject={safe_subject}&body={safe_mailto_body}"
            )

            gmail_web_link = (
                "https://mail.google.com/mail/"
                f"?view=cm&fs=1&to={email}"
                f"&su={safe_subject}&body={safe_full_body}"
            )

            links_section += (
                f"📨 <b>گیرنده {idx}:</b> {email}\n"
                f"📱 <a href='{mailto_link}'>باز کردن در اپ ایمیل (موبایل)</a>\n"
                f"💻 <a href='{gmail_web_link}'>باز کردن در Gmail Web (کامپیوتر)</a>\n\n"
            )

        safe_body_display = html.escape(email_body)
        safe_subject_display = html.escape(email_subject)

        final_text = (
            "✅ <b>ایمیل شما آماده است</b>\n\n"
            "📱 <b>راهنمای موبایل:</b>\n"
            "اگر با زدن لینک فقط Gmail باز شد، متن پایین را کپی کرده و دستی Paste کنید.\n\n"
            "💻 <b>راهنمای کامپیوتر:</b>\n"
            "لینک Gmail Web ایمیل را با متن آماده باز می‌کند.\n\n"
            f"📝 <b>موضوع:</b> {safe_subject_display}\n"
            f"{f'📌 <b>توضیحات شما:</b> {html.escape(shorten(custom_info))}\n' if custom_info else ''}\n"
            "👇 <b>لینک‌ها:</b>\n\n"
            f"{links_section}"
            "━━━━━━━━━━━━━━━━━━\n"
            "✂️ <b>متن کامل ایمیل (برای کپی):</b>\n"
            "روی متن بزنید و نگه دارید → Copy\n\n"
            f"<pre>{safe_body_display}</pre>"
        )

        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")]
        ]

        await message.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        print("EMAIL_GENERATION_ERROR:", e)
        await message.edit_text("❌ خطا در ساخت ایمیل. لطفاً دوباره تلاش کنید.")
