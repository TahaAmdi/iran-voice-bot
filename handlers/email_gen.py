import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.ai_service import AIService
from config.targets import TARGETS
from handlers.menu import start_handler

ai_service = AIService()

MAX_MAILTO_BODY_LEN = 1800 

def shorten(text: str, n: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n] + "…"

# ---------------------------------------------------------
# هندلرهای ورودی
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
    waiting_msg = await update.message.reply_text("⏳ در حال تولید متن ایمیل و توییت...")
    await generate_final_email(update, context, message_object=waiting_msg)

# ---------------------------------------------------------
# مرحله نهایی: رفع باگ SyntaxError و ساخت خروجی
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
        # 1. تولید محتوا (ایمیل + توییت)
        email_body = await ai_service.generate_email(target_data['topic'], custom_details=custom_info)
        email_subject = target_data['topic']
        
        # توییت (اگر آیدی توییتر داشته باشد)
        twitter_handle = target_data.get('twitter')
        tweet_text = ""
        if twitter_handle:
            tweet_text = await ai_service.generate_tweet(target_data['topic'], twitter_handle, custom_info)

        # 2. انکودینگ ایمیل
        email_body = email_body.strip()
        url_safe_body = urllib.parse.quote(email_body, safe='')
        url_safe_subject = urllib.parse.quote(email_subject, safe='')

        keyboard = []
        
        # دکمه‌های ایمیل
        for idx, email in enumerate(target_data['emails']):
            clean_email = email.strip()
            web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={clean_email}&su={url_safe_subject}&body={url_safe_body}"
            if len(web_link) > 2000:
                web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={clean_email}&su={url_safe_subject}"

            keyboard.append([InlineKeyboardButton(f"📧 ارسال ایمیل (گیرنده {idx+1})", url=web_link)])

        # دکمه توییتر
        if twitter_handle and tweet_text:
            safe_tweet = urllib.parse.quote(tweet_text, safe='')
            twitter_link = f"https://twitter.com/intent/tweet?text={safe_tweet}"
            keyboard.append([
                InlineKeyboardButton(f"🐦 ارسال توییت به {twitter_handle}", url=twitter_link)
            ])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")])

        # 3. نمایش متن‌ها
        display_safe_subject = html.escape(email_subject)
        display_safe_body = html.escape(email_body)
        emails_display = ", ".join([f"<code>{e}</code>" for e in target_data['emails']])

        # --- رفع باگ: محاسبه بخش‌های شرطی بیرون از f-string ---
        
        # بخش توییت
        tweet_display_section = ""
        if tweet_text:
            tweet_display_section = (
                f"🐦 <b>متن توییت (X):</b>\n"
                f"<code>{html.escape(tweet_text)}</code>\n"
                f"(اگر دکمه کار نکرد، متن بالا را کپی کنید و در توییتر پست کنید)\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )
            
        # بخش توضیحات اضافی (Custom Info)
        custom_info_section = ""
        if custom_info:
            custom_info_section = f"📌 <b>توضیحات:</b> {html.escape(shorten(custom_info))}\n"

        # --- متن نهایی ---
        final_text = (
            f"🎯 <b>هدف: {target_data['name']}</b>\n\n"
            f"✅ <b>محتوا آماده شد!</b>\n\n"
            
            f"{tweet_display_section}"

            f"📧 <b>متن ایمیل:</b>\n"
            f"۱. دکمه ارسال ایمیل را بزنید.\n"
            f"۲. اگر از موبایل هستید، متن‌های زیر را کپی و در اپ ایمیل Paste کنید:\n\n"
            
            f"📬 <b>گیرندگان:</b>\n"
            f"{emails_display}\n\n"

            f"👇 <b>موضوع (Subject):</b>\n"
            f"<code>{display_safe_subject}</code>\n\n"
            
            f"{custom_info_section}"
            
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
        await message_to_edit.edit_text(
            text="❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.", 
            reply_markup=InlineKeyboardMarkup(err_kb)
        )