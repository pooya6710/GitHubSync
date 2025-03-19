#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ربات تلگرام برای دانلود ویدیو از یوتیوب و اینستاگرام
این ربات امکان دانلود ویدیو از یوتیوب و اینستاگرام را فراهم می‌کند
"""

import os
import sys
import json
import time
import datetime
import traceback
import logging
import threading
import concurrent.futures

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        logging.FileHandler("debug_logs.txt", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# واردکردن ماژول‌های خارجی با مدیریت خطا
try:
    import telebot
    from telebot import types
    logger.info("✅ ماژول telebot با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول telebot نصب نشده است")
    print("نصب telebot با دستور: pip install pytelegrambotapi")
    sys.exit(1)

try:
    import requests
    logger.info("✅ ماژول requests با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول requests نصب نشده است")
    print("نصب requests با دستور: pip install requests")
    sys.exit(1)

try:
    import psutil
    logger.info("✅ ماژول psutil با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول psutil نصب نشده است")
    psutil = None
    print("نصب psutil با دستور: pip install psutil")

try:
    from flask import Flask, request
    logger.info("✅ ماژول flask با موفقیت بارگذاری شد")
    USE_FLASK = True
except ImportError:
    logger.error("⚠️ ماژول flask نصب نشده است")
    USE_FLASK = False
    print("نصب flask با دستور: pip install flask")

try:
    from yt_dlp import YoutubeDL
    logger.info("✅ ماژول yt-dlp با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول yt-dlp نصب نشده است")
    print("نصب yt-dlp با دستور: pip install yt-dlp")
    sys.exit(1)

# متغیرهای محیطی و تنظیمات
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("توکن ربات تلگرام یافت نشد!")
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN را در متغیرهای محیطی تنظیم کنید.")

# شناسه‌های ادمین و کانال‌ها
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
DEFAULT_VIDEO_QUALITY = "360p"  # کیفیت پیش‌فرض ویدیو
MAX_VIDEOS_TO_KEEP = 50  # حداکثر تعداد ویدیو برای نگهداری در پوشه temp_downloads

# ایجاد نمونه ربات
bot = telebot.TeleBot(TOKEN)

# پوشه دانلودها
TEMP_DOWNLOAD_DIR = "temp_downloads"
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

# بررسی اعتبار لینک یوتیوب
def is_youtube_url(url: str) -> bool:
    """بررسی اعتبار لینک یوتیوب"""
    return "youtube.com" in url or "youtu.be" in url

# بررسی اعتبار لینک اینستاگرام
def is_instagram_url(url: str) -> bool:
    """بررسی اعتبار لینک اینستاگرام"""
    return "instagram.com" in url or "instagr.am" in url

# دانلود ویدیو از یوتیوب
def process_youtube_url(message, url):
    """پردازش لینک یوتیوب و دانلود آن"""
    user_id = message.from_user.id
    quality = "360p"  # کیفیت پیش‌فرض
    
    # نمایش پیام در حال دانلود
    processing_msg = bot.reply_to(message, "🎬 لینک یوتیوب تشخیص داده شد. در حال دانلود...")
    
    try:
        # تنظیمات yt-dlp
        ydl_opts = {
            'format': 'best[height<=360]/bestvideo[height<=360]+bestaudio/best',
            'outtmpl': f'{TEMP_DOWNLOAD_DIR}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': True
        }
        
        # دانلود ویدیو
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                bot.edit_message_text(
                    "❌ خطا در دانلود ویدیو. لطفاً از لینک دیگری استفاده کنید.",
                    message.chat.id,
                    processing_msg.message_id
                )
                return
            
            video_path = ydl.prepare_filename(info)
            title = info.get('title', 'ویدیوی دانلود شده')
            
            # بررسی وجود فایل
            if not os.path.exists(video_path):
                # سعی می‌کنیم پسوند فایل را بررسی کنیم
                for ext in ['mp4', 'webm', 'mkv']:
                    possible_path = os.path.splitext(video_path)[0] + f'.{ext}'
                    if os.path.exists(possible_path):
                        video_path = possible_path
                        break
            
            # ارسال ویدیو
            if os.path.exists(video_path):
                with open(video_path, 'rb') as video_file:
                    bot.edit_message_text(
                        "✅ دانلود با موفقیت انجام شد. در حال ارسال ویدیو...",
                        message.chat.id,
                        processing_msg.message_id
                    )
                    
                    # ارسال ویدیو
                    bot.send_video(
                        message.chat.id,
                        video_file,
                        caption=f"🎬 {title}\n\n🔗 {url}",
                        supports_streaming=True,
                        reply_to_message_id=message.message_id
                    )
                    
                    # حذف پیام "در حال دانلود"
                    bot.delete_message(message.chat.id, processing_msg.message_id)
                    
                    # پاکسازی فایل
                    try:
                        os.remove(video_path)
                    except:
                        pass
            else:
                bot.edit_message_text(
                    "❌ خطا در دانلود ویدیو. فایل دانلود شده یافت نشد.",
                    message.chat.id,
                    processing_msg.message_id
                )
    
    except Exception as e:
        bot.edit_message_text(
            f"⚠️ خطا در دانلود ویدیو: {str(e)}",
            message.chat.id,
            processing_msg.message_id
        )
        logger.error(f"خطا در دانلود یوتیوب: {e}", exc_info=True)

# دانلود پست اینستاگرام
def process_instagram_url(message, url):
    """پردازش لینک اینستاگرام و دانلود آن"""
    # نمایش پیام در حال دانلود
    processing_msg = bot.reply_to(message, "📸 لینک اینستاگرام تشخیص داده شد. در حال دانلود...")
    
    try:
        # ایجاد پوشه موقت برای ذخیره فایل‌ها
        url_hash = url.replace("/", "_").replace(":", "_")
        temp_dir = f"{TEMP_DOWNLOAD_DIR}/insta_{url_hash}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # استفاده از yt-dlp برای دانلود پست اینستاگرام
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info is None:
                bot.edit_message_text(
                    "❌ خطا در دانلود پست اینستاگرام. لطفاً از لینک دیگری استفاده کنید.",
                    message.chat.id,
                    processing_msg.message_id
                )
                return
            
            # جستجوی فایل‌های دانلود شده
            media_files = []
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and not file.endswith('.txt'):
                    media_files.append(file_path)
            
            if not media_files:
                bot.edit_message_text(
                    "❌ فایل رسانه‌ای در پست اینستاگرام یافت نشد.",
                    message.chat.id,
                    processing_msg.message_id
                )
                return
            
            # ارسال فایل‌ها
            bot.edit_message_text(
                f"✅ دانلود با موفقیت انجام شد. در حال ارسال {len(media_files)} فایل...",
                message.chat.id,
                processing_msg.message_id
            )
            
            for file_path in media_files[:10]:  # محدودیت 10 فایل
                if file_path.endswith(('.mp4', '.mov')):
                    with open(file_path, 'rb') as video_file:
                        bot.send_video(
                            message.chat.id,
                            video_file,
                            caption=f"📸 پست اینستاگرام\n\n🔗 {url}",
                            supports_streaming=True
                        )
                elif file_path.endswith(('.jpg', '.jpeg', '.png')):
                    with open(file_path, 'rb') as photo_file:
                        bot.send_photo(
                            message.chat.id,
                            photo_file,
                            caption=f"📸 پست اینستاگرام\n\n🔗 {url}"
                        )
            
            # حذف پوشه موقت
            try:
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
            except:
                pass
            
            # حذف پیام "در حال دانلود"
            bot.delete_message(message.chat.id, processing_msg.message_id)
    
    except Exception as e:
        bot.edit_message_text(
            f"⚠️ خطا در دانلود پست اینستاگرام: {str(e)}",
            message.chat.id,
            processing_msg.message_id
        )
        logger.error(f"خطا در دانلود اینستاگرام: {e}", exc_info=True)

# دستور /start
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """پاسخ به دستور /start و /help"""
    # ایجاد کیبورد اینلاین با دکمه‌های مختلف
    markup = types.InlineKeyboardMarkup(row_width=2)
    help_btn = types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
    quality_btn = types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
    status_btn = types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="server_status")
    
    markup.add(help_btn, quality_btn)
    markup.add(status_btn)
    
    bot.send_message(
        message.chat.id,
        f"👋 سلام {message.from_user.first_name}!\n\n"
        "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
        "🔸 <b>قابلیت‌های ربات:</b>\n"
        "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
        "• امکان انتخاب کیفیت ویدیو\n"
        "• پاسخ‌گویی به سوالات متداول\n\n"
        "🔹 <b>روش استفاده:</b>\n"
        "کافیست لینک ویدیوی مورد نظر خود را از یوتیوب یا اینستاگرام ارسال کنید.",
        parse_mode="HTML",
        reply_markup=markup
    )

# دستور /status
@bot.message_handler(commands=['status'])
def handle_status(message):
    """نمایش وضعیت سرور"""
    try:
        import platform
        
        # جمع‌آوری اطلاعات سیستم
        status_sections = ["📊 **وضعیت سرور:**\n\n"]
        
        # اطلاعات سیستم‌عامل
        try:
            status_sections.append(f"🔹 **سیستم عامل:** `{platform.platform()}`\n")
            status_sections.append(f"🔹 **پایتون:** `{platform.python_version()}`\n")
        except Exception as e:
            status_sections.append("🔹 **سیستم عامل:** `اطلاعات در دسترس نیست`\n")
            logger.error(f"خطا در دریافت اطلاعات سیستم: {e}")
        
        # CPU
        if psutil:
            try:
                cpu_usage = psutil.cpu_percent(interval=1)
                status_sections.append(f"🔹 **CPU:** `{cpu_usage}%`\n")
            except Exception as e:
                status_sections.append("🔹 **CPU:** `اطلاعات در دسترس نیست`\n")
                logger.error(f"خطا در دریافت اطلاعات CPU: {e}")
            
            # RAM
            try:
                ram = psutil.virtual_memory()
                status_sections.append(f"🔹 **RAM:** `{ram.used / (1024**3):.2f}GB / {ram.total / (1024**3):.2f}GB`\n")
            except Exception as e:
                status_sections.append("🔹 **RAM:** `اطلاعات در دسترس نیست`\n")
                logger.error(f"خطا در دریافت اطلاعات RAM: {e}")
            
            # فضای دیسک
            try:
                disk = psutil.disk_usage('/')
                status_sections.append(f"🔹 **دیسک:** `{disk.used / (1024**3):.2f}GB / {disk.total / (1024**3):.2f}GB ({disk.percent}%)`\n")
            except Exception as e:
                status_sections.append("🔹 **فضای دیسک:** `اطلاعات در دسترس نیست`\n")
                logger.error(f"خطا در دریافت اطلاعات دیسک: {e}")
        else:
            status_sections.append("🔹 **منابع سیستم:** `اطلاعات در دسترس نیست (psutil نصب نشده)`\n")
        
        # زمان سرور
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_sections.append(f"🔹 **زمان سرور:** `{current_time}`\n")
        except Exception as e:
            status_sections.append("🔹 **زمان سرور:** `اطلاعات در دسترس نیست`\n")
            logger.error(f"خطا در دریافت اطلاعات زمان: {e}")
        
        # وضعیت ربات
        status_sections.append(f"🔹 **وضعیت ربات:** `فعال ✅`\n")
        
        # ارسال پیام نهایی
        bot.send_message(message.chat.id, "".join(status_sections), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"خطای کلی در دریافت وضعیت سرور: {e}")
        bot.send_message(message.chat.id, f"⚠ خطا در دریافت وضعیت سرور: {str(e)}")

# مدیریت کلیدهای میانبر (Callback Query)
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    try:
        # پاسخ سریع به کالبک برای جلوگیری از خطای ساعت شنی
        bot.answer_callback_query(call.id)
        
        # وضعیت سرور
        if call.data == "server_status":
            handle_status(call.message)
        
        # راهنمای دانلود
        elif call.data == "download_help":
            help_text = (
                "🎬 <b>راهنمای دانلود ویدیو</b>\n\n"
                "<b>🔹 انواع لینک‌های پشتیبانی شده:</b>\n"
                "• یوتیوب: لینک‌های معمولی، کوتاه و پلی‌لیست\n"
                "• اینستاگرام: پست‌ها، IGTV، ریلز\n\n"
                "<b>🔸 نکات مهم:</b>\n"
                "• <b>کیفیت:</b> برای صرفه‌جویی در مصرف داده و سرعت بیشتر، از کیفیت‌های پایین‌تر استفاده کنید\n"
                "• <b>زمان دانلود:</b> بسته به حجم ویدیو و کیفیت انتخابی، ممکن است تا 2 دقیقه زمان ببرد\n"
                "• <b>خطاها:</b> در صورت خطا، مجدداً با کیفیت پایین‌تر امتحان کنید\n\n"
                "<b>🔄 روش استفاده:</b>\n"
                "1. کیفیت موردنظر را انتخاب کنید\n"
                "2. لینک را کپی و برای ربات ارسال کنید\n"
                "3. منتظر دانلود و ارسال ویدیو باشید"
            )
            
            bot.send_message(
                call.message.chat.id,
                help_text,
                parse_mode="HTML"
            )
        
        # انتخاب کیفیت ویدیو
        elif call.data == "select_quality":
            quality_text = (
                "📊 <b>انتخاب کیفیت ویدیو</b>\n\n"
                "فعلاً همه ویدیوها با کیفیت استاندارد (360p) دانلود می‌شوند.\n"
                "در نسخه‌های آینده، امکان انتخاب کیفیت اضافه خواهد شد."
            )
            
            bot.send_message(
                call.message.chat.id,
                quality_text,
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error(f"خطا در پردازش callback: {e}", exc_info=True)
        bot.send_message(call.message.chat.id, f"⚠️ خطا در پردازش عملیات: {str(e)}")

# پاسخ به همه پیام‌ها
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """پاسخ به همه پیام‌ها"""
    url = message.text.strip()
    
    if is_youtube_url(url):
        # دانلود از یوتیوب
        threading.Thread(target=process_youtube_url, args=(message, url)).start()
    
    elif is_instagram_url(url):
        # دانلود از اینستاگرام
        threading.Thread(target=process_instagram_url, args=(message, url)).start()
    
    else:
        bot.reply_to(message, "❌ لطفاً یک لینک معتبر از یوتیوب یا اینستاگرام ارسال کنید.")

# راه‌اندازی وب‌هوک فلسک (اگر نیاز باشد)
def setup_flask_webhook(webhook_url):
    if not USE_FLASK:
        return None
    
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return 'ربات تلگرام در حال اجراست!'
    
    @app.route('/status')
    def status():
        return 'ربات تلگرام فعال است.'
    
    @app.route(f'/{TOKEN}', methods=['POST'])
    def webhook():
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
        return 'ok', 200
    
    bot.remove_webhook()
    bot.set_webhook(url=f"{webhook_url}/{TOKEN}")
    
    return app

# تابع اصلی
def main():
    """راه‌اندازی ربات تلگرام"""
    try:
        # پاکسازی وب‌هوک‌های قبلی
        bot.remove_webhook()
        
        # شروع پولینگ
        logger.info("ربات تلگرام با موفقیت راه‌اندازی شد!")
        bot.polling(none_stop=True)
    
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()