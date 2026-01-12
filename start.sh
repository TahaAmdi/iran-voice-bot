#!/bin/bash

# اجرای سرور Flask در پس‌زمینه (Background)
python server.py &

# اجرای ربات تلگرام در پیش‌زمینه (Foreground)
python main.py