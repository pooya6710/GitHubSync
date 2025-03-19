import os
import logging
import telebot
import time
from flask import Flask, request
import threading

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# دریافت توکن ربات از متغیر محیطی
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("توکن ربات تلگرام یافت نشد!")
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN را در متغیرهای محیطی تنظیم کنید.")

# ایجاد نمونه ربات
bot = telebot.TeleBot(TOKEN)

# ایجاد نمونه فلسک
app = Flask(__name__)

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
    try:
        import platform
        import psutil
        
        # جمع‌آوری اطلاعات سیستم
        status_text = "📊 **وضعیت سرور:**\n\n"
        
        # اطلاعات سیستم‌عامل
        status_text += f"🔹 **سیستم عامل:** `{platform.platform()}`\n"
        status_text += f"🔹 **پایتون:** `{platform.python_version()}`\n"
        
        # اطلاعات CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        status_text += f"🔹 **CPU:** `{cpu_usage}%`\n"
        
        # اطلاعات RAM
        ram = psutil.virtual_memory()
        status_text += f"🔹 **RAM:** `{ram.used / (1024**3):.2f}GB / {ram.total / (1024**3):.2f}GB ({ram.percent}%)`\n"
        
        # اطلاعات دیسک
        disk = psutil.disk_usage('/')
        status_text += f"🔹 **دیسک:** `{disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB ({disk.percent}%)`\n"
        
        # زمان سرور
        import datetime
        status_text += f"🔹 **زمان سرور:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        
        # ارسال پیام
        bot.send_message(message.chat.id, status_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"خطا در دریافت وضعیت سرور: {e}")
        bot.send_message(message.chat.id, f"⚠ خطا در دریافت وضعیت سرور: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """پاسخ به همه پیام‌ها"""
    if "youtube.com" in message.text or "youtu.be" in message.text:
        # نمایش پیام در حال دانلود
        processing_msg = bot.reply_to(message, "🎬 لینک یوتیوب تشخیص داده شد. در حال دانلود...")
        
        # در واقعیت اینجا باید کد دانلود ویدیو از یوتیوب اجرا شود
        # اما برای این نمونه ساده فقط پیام ارسال می‌کنیم
        time.sleep(2)  # شبیه‌سازی زمان دانلود
        
        bot.edit_message_text(
            "✅ دانلود یوتیوب به صورت شبیه‌سازی انجام شد.\n"
            "در نسخه نهایی، ویدیو دانلود و ارسال خواهد شد.",
            message.chat.id,
            processing_msg.message_id
        )
        
    elif "instagram.com" in message.text:
        # نمایش پیام در حال دانلود
        processing_msg = bot.reply_to(message, "📸 لینک اینستاگرام تشخیص داده شد. در حال دانلود...")
        
        # در واقعیت اینجا باید کد دانلود پست اینستاگرام اجرا شود
        # اما برای این نمونه ساده فقط پیام ارسال می‌کنیم
        time.sleep(2)  # شبیه‌سازی زمان دانلود
        
        bot.edit_message_text(
            "✅ دانلود اینستاگرام به صورت شبیه‌سازی انجام شد.\n"
            "در نسخه نهایی، ویدیو دانلود و ارسال خواهد شد.",
            message.chat.id,
            processing_msg.message_id
        )
        
    else:
        bot.reply_to(message, "❌ لطفاً یک لینک معتبر از یوتیوب یا اینستاگرام ارسال کنید.")

# مسیر webhook برای دریافت پیام‌های تلگرام
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'ok', 200

@app.route('/')
def index():
    return 'ربات تلگرام در حال اجراست!'

@app.route('/status')
def status():
    return 'ربات تلگرام فعال است.'

# تابع شروع ربات با پولینگ
def start_polling():
    logger.info("شروع ربات با پولینگ...")
    bot.remove_webhook()
    bot.polling(none_stop=True)

# تابع شروع ربات با وب‌هوک
def start_webhook(url):
    logger.info(f"شروع ربات با وب‌هوک در آدرس {url}...")
    bot.remove_webhook()
    bot.set_webhook(url=f"{url}/{TOKEN}")
    return app

# تابع اصلی
def main():
    # تشخیص محیط اجرا (از متغیرهای محیطی)
    use_webhook = os.environ.get('USE_WEBHOOK', 'False').lower() == 'true'
    webhook_url = os.environ.get('WEBHOOK_URL', '')
    
    if use_webhook and webhook_url:
        # فقط اپلیکیشن فلسک را برگردان (برای استفاده با سرورهای مانند گونیکورن)
        return start_webhook(webhook_url)
    else:
        # اجرای ربات در حالت پولینگ و سرور فلسک در ترد جداگانه
        polling_thread = threading.Thread(target=start_polling)
        polling_thread.daemon = True
        polling_thread.start()
        
        # اجرای سرور فلسک
        return app

# اگر این فایل مستقیماً اجرا شود
if __name__ == "__main__":
    flask_app = main()
    flask_app.run(host='0.0.0.0', port=5000)