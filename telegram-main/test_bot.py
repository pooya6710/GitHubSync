import os
import telebot
import logging

# تنظیم لاگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# دریافت توکن ربات از متغیر محیطی
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("No TELEGRAM_BOT_TOKEN found in environment variables!")
    exit(1)

# ایجاد نمونه ربات
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """پاسخ به دستور /start و /help"""
    bot.reply_to(message, 
                "👋 سلام! من ربات دانلود ویدیو هستم.\n"
                "می‌توانم ویدیوهای یوتیوب و اینستاگرام را دانلود کنم.\n"
                "کافیست لینک ویدیو را برای من ارسال کنید.")

@bot.message_handler(commands=['status'])
def handle_status(message):
    """نمایش وضعیت سرور"""
    bot.reply_to(message, "✅ ربات فعال است و در حال کار می‌باشد.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """پاسخ به همه پیام‌ها"""
    if "youtube.com" in message.text or "youtu.be" in message.text:
        bot.reply_to(message, "🎬 لینک یوتیوب تشخیص داده شد. در حال پردازش...")
    elif "instagram.com" in message.text:
        bot.reply_to(message, "📸 لینک اینستاگرام تشخیص داده شد. در حال پردازش...")
    else:
        bot.reply_to(message, "❌ لطفاً یک لینک معتبر از یوتیوب یا اینستاگرام ارسال کنید.")

def main():
    """تابع اصلی اجرای ربات"""
    logger.info("Starting the Telegram bot...")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    main()