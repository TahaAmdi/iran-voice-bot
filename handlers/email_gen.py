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
# مرحله ۲: پرسش برای افزودن جزئیات
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
        try: await update.message.delete()
        except: pass
        await update.message.reply_text("⛔️ لطفاً فقط از دکمه‌های منو استفاده کنید.")
        return 

    user_text = update.message.text
    context.user_data['custom_info'] = user_text
    context.user_data['state'] = None 

    waiting_msg = await update.message.reply_text("⏳ دریافت شد! در حال نوشتن ایمیل...")
    await generate_final_email(update, context, message_object=waiting_msg)

# ---------------------------------------------------------
# مرحله ۴ (نهایی): دکمه‌ها اپلیکیشن را باز می‌کنند، متن کپی می‌شود
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
        # 1. تولید متن توسط AI
        email_body = await ai_service.generate_email(target_data['topic'], custom_details=custom_info)
        email_subject = target_data['topic']

        # 2. ساخت دکمه‌ها (فقط باز کردن اپلیکیشن ایمیل)
        keyboard = []
        for idx, email in enumerate(target_data['emails']):
            # لینک mailto ساده: فقط گیرنده را ست می‌کند
            # این لینک روی موبایل اپلیکیشن ایمیل را باز می‌کند و روی دسکتاپ برنامه پیش‌فرض را
            mailto_link = f"mailto:{email}"
            
            keyboard.append([InlineKeyboardButton(f"📧 باز کردن ایمیل (گیرنده {idx+1})", url=mailto_link)])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")])

        # 3. آماده‌سازی متن برای نمایش و کپی
        display_safe_subject = html.escape(email_subject)
        display_safe_body = html.escape(email_body)
        emails_list_str = ", ".join(target_data['emails'])

        # 4. پیام راهنما و متن‌ها
        final_text = (
            f"✅ **ایمیل شما آماده است!**\n\n"
            f"👤 **گیرندگان:** {html.escape(emails_list_str)}\n"
            f"──────────────────\n"
            f"۱. روی دکمه‌های بالا بزنید تا برنامه ایمیل باز شود.\n"
            f"۲. سپس **موضوع** و **متن** زیر را لمس کنید تا کپی شوند و در ایمیل خود Paste کنید:\n\n"
            
            f"👇 **موضوع (Subject):**\n"
            f"<code>{display_safe_subject}</code>\n\n" # کپی با یک کلیک
            
            f"👇 **متن ایمیل (Body):**\n"
            f"<code>{display_safe_body}</code>"      # کپی با یک کلیک
        )

        await message_to_edit.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Error: {e}")
        error_keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]]
        await message_to_edit.edit_text(
            text="❌ متاسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.", 
            reply_markup=InlineKeyboardMarkup(error_keyboard)
        )