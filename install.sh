#!/bin/bash

# اسکریپت نصب ربات تلگرام
# این اسکریپت تمام مراحل راه‌اندازی ربات تلگرام را انجام می‌دهد

# رنگ‌های ترمینال
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# نمایش راهنما
echo -e "${BLUE}=================================================${NC}"
echo -e "${YELLOW}         نصب و راه‌اندازی ربات تلگرام دانلود ویدیو${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "\n${GREEN}این اسکریپت ربات تلگرام دانلود ویدیو را نصب و راه‌اندازی می‌کند.${NC}\n"

# بررسی وجود آدرس مخزن گیت
if [ -z "$1" ]
then
    # آدرس پیش‌فرض مخزن گیت
    GIT_REPO="https://github.com/pooya6710/telegram.git"
    echo -e "${YELLOW}نکته: آدرس مخزن گیت وارد نشده است. از آدرس پیش‌فرض استفاده می‌شود:${NC}"
    echo -e "${BLUE}$GIT_REPO${NC}\n"
else
    GIT_REPO=$1
    echo -e "${GREEN}استفاده از مخزن گیت:${NC} ${BLUE}$GIT_REPO${NC}\n"
fi

# بررسی نصب گیت
if ! command -v git &> /dev/null
then
    echo -e "${YELLOW}گیت نصب نشده است. در حال نصب گیت...${NC}"
    apt-get update && apt-get install -y git
    if [ $? -ne 0 ]; then
        echo -e "${RED}خطا در نصب گیت!${NC}"
        exit 1
    fi
fi

# بررسی نصب پایتون
if ! command -v python3 &> /dev/null
then
    echo -e "${YELLOW}پایتون 3 نصب نشده است. در حال نصب پایتون 3...${NC}"
    apt-get update && apt-get install -y python3 python3-pip
    if [ $? -ne 0 ]; then
        echo -e "${RED}خطا در نصب پایتون 3!${NC}"
        exit 1
    fi
fi

# اجرای اسکریپت تنظیم پروژه گیت
echo -e "${GREEN}در حال اجرای اسکریپت تنظیم پروژه گیت...${NC}"
./git_project_setup.sh $GIT_REPO

if [ $? -ne 0 ]; then
    echo -e "${RED}خطا در اجرای اسکریپت تنظیم پروژه گیت!${NC}"
    exit 1
fi

# درخواست توکن ربات تلگرام
echo -e "\n${YELLOW}برای راه‌اندازی ربات، نیاز به توکن ربات تلگرام دارید.${NC}"
echo -e "${BLUE}توکن ربات را می‌توانید از @BotFather در تلگرام دریافت کنید.${NC}"
echo -e "${YELLOW}توکن ربات تلگرام خود را وارد کنید:${NC}"
read -p "> " TELEGRAM_BOT_TOKEN

if [ -z "$TELEGRAM_BOT_TOKEN" ]
then
    echo -e "${RED}خطا: توکن ربات تلگرام وارد نشده است!${NC}"
    exit 1
else
    # ذخیره توکن در متغیر محیطی
    export TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
    
    # ذخیره توکن در فایل .env
    echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" > ./telegram-main/.env
    echo -e "${GREEN}توکن ربات تلگرام با موفقیت ذخیره شد.${NC}"
fi

# اجرای ربات
echo -e "\n${GREEN}در حال راه‌اندازی ربات تلگرام...${NC}"
cd telegram-main && python3 run_telegram_bot.py