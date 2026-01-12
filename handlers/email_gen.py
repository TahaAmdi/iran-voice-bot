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

MAX_MAILTO_BODY_LEN = 1000  # حد امن

def shorten(text: str, n: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n] + "…"


# ---------------------------------------------------------
# مرحله ۱: انتخاب سازمان (نمایش لیست ایمیل‌ها با توضیحات فارسی)
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

    # ساخت دکمه برای هر ایمیل بر اساس توضیحات فارسی (Labels)
    keyboard = []
    for idx, email in enumerate(target_data["emails"]):
        # استفاده از لیبل فارسی تعریف شده در TARGETS
        label = target_data.get("email_labels", [])[idx] if "email_labels" in target_data else email
        keyboard.append([InlineKeyboardButton(f"👤 {label}", callback_data=f"SEL_MAIL_{idx}")])

    keyboard.append([InlineKeyboardButton("📢 ارسال به همه گزینه‌ها (All)", callback_data="SEL_MAIL_ALL")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="BACK_TO_MENU")])

    # نمایش نام فارسی و موضوع فارسی در متن پیام
    name_fa = target_data.get("name_fa", target_data["name"])
    topic_fa = target_data.get("topic_fa", "ارسال گزارش")

    text = (
        f"🎯 **هدف:** {name_fa}\n"
        f"📝 **موضوع:** {topic_fa}\n\n"
        "📬 لطفاً بخش مورد نظر برای ارسال ایمیل را انتخاب کنید:"
    )

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


# ---------------------------------------------------------
# مرحله ۲: تایید گیرنده و پرسش برای جزئیات
# ---------------------------------------------------------
async def email_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    target_data = context.user_data.get("selected_target")
    
    if not target_data:
        await start_handler(update, context)
        return

    selected_emails = []
    if data == "SEL_MAIL_ALL":
        selected_emails = target_data["emails"]
        selection_display = "همه گیرندگان لیست"
    else:
        try:
            idx = int(data.split("_")[-1])
            selected_emails = [target_data["emails"][idx]]
            # استفاده از لیبل فارسی برای نمایش در تاییدیه
            selection_display = target_data.get("email_labels", [])[idx] if "email_labels" in target_data else selected_emails[0]
        except:
            await start_handler(update, context)
            return

    context.user_data["recipient_list"] = selected_emails

    text = (
        f"✅ **گیرنده انتخاب شد:** `{selection_display}`\n\n"
        "📊 **آیا مایلید آمار یا جزئیات خاصی به متن ایمیل اضافه شود؟**"
    )

    keyboard = [
        [InlineKeyboardButton("✅ بله، می‌نویسم", callback_data="ADD_DATA_YES")],
        [InlineKeyboardButton("❌ خیر، متن استاندارد بساز", callback_data="ADD_DATA_NO")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]
    ]

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


# ---------------------------------------------------------
# مرحله ۳: پرسش برای دریافت متن اضافه
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
            text="✍️ **لطفاً جزئیات مورد نظر خود را بنویسید:**\n(مثلاً: نام زندانی، نام شهر، یا تاریخ واقعه)",
            reply_markup=ForceReply(input_field_placeholder="در اینجا بنویسید...")
        )


# ---------------------------------------------------------
# مرحله ۴: دریافت متن کاربر
# ---------------------------------------------------------
async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "WAITING_FOR_DETAILS":
        return

    context.user_data["custom_info"] = update.message.text
    context.user_data["state"] = None

    waiting = await update.message.reply_text("⏳ در حال آماده‌سازی ایمیل و ساخت لینک‌های ارسال…")
    await generate_final_email(update, context, message_object=waiting)


# ---------------------------------------------------------
# مرحله ۵: خروجی نهایی (فارسی‌سازی کامل راهنما و برچسب‌ها)
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get("selected_target")
    custom_info = context.user_data.get("custom_info")
    recipient_list = context.user_data.get("recipient_list")

    if not target_data or not recipient_list:
        await start_handler(update, context)
        return

    message = (message_object or (update.callback_query.message if update.callback_query else None))
    if not message: return

    try:
        # تولید متن ایمیل (موضوع اصلی برای ایمیل باید انگلیسی بماند)
        full_body = await ai_service.generate_email(target_data["topic"], custom_details=custom_info)
        if not full_body: raise Exception("AI returned empty response")

        full_subject = target_data["topic"]
        safe_full_subject = urllib.parse.quote(full_subject)
        safe_full_body = urllib.parse.quote(full_body)

        short_subject = shorten(full_subject, 80)
        short_body = full_body[:MAX_MAILTO_BODY_LEN]
        safe_short_subject = urllib.parse.quote(short_subject)
        safe_short_body = urllib.parse.quote(short_body)

        links_section = ""
        for email in recipient_list:
            # پیدا کردن لیبل فارسی گیرنده
            try:
                idx = target_data["emails"].index(email)
                label = target_data.get("email_labels", [])[idx]
            except:
                label = email

            # لینک‌های ارسال
            mailto_link = f"mailto:{email}?subject={safe_short_subject}&body={safe_short_body}"
            gmail_web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={safe_full_subject}&body={safe_full_body}"

            # --- بخش اصلاح شده ---
            links_section += (
                f"👤 <b>گیرنده:</b> {label}\n"
                f"└─ 📩 <a href='{mailto_link}'>{email}</a>\n\n"
                f"📱 <a href='{mailto_link}'>ارسال با اپلیکیشن موبایل (روی لینک ایمیل بالا ضربه بزنید)</a>\n"
                f"💻 <a href='{gmail_web_link}'>ارسال با نسخه وب Gmail</a>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )

        custom_info_display = ""
        if custom_info:
            custom_info_display = f"📌 **توضیحات شما:** {html.escape(shorten(custom_info))}\n"

        safe_subject_display = html.escape(full_subject)
        safe_body_display = html.escape(full_body)

        final_text = (
            "✅ **ایمیل شما آماده ارسال است**\n\n"
            "📱 **راهنمای موبایل:**\n"
            "روی لینک «ارسال با اپلیکیشن» بزنید. اگر عمل نکرد، متن پایین را کپی و دستی ارسال کنید.\n\n"
            f"📝 **موضوع (Subject):**\n`{safe_subject_display}`\n"
            f"{custom_info_display}\n"
            "👇 **لینک‌های ارسال مستقیم:**\n\n"
            f"{links_section}"
            "━━━━━━━━━━━━━━━━━━\n"
            "📌 * جهت کپی فقط یک ضربه بزنید(کلیک کنید) (Subject):**\n"
            f"<pre>{safe_subject_display}</pre>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✂️ **جهت کپی کامل متن فقط یک ضربه بزنید(کلیک کنید) (Body):**\n"
            f"<pre>{safe_body_display}</pre>"
        )

        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو اصلی", callback_data="BACK_TO_MENU")]]
        await message.edit_text(text=final_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    except Exception as e:
        print(f"EMAIL_GEN_ERROR: {e}")
        await message.edit_text(f"❌ متاسفانه خطایی در ساخت ایمیل رخ داد. لطفاً دوباره تلاش کنید.")