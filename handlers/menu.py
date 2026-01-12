from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from config.targets import TARGETS  # خواندن لیست هدف‌ها

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش منوی اصلی با متن فارسی و دکمه‌های فارسی‌سازی شده.
    """
    
    # متن خوش‌آمدگویی (بر اساس عکسی که فرستادید)
    welcome_text = (
        "👋 <b>سلام هموطن! به «صدای ایران» خوش آمدی.</b>\n\n"
        
        "🕊 <b>صدای تو، قوی‌ترین سلاح است.</b>\n"
        "در شرایطی که تلاش می‌شود صدای ما خاموش بماند، ما فریاد می‌زنیم. "
        "هر ایمیل شما، یک سند ثبت‌شده در تاریخ و یک فشار دیپلماتیک بر مسئولین جهانی است.\n\n"
        
        "🛡 <b>امنیت شما، اولویت اصلی ماست:</b>\n"
        "🔒 <b>بدون ذخیره‌سازی:</b> این ربات هیچ لاگی از نام، آیدی یا شماره شما نگه نمی‌دارد.\n"
        "✉️ <b>ارسال امن:</b> ایمیل‌ها مستقیماً از اپلیکیشن شخصی شما (Gmail/Outlook) ارسال می‌شوند و ربات هیچ دسترسی به اکانت شما ندارد.\n"
        "🤖 <b>متن هوشمند:</b> متن‌ها توسط هوش مصنوعی تولید می‌شوند تا هر ایمیل منحصر‌به‌فرد باشد و اسپم نشود.\n\n"
        
        "👇 <b>همین حالا سازمان یا نهاد مورد نظر را انتخاب کنید:</b>"
    )

    # ساخت دکمه‌ها با اولویت نام فارسی
    keyboard = []
    for key, data in TARGETS.items():
        # ✅ تغییر اصلی اینجاست: استفاده از name_fa به جای name
        button_text = data.get('name_fa', data['name'])
        keyboard.append([InlineKeyboardButton(button_text, callback_data=key)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # مدیریت نمایش پیام
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )