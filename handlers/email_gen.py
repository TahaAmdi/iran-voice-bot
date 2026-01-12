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
# مرحله ۱: انتخاب سازمان (نمایش لیست ایمیل‌ها)
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

    # ساخت دکمه برای هر ایمیل موجود در تارگت
    keyboard = []
    for idx, email in enumerate(target_data["emails"]):
        # کال‌بک به صورت SEL_MAIL_0, SEL_MAIL_1 و ...
        keyboard.append([InlineKeyboardButton(f"👤 {email}", callback_data=f"SEL_MAIL_{idx}")])

    # دکمه ارسال به همه
    keyboard.append([InlineKeyboardButton("📢 ارسال به همه (All)", callback_data="SEL_MAIL_ALL")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")])

    text = (
        f"🎯 هدف: **{target_data['name']}**\n\n"
        "📬 لطفاً انتخاب کنید به کدام ایمیل ارسال شود:"
    )

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


# ---------------------------------------------------------
# مرحله ۲ (جدید): ذخیره ایمیل انتخاب شده و پرسش برای متن
# ---------------------------------------------------------
async def email_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    target_data = context.user_data.get("selected_target")
    
    if not target_data:
        await start_handler(update, context)
        return

    # تشخیص انتخاب کاربر
    selected_emails = []
    
    if data == "SEL_MAIL_ALL":
        selected_emails = target_data["emails"]
        selection_name = "همه ایمیل‌ها"
    else:
        # فرمت SEL_MAIL_0 است
        try:
            idx = int(data.split("_")[-1])
            selected_emails = [target_data["emails"][idx]]
            selection_name = selected_emails[0]
        except:
            await start_handler(update, context)
            return

    # ذخیره در user_data برای مرحله بعد
    context.user_data["recipient_list"] = selected_emails

    # حالا می‌رویم سراغ سوال همیشگی (افزودن جزئیات)
    text = (
        f"✅ گیرنده انتخاب شد: `{selection_name}`\n\n"
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
# مرحله ۳: انتخاب افزودن یا عدم افزودن متن (بدون تغییر)
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
# مرحله ۴: دریافت متن کاربر (بدون تغییر)
# ---------------------------------------------------------
async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "WAITING_FOR_DETAILS":
        try: await update.message.delete()
        except: pass
        await update.message.reply_text("⛔️ لطفاً فقط از دکمه‌های منو استفاده کنید.")
        return

    context.user_data["custom_info"] = update.message.text
    context.user_data["state"] = None

    waiting = await update.message.reply_text("⏳ دریافت شد. در حال آماده‌سازی ایمیل…")
    await generate_final_email(update, context, message_object=waiting)


# ---------------------------------------------------------
# مرحله ۵: ساخت خروجی نهایی (فقط برای ایمیل‌های انتخاب شده)
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get("selected_target")
    custom_info = context.user_data.get("custom_info")
    recipient_list = context.user_data.get("recipient_list") # دریافت لیست انتخاب شده

    if not target_data or not recipient_list:
        await start_handler(update, context)
        return

    message = (message_object or (update.callback_query.message if update.callback_query else None))
    if not message: return

    try:
        # -------- تولید متن ایمیل (AI) --------
        full_body = await ai_service.generate_email(target_data["topic"], custom_details=custom_info)
        
        if not full_body: raise Exception("AI returned empty response")

        full_subject = target_data["topic"]

        # -------- آماده‌سازی لینک‌ها --------
        short_subject = shorten(full_subject, 80)
        short_body = full_body[:MAX_MAILTO_BODY_LEN]

        safe_short_subject = urllib.parse.quote(short_subject)
        safe_short_body = urllib.parse.quote(short_body)
        safe_full_subject = urllib.parse.quote(full_subject)
        safe_full_body = urllib.parse.quote(full_body)

        links_section = ""
        # فقط روی ایمیل‌های انتخاب شده حلقه می‌زنیم
        for idx, email in enumerate(recipient_list, start=1):
            
            mailto_link = f"mailto:{email}?subject={safe_short_subject}&body={safe_short_body}"
            gmail_web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={safe_full_subject}&body={safe_full_body}"

            links_section += (
                f"📨 <b>گیرنده:</b> {email}\n"
                f"📱 <a href='{mailto_link}'> ارسال با اپلیکیشن موبایل روی لینک بالا (ایمیل) بزنید</a>\n"
                f"💻 <a href='{gmail_web_link}'>ارسال با Gmail Web</a>\n\n"
            )

        custom_info_display = ""
        if custom_info:
            custom_info_display = f"📌 <b>توضیحات شما:</b> {html.escape(shorten(custom_info))}\n"

        safe_subject_display = html.escape(full_subject)
        safe_body_display = html.escape(full_body)

        final_text = (
            "✅ <b>ایمیل شما آماده است</b>\n\n"
            "📱 <b>راهنمای موبایل:</b>\n"
            "روی دکمه ارسال بزنید. اگر باز نشد، متن پایین را کپی کنید.\n\n"
            f"📝 <b>موضوع:</b> {safe_subject_display}\n"
            f"{custom_info_display}\n"
            "👇 <b>لینک‌های ارسال:</b>\n\n"
            f"{links_section}"
            "━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Subject (برای کپی):</b>\n"
            f"<pre>{safe_subject_display}</pre>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✂️ <b>Body (برای کپی):</b>\n"
            f"<pre>{safe_body_display}</pre>"
        )

        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")]]

        await message.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"EMAIL_GEN_ERROR: {e}")
        await message.edit_text(f"❌ خطا: {str(e)[:100]}")