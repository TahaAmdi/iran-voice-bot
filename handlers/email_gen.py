import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler 

ai_service = AIService()

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
# مرحله ۲: پرسش برای دریافت متن
# ---------------------------------------------------------
async def ask_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "ADD_DATA_NO":
        await generate_final_email(update, context)
    
    elif data == "ADD_DATA_YES":
        context.user_data['state'] = 'WAITING_FOR_DETAILS'
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✍️ لطفاً متن خود را بنویسید و ارسال کنید:",
            reply_markup=ForceReply(input_field_placeholder="مثلا: قطعی اینترنت در تهران...")
        )

# ---------------------------------------------------------
# مرحله ۳: دریافت متن کاربر
# ---------------------------------------------------------
async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != 'WAITING_FOR_DETAILS':
        try:
            await update.message.delete()
        except:
            pass
        msg = await update.message.reply_text("⛔️ لطفاً فقط از دکمه‌های منو استفاده کنید.")
        return 

    user_text = update.message.text
    context.user_data['custom_info'] = user_text
    context.user_data['state'] = None 

    waiting_msg = await update.message.reply_text("⏳ دریافت شد! در حال نوشتن ایمیل...")
    await generate_final_email(update, context, message_object=waiting_msg)

# ---------------------------------------------------------
# مرحله ۴ (نهایی): ساخت لینک‌ها
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get('selected_target')
    custom_info = context.user_data.get('custom_info')

    if not target_data:
        await start_handler(update, context)
        return

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

        # اینکود کردن متن برای قرارگیری در URL
        safe_body = urllib.parse.quote(email_body)
        safe_subject = urllib.parse.quote(email_subject)

        links_section = ""
        # شمارنده برای اینکه اگر چند ایمیل بود، مشخص شود
        count = 1
        
        for email in target_data['emails']:
            # لینک ۱: Mailto (استاندارد جهانی موبایل)
            # نکته: در اندروید و iOS این بهترین روش است
            mailto_link = f"mailto:{email}?subject={safe_subject}&body={safe_body}"
            
            # لینک ۲: وب (فقط دسکتاپ)
            gmail_web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={safe_subject}&body={safe_body}"
            
            links_section += (
                f"📨 <b>گیرنده {count}:</b> {email}\n"
                f"📱 <a href='{mailto_link}'>کلیک برای موبایل (App)</a>\n"
                f"💻 <a href='{gmail_web_link}'>کلیک برای کامپیوتر (Web)</a>\n\n"
            )
            count += 1

        safe_body_display = html.escape(email_body)
        
        final_text = (
            f"✅ **متن آماده شد!**\n"
            f"{f'📌 <b>توضیحات شما:</b> {html.escape(custom_info[:50])}...' if custom_info else ''}\n\n"
            f"📝 <b>موضوع:</b> {email_subject}\n\n"
            f"👇 <b>لطفاً بر اساس دستگاه خود انتخاب کنید:</b>\n\n"
            f"{links_section}"
            f"--------------------------------\n"
            f"⚠️ <i>نکته مهم: اگر لینک موبایل کار نکرد، یعنی متن ایمیل خیلی طولانی شده است. لطفاً متن زیر را دستی کپی کنید:</i>\n\n"
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