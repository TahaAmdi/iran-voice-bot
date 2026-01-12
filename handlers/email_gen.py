import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler

ai_service = AIService()

# محدودیت سخت‌گیرانه برای لینک موبایل (بیشتر از این معمولاً نادیده گرفته می‌شود)
MAX_MAILTO_BODY_LEN = 200


def shorten(text: str, n: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n] + "…"


# ---------------------------------------------------------
# هندلرهای انتخاب و دریافت ورودی (بدون تغییر منطقی)
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
# تابع اصلی ساخت ایمیل (بازنویسی شده برای رفع باگ لینک)
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
        # 1. تولید متن توسط هوش مصنوعی
        email_body = await ai_service.generate_email(
            target_data["topic"],
            custom_details=custom_info
        )
        email_subject = target_data["topic"]

        # 2. آماده‌سازی متن برای لینک mailto (نسخه کوتاه)
        # اگر متن خیلی طولانی باشد، اپ‌های موبایل کلاً Subject و Body را نادیده می‌گیرند.
        if len(email_body) > MAX_MAILTO_BODY_LEN:
            mailto_body_text = email_body[:MAX_MAILTO_BODY_LEN] + "...\n\n(متن کامل را از ربات کپی کنید)"
        else:
            mailto_body_text = email_body

        # 3. انکودینگ (Encoding) تهاجمی برای رفع مشکل Subject
        # پارامتر safe='' باعث می‌شود حتی کاراکترهای / : = هم انکود شوند.
        # این حیاتی است تا لینک شکسته نشود.
        safe_subject = urllib.parse.quote(email_subject, safe='')
        safe_mailto_body = urllib.parse.quote(mailto_body_text, safe='')
        safe_full_body = urllib.parse.quote(email_body, safe='') # برای وب

        links_section = ""
        for idx, email in enumerate(target_data["emails"], start=1):
            # ساخت لینک Mailto
            mailto_link = f"mailto:{email}?subject={safe_subject}&body={safe_mailto_body}"

            # ساخت لینک Gmail Web
            gmail_web_link = (
                "https://mail.google.com/mail/"
                f"?view=cm&fs=1&to={email}"
                f"&su={safe_subject}&body={safe_full_body}"
            )

            # استفاده از دابل کوتیشن " برای href تا با کوتیشن‌های احتمالی در URL تداخل نکند
            links_section += (
                f"📨 <b>گیرنده {idx}:</b> {email}\n"
                f'📱 <a href="{mailto_link}">ارسال با اپلیکیشن (کلیک کنید)</a>\n'
                f'💻 <a href="{gmail_web_link}">نسخه وب (مخصوص کامپیوتر)</a>\n\n'
            )

        # 4. آماده‌سازی نمایش HTML
        safe_body_display = html.escape(email_body)
        safe_subject_display = html.escape(email_subject)

        # جلوگیری از خطای f-string (منطق در بیرون)
        custom_info_line = ""
        if custom_info:
            safe_custom_info = html.escape(shorten(custom_info))
            custom_info_line = f"📌 <b>توضیحات شما:</b> {safe_custom_info}\n"

        # 5. چیدمان پیام نهایی
        final_text = (
            "✅ <b>ایمیل شما آماده است</b>\n\n"
            "⚠️ <b>نکته مهم:</b> اگر با زدن دکمهٔ «ارسال با اپلیکیشن»، موضوع یا متن وارد نشد، "
            "به دلیل محدودیت‌های سیستم‌عامل گوشی است. در این صورت متن زیر را کپی کنید.\n\n"
            f"📝 <b>موضوع:</b> {safe_subject_display}\n"
            f"{custom_info_line}\n"
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