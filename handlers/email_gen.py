import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler # برای بازگشت به منو

ai_service = AIService()

# ---------------------------------------------------------
# مرحله ۱: وقتی کاربر روی اسم سازمان (مثلاً UN) کلیک می‌کند
# ---------------------------------------------------------
async def target_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_key = query.data
    target_data = TARGETS.get(target_key)
    
    if not target_data:
        return

    # ذخیره هدف انتخاب شده
    context.user_data['selected_target'] = target_data
    context.user_data['custom_info'] = None  

    text = (
        f"🎯 شما «{target_data['name']}» را انتخاب کردید.\n\n"
        "📊 **آیا می‌خواهید آمار یا جزئیات خاصی به متن اضافه کنید؟**"
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
# مرحله ۲: بررسی انتخاب کاربر (بله یا خیر)
# ---------------------------------------------------------
async def ask_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "ADD_DATA_NO":
        await generate_final_email(update, context)
    
    elif data == "ADD_DATA_YES":
        context.user_data['state'] = 'WAITING_FOR_DETAILS'
        
        # نکته مهم: پیام قبلی را حذف می‌کنیم تا صفحه تمیز شود
        await query.message.delete()

        # ارسال پیام جدید با ForceReply
        # این کار باعث می‌شود کیبورد کاربر خودکار باز شود و روی این پیام ریپلای کند
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✍️ لطفاً متن خود را بنویسید و ارسال کنید:",
            reply_markup=ForceReply(input_field_placeholder="مثلا: قطعی اینترنت در تهران...")
        )

# ---------------------------------------------------------
# مرحله ۳: دریافت متنی که کاربر تایپ کرده
# ---------------------------------------------------------
async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # چک می‌کنیم آیا کاربر اجازه تایپ دارد؟ (یعنی دکمه YES را زده؟)
    if context.user_data.get('state') != 'WAITING_FOR_DETAILS':
        # اگر کاربر همینطوری متنی فرستاد، آن را پاک می‌کنیم یا اخطار می‌دهیم
        try:
            await update.message.delete()  # پیام الکی کاربر را پاک کن
        except:
            pass
        
        # یک پیام موقت می‌فرستیم که "لطفا از دکمه‌ها استفاده کنید"
        msg = await update.message.reply_text("⛔️ لطفاً فقط از دکمه‌های منو استفاده کنید.")
        return 

    # دریافت متن کاربر
    user_text = update.message.text
    context.user_data['custom_info'] = user_text
    context.user_data['state'] = None # خروج از حالت انتظار

    # پیام "در حال دریافت"
    waiting_msg = await update.message.reply_text("⏳ دریافت شد! در حال نوشتن ایمیل...")
    
    # ساخت ایمیل نهایی
    await generate_final_email(update, context, message_object=waiting_msg)

# ---------------------------------------------------------
# مرحله ۴ (نهایی): ساخت و نمایش لینک Gmail
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get('selected_target')
    custom_info = context.user_data.get('custom_info')

    if not target_data:
        # اگر دیتایی نبود، برگرد به منوی اصلی
        await start_handler(update, context)
        return

    # تعیین پیامی که باید ادیت شود
    if message_object:
        message_to_edit = message_object
    elif update.callback_query:
        message_to_edit = update.callback_query.message
    else:
        return

    try:
        # تولید متن توسط AI
        email_body = await ai_service.generate_email(target_data['topic'], custom_details=custom_info)
        email_subject = target_data['topic']

        # آماده‌سازی لینک‌ها
        windows_compatible_body = email_body.replace("\n", "\r\n")
        safe_body = urllib.parse.quote(windows_compatible_body, safe='')
        safe_subject = urllib.parse.quote(email_subject, safe='')

        links_section = ""
        for email in target_data['emails']:
            gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={safe_subject}&body={safe_body}"
            links_section += f"🔴 <a href='{gmail_link}'>ارسال با GMAIL به {email}</a>\n\n"

        safe_body_display = html.escape(email_body)
        
        final_text = (
            f"✅ **متن آماده شد!**\n"
            f"{f'📌 <b>شامل توضیحات شما:</b> {html.escape(custom_info[:50])}...' if custom_info else ''}\n\n"
            f"🎯 <b>هدف:</b> {target_data['name']}\n"
            f"📝 <b>موضوع:</b> {email_subject}\n\n"
            f"👇 <b>روی لینک قرمز زیر بزنید تا GMAIL باز شود:</b>\n\n"
            f"{links_section}"
            f"--------------------------------\n"
            f"⚠️ <i>اگر لینک کار نکرد، متن زیر را کپی کنید:</i>\n"
            f"<pre>{safe_body_display}</pre>"
        )

        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")]]

        await message_to_edit.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Error: {e}")
        await message_to_edit.edit_text("❌ خطا در ارتباط با هوش مصنوعی.")