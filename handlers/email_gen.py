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
# هندلرهای انتخاب و دریافت متن (بدون تغییر)
# ---------------------------------------------------------
async def target_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_key = query.data
    target_data = TARGETS.get(target_key)
    if not target_data: return
    context.user_data['selected_target'] = target_data
    context.user_data['custom_info'] = None  
    text = (f"🎯 شما «{target_data['name']}» را انتخاب کردید.\n\n" "📊 **آیا می‌خواهید آمار یا جزئیات خاصی به متن اضافه کنید؟**")
    keyboard = [[InlineKeyboardButton("✅ بله، می‌نویسم", callback_data="ADD_DATA_YES")], [InlineKeyboardButton("❌ خیر، بساز", callback_data="ADD_DATA_NO")], [InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def ask_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "ADD_DATA_NO": await generate_final_email(update, context)
    elif query.data == "ADD_DATA_YES":
        context.user_data['state'] = 'WAITING_FOR_DETAILS'
        await query.message.delete()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✍️ لطفاً متن خود را بنویسید:", reply_markup=ForceReply(input_field_placeholder="مثلا: قطعی اینترنت..."))

async def receive_custom_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != 'WAITING_FOR_DETAILS':
        try: await update.message.delete()
        except: pass
        await update.message.reply_text("⛔️ لطفاً فقط از دکمه‌های منو استفاده کنید.")
        return 
    context.user_data['custom_info'] = update.message.text
    context.user_data['state'] = None 
    waiting_msg = await update.message.reply_text("⏳ در حال نوشتن ایمیل...")
    await generate_final_email(update, context, message_object=waiting_msg)

# ---------------------------------------------------------
# مرحله نهایی: چیدمان دقیق طبق عکس درخواستی
# ---------------------------------------------------------
async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get('selected_target')
    custom_info = context.user_data.get('custom_info')

    if not target_data:
        await start_handler(update, context)
        return

    message_to_edit = message_object or update.callback_query.message
    if not message_to_edit: return

    try:
        # 1. تولید متن توسط AI
        email_body = await ai_service.generate_email(target_data['topic'], custom_details=custom_info)
        email_subject = target_data['topic']

        # 2. آماده‌سازی لینک‌ها (Encoding)
        # برای لینک وب (کامل)
        windows_body = email_body.replace("\n", "\r\n")
        url_safe_body = urllib.parse.quote(windows_body, safe='')
        url_safe_subject = urllib.parse.quote(email_subject, safe='')

        # 3. ساخت دکمه‌ها (به ازای هر گیرنده ۲ دکمه)
        keyboard = []
        
        for idx, email in enumerate(target_data['emails']):
            # لینک موبایل: فقط mailto ساده (بدون موضوع/بدنه که کرش نکند)
            mobile_link = f"mailto:{email}"
            
            # لینک وب: کامل (Gmail Composer)
            web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={url_safe_subject}&body={url_safe_body}"
            
            # چیدمان: هر گیرنده در یک ردیف جداگانه با دو گزینه
            keyboard.append([
                InlineKeyboardButton(f"📱 موبایل (گیرنده {idx+1})", url=mobile_link),
                InlineKeyboardButton(f"💻 وب (Gmail)", url=web_link)
            ])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")])

        # 4. آماده‌سازی متن‌های کپی (HTML Escaping)
        display_safe_subject = html.escape(email_subject)
        display_safe_body = html.escape(email_body)
        
        # لیست ایمیل‌ها فقط جهت نمایش متنی
        emails_display = ", ".join([f"<code>{e}</code>" for e in target_data['emails']])

        # 5. چیدمان پیام نهایی (Header + Instructions + Copyable Text)
        final_text = (
            f"🎯 <b>هدف: {target_data['name']}</b>\n\n"
            f"✅ <b>ایمیل شما آماده است!</b>\n"
            f"دستورالعمل:\n"
            f"۱. برای موبایل دکمه «موبایل» و برای کامپیوتر «وب» را بزنید.\n"
            f"۲. اگر از دکمه موبایل استفاده کردید، متن‌های پایین را لمس کنید تا کپی شوند و در ایمیل Paste کنید.\n\n"
            
            f"📬 <b>لیست گیرندگان:</b>\n"
            f"{emails_display}\n\n"

            f"👇 <b>موضوع (Subject):</b>\n"
            f"<code>{display_safe_subject}</code>\n\n"
            
            f"👇 <b>متن ایمیل (Body):</b>\n"
            f"<code>{display_safe_body}</code>"
        )

        await message_to_edit.edit_text(
            text=final_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Error: {e}")
        err_kb = [[InlineKeyboardButton("🔙 بازگشت", callback_data="BACK_TO_MENU")]]
        await message_to_edit.edit_text("❌ خطا در تولید ایمیل.", reply_markup=InlineKeyboardMarkup(err_kb))