import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler

ai_service = AIService()

MAX_MAILTO_BODY_LEN = 1000  # حد امن برای جلوگیری از کرش در موبایل


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

    waiting = await update.message.reply_text("⏳ دریافت شد. در حال آماده‌سازی ایمیل و توییت…")
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
        # -------- 1. تولید متن ایمیل (AI) --------
        full_body = await ai_service.generate_email(
            target_data["topic"],
            custom_details=custom_info
        )
        full_subject = target_data["topic"]

        # -------- 2. تولید متن توییت (AI) --------
        # چک می‌کنیم آیا این تارگت توییتر دارد؟
        twitter_handle = target_data.get("twitter")
        tweet_text = ""
        tweet_section_html = ""

        if twitter_handle:
            # اگر در سرویس AI تابع generate_tweet را اضافه کرده باشید:
            tweet_text = await ai_service.generate_tweet(
                topic=target_data["topic"],
                target_handle=twitter_handle,
                custom_details=custom_info
            )
            
            # ساخت لینک توییتر
            safe_tweet = urllib.parse.quote(tweet_text)
            tweet_link = f"https://twitter.com/intent/tweet?text={safe_tweet}"
            
            tweet_section_html = (
                "🐦 <b>توییتر (X):</b>\n"
                f"🚀 <a href='{tweet_link}'>برای ارسال توییت اینجا کلیک کنید</a>\n"
                f"<code>{html.escape(tweet_text)}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
            )

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
        # ⚠️ نکته مهم: شرط را اینجا محاسبه می‌کنیم، نه داخل f-string
        custom_info_display = ""
        if custom_info:
            custom_info_display = f"📌 <b>توضیحات شما:</b> {html.escape(shorten(custom_info))}\n"

        safe_subject_display = html.escape(full_subject)
        safe_body_display = html.escape(full_body)

        # -------- متن نهایی --------
        final_text = (
            "✅ <b>محتوا آماده شد</b>\n\n"
            f"{tweet_section_html}"
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
        print("EMAIL_GENERATION_ERROR:", e)
        # در صورت خطا، متن ساده‌تری می‌فرستیم تا کاربر متوجه شود
        await message.edit_text("❌ خطا در ساخت محتوا. لطفاً دوباره تلاش کنید.")