import urllib.parse
import html
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler

ai_service = AIService()

MAX_MAILTO_BODY_LEN = 350  # حد امن برای جلوگیری از کرش در موبایل


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
        # -------- تولید متن ایمیل (AI) --------
        # تلاش برای تولید متن
        full_body = await ai_service.generate_email(
            target_data["topic"],
            custom_details=custom_info
        )
        
        # اگر AI خروجی نداد یا خالی بود
        if not full_body:
            raise Exception("AI returned empty response")

        full_subject = target_data["topic"]

        # -------- آماده‌سازی ایمیل --------
        short_subject = shorten(full_subject, 80)
        short_body = full_body[:MAX_MAILTO_BODY_LEN]

        # انکودینگ
        safe_short_subject = urllib.parse.quote(short_subject)
        safe_short_body = urllib.parse.quote(short_body)
        safe_full_subject = urllib.parse.quote(full_subject)
        safe_full_body = urllib.parse.quote(full_body)

        # ساخت لینک‌های ایمیل
        links_section = ""
        for idx, email in enumerate(target_data["emails"], start=1):
            
            # لینک موبایل (Mailto)
            mailto_link = (
                f"mailto:{email}"
                f"?subject={safe_short_subject}&body={safe_short_body}"
            )
            
            # لینک وب (Gmail)
            gmail_web_link = (
                "https://mail.google.com/mail/"
                f"?view=cm&fs=1&to={email}"
                f"&su={safe_full_subject}&body={safe_full_body}"
            )

            links_section += (
                f"📨 <b>گیرنده {idx}:</b> {email}\n"
                f"📱 <a href='{mailto_link}'>ارسال با اپلیکیشن موبایل</a>\n"
                f"💻 <a href='{gmail_web_link}'>ارسال با Gmail Web</a>\n\n"
            )

        # -------- رفع باگ SyntaxError --------
        # شرط را اینجا محاسبه می‌کنیم
        custom_info_display = ""
        if custom_info:
            custom_info_display = f"📌 <b>توضیحات شما:</b> {html.escape(shorten(custom_info))}\n"

        safe_subject_display = html.escape(full_subject)
        safe_body_display = html.escape(full_body)

        # -------- متن نهایی --------
        final_text = (
            "✅ <b>ایمیل شما آماده است</b>\n\n"
            "📱 <b>راهنمای موبایل (ایمیل):</b>\n"
            "روی لینک «ارسال با اپلیکیشن» بزنید. اگر کار نکرد، متن پایین را کپی کنید.\n\n"
            "💻 <b>راهنمای کامپیوتر:</b>\n"
            "لینک Gmail Web را بزنید.\n\n"
            f"📝 <b>موضوع:</b> {safe_subject_display}\n"
            f"{custom_info_display}\n"
            "👇 <b>لینک‌های ارسال:</b>\n\n"
            f"{links_section}"
            "━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Subject کامل (برای کپی):</b>\n"
            "روی متن بزنید و نگه دارید → Copy\n\n"
            f"<pre>{safe_subject_display}</pre>\n"
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
        print(f"EMAIL_GENERATION_ERROR: {e}")
        error_msg = str(e)
        
        # اگر خطا مربوط به Rate Limit باشد
        if "429" in error_msg or "Rate limit" in error_msg:
             await message.edit_text("⏳ لطفاً چند ثانیه صبر کنید و دوباره امتحان کنید (محدودیت هوش مصنوعی).")
        else:
             await message.edit_text(f"❌ خطا در ساخت ایمیل: {error_msg[:100]}...")