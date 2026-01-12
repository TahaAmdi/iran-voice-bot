import urllib.parse
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.ai_service import AIService

# ... بقیه ایمپورت‌ها و توابع مرحله ۱ تا ۳ ثابت بماند ...

async def generate_final_email(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object=None):
    target_data = context.user_data.get('selected_target')
    custom_info = context.user_data.get('custom_info')

    # تعیین پیامی که باید ادیت شود
    if message_object:
        message_to_edit = message_object
    elif update.callback_query:
        message_to_edit = update.callback_query.message
    else:
        return

    try:
        email_body = await ai_service.generate_email(target_data['topic'], custom_details=custom_info)
        email_subject = target_data['topic']

        # ترفند طلایی: فقط ۵۰۰ کاراکتر اول را برای موبایل می‌فرستیم تا لینک نشکند
        # این باعث می‌شود در موبایل، جیمیل با "شروع متن" باز شود
        body_for_mobile = email_body[:500] + "\n\n(ادامه متن را از تلگرام کپی و اینجا پیست کنید...)"
        
        safe_subject = urllib.parse.quote(email_subject)
        safe_body_mobile = urllib.parse.quote(body_for_mobile)
        safe_body_web = urllib.parse.quote(email_body) # دسکتاپ محدودیت ندارد

        keyboard = []
        for email in target_data['emails']:
            # لینک مخصوص موبایل (که حالا متن کوتاه‌تری دارد و حتما باز می‌شود)
            mailto_url = f"mailto:{email}?subject={safe_subject}&body={safe_body_mobile}"
            # لینک وب برای لپ‌تاپ
            web_url = f"https://mail.google.com/mail/u/0/?view=cm&fs=1&to={email}&su={safe_subject}&body={safe_body_web}"
            
            keyboard.append([InlineKeyboardButton(f"📱 ارسال سریع با گوشی ({email})", url=mailto_url)])
            keyboard.append([InlineKeyboardButton(f"💻 ارسال کامل با کامپیوتر", url=web_url)])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="BACK_TO_MENU")])

        safe_body_display = html.escape(email_body)
        
        await message_to_edit.edit_text(
            text=(
                f"✅ **متن آماده شد!**\n\n"
                f"📱 **در موبایل:** بعد از زدن دکمه، اگر متن ناقص بود، بقیه را از کادر زیر کپی و در ایمیل Paste کنید.\n\n"
                f"<pre>{safe_body_display}</pre>"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        print(f"Error: {e}")
        await message_to_edit.edit_text("❌ خطا در تولید ایمیل.")