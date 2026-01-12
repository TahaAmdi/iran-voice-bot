from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from config.targets import TARGETS  # خواندن لیست هدف‌ها از کانفیگ

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش منوی اصلی با متن جذاب، انگیزشی و توضیحات امنیتی.
    این هندلر هم دستور /start و هم دکمه «بازگشت به منو» را مدیریت می‌کند.
    """
    
    # متن خوش‌آمدگویی با فرمت HTML
    welcome_text = (
        "👋 <b>سلام هموطن! به «صدای ایران» خوش آمدی.</b>\n\n"
        
        "🕊 <b>صدای تو، قوی‌ترین سلاح است.</b>\n"
        "در شرایطی که تلاش می‌شود صدای ما خاموش بماند، ما فریاد می‌زنیم. "
        "هر ایمیل شما، یک سند ثبت‌شده در تاریخ و یک فشار دیپلماتیک بر مسئولین جهانی است.\n\n"
        
        "🛡 <b>امنیت شما، اولویت اصلی ماست:</b>\n"
        "🔒 <b>بدون ذخیره‌سازی:</b> این ربات هیچ لاگی از نام، آیدی یا شماره شما نگه نمی‌دارد.\n"
        "✉️ <b>ارسال امن:</b> ایمیل‌ها مستقیماً از اپلیکیشن شخصی شما (Gmail/Outlook) ارسال می‌شوند و ربات هیچ دسترسی به اکانت شما ندارد.\n"
        "🤖 <b>متن هوشمند:</b> متن‌ها توسط هوش مصنوعی تولید می‌شوند تا هر ایمیل منحصر‌به‌فرد باشد و اسپم نشود.\n\n"
        
        "👇 <b>همین حالا سازمان یا نهاد مورد نظر را انتخاب کنید و صدای بی‌صدایان باشید:</b>"
    )

    # ساخت دکمه‌ها از روی لیست TARGETS موجود در فایل کانفیگ
    keyboard = []
    for key, data in TARGETS.items():
        # نام دکمه را از کانفیگ می‌خوانیم
        button_text = data['name']
        keyboard.append([InlineKeyboardButton(button_text, callback_data=key)])

    # لینک به گیت‌هاب (اختیاری - اگر دارید آن‌کامنت کنید)
    # keyboard.append([InlineKeyboardButton("کد منبع باز (Open Source) 🌐", url="https://github.com/YOUR_USERNAME/YOUR_REPO")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # تشخیص اینکه دستور استارت بوده یا دکمه بازگشت
    if update.callback_query:
        # حالت دکمه بازگشت (پیام قبلی ویرایش می‌شود تا صفحه شلوغ نشود)
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # حالت دستور /start (پیام جدید ارسال می‌شود)
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )