# در فایل handlers/email_gen.py

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

        # آماده‌سازی لینک‌ها
        # تبدیل خط جدید به فرمت استاندارد URL
        safe_body = urllib.parse.quote(email_body, safe='')
        safe_subject = urllib.parse.quote(email_subject, safe='')

        links_section = ""
        for email in target_data['emails']:
            # لینک ۱: مخصوص موبایل (باز کردن اپلیکیشن)
            mailto_link = f"mailto:{email}?subject={safe_subject}&body={safe_body}"
            
            # لینک ۲: مخصوص کامپیوتر (نسخه وب Gmail)
            gmail_web_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={safe_subject}&body={safe_body}"
            
            links_section += (
                f"👤 <b>گیرنده: {email}</b>\n"
                f"📱 <a href='{mailto_link}'>ارسال با اپلیکیشن (موبایل)</a>\n"
                f"💻 <a href='{gmail_web_link}'>ارسال با وب (کامپیوتر)</a>\n\n"
            )

        safe_body_display = html.escape(email_body)
        
        final_text = (
            f"✅ **متن آماده شد!**\n"
            f"{f'📌 <b>شامل توضیحات شما:</b> {html.escape(custom_info[:50])}...' if custom_info else ''}\n\n"
            f"🎯 <b>هدف:</b> {target_data['name']}\n"
            f"📝 <b>موضوع:</b> {email_subject}\n\n"
            f"👇 <b>یکی از لینک‌های زیر را انتخاب کنید:</b>\n\n"
            f"{links_section}"
            f"--------------------------------\n"
            f"⚠️ <i>اگر لینک‌ها کار نکرد، متن زیر را کپی کنید:</i>\n"
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