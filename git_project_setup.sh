#!/bin/bash

# اسکریپت تنظیم پروژه گیت
# این اسکریپت یک مخزن گیت را دریافت کرده و آن را آماده‌ی اجرا می‌کند
# همچنین تنظیمات لازم برای توسعه‌ی آینده را فراهم می‌کند

# بررسی وجود آدرس مخزن گیت
if [ -z "$1" ]
then
    echo "خطا: آدرس مخزن گیت وارد نشده است."
    echo "استفاده از اسکریپت:"
    echo "  ./git_project_setup.sh [آدرس مخزن گیت]"
    echo "مثال:"
    echo "  ./git_project_setup.sh https://github.com/username/repository.git"
    echo "توضیحات:"
    echo "این اسکریپت یک مخزن گیت را دریافت کرده و آن را آماده‌ی اجرا می‌کند."
    echo "همچنین تنظیمات لازم برای توسعه‌ی آینده را فراهم می‌کند."
    exit 1
fi

# ذخیره آدرس مخزن گیت
REPO_URL=$1

# پاکسازی پوشه‌های موجود
if [ -d "telegram-main" ]; then
    echo "در حال پاکسازی پوشه قبلی..."
    rm -rf telegram-main
fi

# کلون کردن مخزن گیت
echo "در حال دریافت مخزن گیت از آدرس $REPO_URL ..."
git clone $REPO_URL telegram-main

if [ $? -ne 0 ]; then
    echo "خطا در دریافت مخزن گیت!"
    exit 1
fi

cd telegram-main

# نصب وابستگی‌ها
echo "در حال نصب وابستگی‌ها..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "فایل requirements.txt یافت نشد. نصب وابستگی‌های پیش‌فرض..."
    pip install pytelegrambotapi flask psutil yt-dlp
fi

# ایجاد پوشه‌های مورد نیاز
echo "در حال ایجاد پوشه‌های مورد نیاز..."
mkdir -p temp_downloads
mkdir -p static/css

# بررسی وجود فایل اصلی
if [ -f "run_telegram_bot.py" ]; then
    echo "فایل اصلی یافت شد: run_telegram_bot.py"
    chmod +x run_telegram_bot.py
elif [ -f "main.py" ]; then
    echo "فایل اصلی یافت شد: main.py"
    chmod +x main.py
elif [ -f "bot.py" ]; then
    echo "فایل اصلی یافت شد: bot.py"
    chmod +x bot.py
else
    echo "هیچ فایل اصلی یافت نشد!"
    exit 1
fi

# تنظیم مجوز اجرا برای تمامی فایل‌های پایتون
find . -name "*.py" -exec chmod +x {} \;

echo "آماده‌سازی پروژه با موفقیت انجام شد!"
echo "برای اجرای ربات، دستور زیر را وارد کنید:"
echo "cd telegram-main && python run_telegram_bot.py"