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
# مرحله ۴ (نهایی): ساخت دکمه‌های ایمیل
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

        # نکته حیاتی: محدود کردن طول متن داخل لینک
        # اگر متن بیشتر از 1000 کاراکتر باشد، لینک خراب می‌شود.
        # پس برای لینک، متن را کوتاه می‌کنیم اما متن کامل را در پیام نمایش می‌دهیم.
        short_body = email_body[:800] + "\n\n[...Text continues...]" if len(email_body) > 800 else email_body
        
        # اینکود کردن متن
        safe_body_short = urllib.parse.quote(short_body)
        safe_subject = urllib.parse.quote(email_subject)
        
        # اینکود متن کامل برای نسخه وب (چون وب تحمل بیشتری دارد)
        safe_body_full = urllib.parse.quote(email_body)

        keyboard = []
        
        # ساخت دکمه‌ها برای هر ایمیل
        for email in target_data['emails']:
            # لینک موبایل (Mailto)
            mailto_link = f"mailto:{email}?subject={safe_subject}&body={safe_body_short}"
            
            # لینک وب (Gmail Web)
            gmail_web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={safe_subject}&body={safe_body_full}"
            
            # اضافه کردن دکمه‌ها
            keyboard.append([InlineKeyboardButton(f"📱 ارسال با ایمیل‌باکس گوشی ({email})", url=mailto_link)])
            keyboard.append([InlineKeyboardButton(f"💻 ارسال با Gmail Web", url=gmail_web_link)])

        # دکمه بازگشت
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")])

        safe_body_display = html.escape(email_body)
        
        final_text = (
            f"✅ **متن آماده شد!**\n"
            f"🎯 <b>هدف:</b> {target_data['name']}\n"
            f"📝 <b>موضوع:</b> {email_subject}\n\n"
            f"👇 <b>روی دکمه‌های زیر کلیک کنید:</b>\n"
            f"(اگر دکمه موبایل متن را کامل نیاورد، متن زیر را دستی کپی کنید)\n\n"
            f"🔻 <b>متن کامل ایمیل:</b>\n"
            f"<pre>{safe_body_display}</pre>"
        )

        await message_to_edit.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Error: {e}")
        # اگر حتی با کوتاه کردن هم ارور داد، لینک‌ها را حذف می‌کنیم و فقط متن می‌دهیم
        safe_body_display = html.escape(email_body)
        fallback_text = (
            f"✅ **متن آماده شد!**\n\n"
            f"⚠️ *لینک خودکار به دلیل طولانی بودن متن ساخته نشد.*\n"
            f"لطفاً متن زیر را کپی کرده و دستی ایمیل کنید:\n\n"
            f"📧 **گیرنده:** {', '.join(target_data['emails'])}\n"
            f"📝 **موضوع:** {email_subject}\n\n"
            f"<pre>{safe_body_display}</pre>"
        )
        await message_to_edit.edit_text(
            text=fallback_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]]),
            parse_mode=ParseMode.HTML
        )