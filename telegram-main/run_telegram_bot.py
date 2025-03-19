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

# ثبت زمان راه‌اندازی ربات برای محاسبه مدت زمان اجرا
START_TIME = time.time()

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

# دانلود ویدیو از یوتیوب - نسخه پیشرفته
def process_youtube_url(message, url):
    """پردازش لینک یوتیوب و دانلود آن با سیستم پیشرفته مدیریت خطا"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    quality = "360p"  # کیفیت پیش‌فرض
    
    # ایجاد شناسه منحصر به فرد برای این دانلود
    download_id = f"yt_{int(time.time())}_{user_id}"
    
    # نمایش پیام در حال دانلود
    processing_msg = bot.reply_to(message, "🎬 لینک یوتیوب تشخیص داده شد. در حال تحلیل اطلاعات ویدیو...")
    
    # ایجاد کیبورد اینلاین برای لغو دانلود
    cancel_markup = types.InlineKeyboardMarkup()
    cancel_btn = types.InlineKeyboardButton("❌ لغو دانلود", callback_data=f"cancel_{download_id}")
    cancel_markup.add(cancel_btn)
    
    # بروزرسانی پیام با دکمه لغو
    bot.edit_message_text(
        "🎬 لینک یوتیوب تشخیص داده شد. در حال تحلیل اطلاعات ویدیو...",
        chat_id,
        processing_msg.message_id,
        reply_markup=cancel_markup
    )
    
    # ذخیره اطلاعات دانلود در حافظه برای دسترسی از طریق callback
    if not hasattr(bot, 'downloads'):
        bot.downloads = {}
    
    bot.downloads[download_id] = {
        'status': 'analyzing',
        'message_id': processing_msg.message_id,
        'chat_id': chat_id,
        'url': url,
        'quality': quality,
        'user_id': user_id,
        'start_time': time.time(),
        'process': None,
        'file_path': None
    }
    
    try:
        # ابتدا اطلاعات ویدیو را بدون دانلود دریافت می‌کنیم
        ydl_opts_info = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': True,
            'skip_download': True,  # فقط اطلاعات را دریافت می‌کنیم
            'noprogress': True
        }
        
        try:
            with YoutubeDL(ydl_opts_info) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                
                if info_dict is None:
                    bot.edit_message_text(
                        "❌ خطا در دریافت اطلاعات ویدیو. این لینک معتبر نیست یا دسترسی به آن محدود شده است.",
                        chat_id,
                        processing_msg.message_id,
                        reply_markup=None
                    )
                    return
                
                # اطلاعات ویدیو
                title = info_dict.get('title', 'ویدیوی دانلود شده')
                duration = info_dict.get('duration')
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "نامشخص"
                thumbnail = info_dict.get('thumbnail')
                
                # نمایش اطلاعات ویدیو
                info_text = (
                    f"📊 <b>اطلاعات ویدیو:</b>\n\n"
                    f"🎬 <b>عنوان:</b> {title}\n"
                    f"⏱ <b>مدت زمان:</b> {duration_str}\n\n"
                    f"🔄 <b>در حال دانلود ویدیو با کیفیت {quality}...</b>"
                )
                
                # کیبورد با افزودن دکمه کیفیت‌ها
                quality_markup = types.InlineKeyboardMarkup(row_width=2)
                cancel_btn = types.InlineKeyboardButton("❌ لغو دانلود", callback_data=f"cancel_{download_id}")
                quality_markup.add(cancel_btn)
                
                # بروزرسانی پیام
                bot.edit_message_text(
                    info_text,
                    chat_id,
                    processing_msg.message_id,
                    parse_mode="HTML",
                    reply_markup=quality_markup
                )
        except Exception as e:
            logger.error(f"خطا در تحلیل اطلاعات ویدیو: {e}", exc_info=True)
            bot.edit_message_text(
                f"⚠️ خطا در تحلیل اطلاعات ویدیو: {str(e)}",
                chat_id,
                processing_msg.message_id
            )
            return
        
        # ذخیره وضعیت جدید
        bot.downloads[download_id]['status'] = 'downloading'
        bot.downloads[download_id]['title'] = title
        
        # مسیر فایل
        safe_title = ''.join(c for c in title if c.isalnum() or c in (' ', '.', '-', '_')).strip()
        if not safe_title:
            safe_title = 'video'
        filename = f"{safe_title}_{download_id}"
        
        # تنظیمات پیشرفته yt-dlp
        ydl_opts = {
            'format': 'best[height<=360]/bestvideo[height<=360]+bestaudio/best',
            'outtmpl': f'{TEMP_DOWNLOAD_DIR}/{filename}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': True,
            'noprogress': True,
            'retries': 5,  # تعداد تلاش‌های مجدد
            'fragment_retries': 5,  # تعداد تلاش‌های مجدد برای هر قطعه
            'skip_unavailable_fragments': True,  # رد کردن قطعات غیرقابل دسترس
            'keepvideo': False,  # پاک کردن فایل‌های موقت
            # در صورت نیاز می‌توان از کوکی برای ویدیوهای محدود شده استفاده کرد
            # 'cookiefile': 'cookies.txt',
        }
            
        # دانلود ویدیو در یک تابع جداگانه
        def do_download():
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    # دریافت اطلاعات و دانلود ویدیو
                    info = ydl.extract_info(url, download=True)
                    
                    if info is None:
                        bot.edit_message_text(
                            "❌ خطا در دانلود ویدیو. لطفاً از لینک دیگری استفاده کنید.",
                            chat_id,
                            processing_msg.message_id,
                            reply_markup=None
                        )
                        return
                    
                    # مسیر فایل دانلود شده
                    video_path = ydl.prepare_filename(info)
                    
                    # بررسی وجود فایل
                    if not os.path.exists(video_path):
                        # بررسی پسوندهای مختلف فایل
                        for ext in ['mp4', 'webm', 'mkv', 'mp3', 'm4a']:
                            possible_path = os.path.splitext(video_path)[0] + f'.{ext}'
                            if os.path.exists(possible_path):
                                video_path = possible_path
                                break
                    
                    # بروزرسانی وضعیت دانلود
                    if download_id in bot.downloads:
                        bot.downloads[download_id]['status'] = 'completed'
                        bot.downloads[download_id]['file_path'] = video_path
                    
                    # ارسال ویدیو
                    if os.path.exists(video_path):
                        # اندازه فایل
                        file_size = os.path.getsize(video_path)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        # بررسی محدودیت سایز فایل تلگرام (50MB)
                        if file_size_mb > 50:
                            # ویدیو بزرگتر از حد مجاز است، نیاز به فشرده‌سازی یا تقسیم دارد
                            bot.edit_message_text(
                                f"⚠️ حجم فایل ({file_size_mb:.1f} MB) بیشتر از حد مجاز تلگرام است.\n"
                                f"در حال آماده‌سازی فایل با حجم کمتر...",
                                chat_id,
                                processing_msg.message_id,
                                reply_markup=None
                            )
                            
                            # تلاش برای دانلود با کیفیت پایین‌تر
                            lower_quality_opts = ydl_opts.copy()
                            lower_quality_opts['format'] = 'best[height<=240]/bestvideo[height<=240]+bestaudio/worst'
                            lower_quality_path = f'{TEMP_DOWNLOAD_DIR}/{filename}_low.%(ext)s'
                            lower_quality_opts['outtmpl'] = lower_quality_path
                            
                            try:
                                with YoutubeDL(lower_quality_opts) as ydl_low:
                                    info_low = ydl_low.extract_info(url, download=True)
                                    video_path_low = ydl_low.prepare_filename(info_low)
                                    
                                    # بررسی پسوندهای مختلف
                                    if not os.path.exists(video_path_low):
                                        for ext in ['mp4', 'webm', 'mkv']:
                                            possible_path = os.path.splitext(video_path_low)[0] + f'.{ext}'
                                            if os.path.exists(possible_path):
                                                video_path_low = possible_path
                                                break
                                    
                                    # استفاده از فایل جدید
                                    if os.path.exists(video_path_low) and os.path.getsize(video_path_low) <= 50 * 1024 * 1024:
                                        video_path = video_path_low
                                    else:
                                        # همچنان بزرگتر از حد مجاز است
                                        bot.send_message(
                                            chat_id,
                                            f"⚠️ متأسفانه حجم فایل ویدیو حتی با کیفیت پایین‌تر نیز بیشتر از حد مجاز تلگرام است. "
                                            f"لطفاً از یک لینک دیگر استفاده کنید."
                                        )
                                        return
                                        
                            except Exception as e:
                                logger.error(f"خطا در دانلود با کیفیت پایین‌تر: {e}", exc_info=True)
                                # ادامه با فایل اصلی و تلاش برای ارسال بخشی از آن
                        
                        try:
                            # ارسال پیام آماده‌سازی نهایی
                            bot.edit_message_text(
                                "✅ دانلود با موفقیت انجام شد. در حال ارسال ویدیو...",
                                chat_id,
                                processing_msg.message_id,
                                reply_markup=None
                            )
                            
                            # تلاش برای ارسال ویدیو
                            with open(video_path, 'rb') as video_file:
                                # اطلاعات توضیحی ویدیو
                                caption = (
                                    f"🎬 <b>{title}</b>\n\n"
                                    f"⏱ مدت زمان: {duration_str}\n"
                                    f"📊 کیفیت: {quality}\n"
                                    f"📦 حجم: {file_size_mb:.1f} MB\n\n"
                                    f"🔗 <a href='{url}'>لینک اصلی</a>"
                                )
                                
                                sent_msg = bot.send_video(
                                    chat_id,
                                    video_file,
                                    caption=caption,
                                    parse_mode="HTML",
                                    supports_streaming=True,
                                    reply_to_message_id=message.message_id
                                )
                                
                                # حذف پیام "در حال دانلود"
                                bot.delete_message(chat_id, processing_msg.message_id)
                        except Exception as video_send_error:
                            logger.error(f"خطا در ارسال ویدیو: {video_send_error}", exc_info=True)
                            
                            # تلاش برای ارسال به صورت فایل اگر ارسال ویدیو با مشکل مواجه شد
                            try:
                                with open(video_path, 'rb') as file:
                                    bot.send_document(
                                        chat_id,
                                        file,
                                        caption=f"🎬 {title}\n\n🔗 {url}",
                                        reply_to_message_id=message.message_id
                                    )
                                    
                                    # حذف پیام "در حال دانلود"
                                    bot.delete_message(chat_id, processing_msg.message_id)
                            except Exception as file_send_error:
                                logger.error(f"خطا در ارسال فایل: {file_send_error}", exc_info=True)
                                bot.edit_message_text(
                                    f"⚠️ ویدیو دانلود شد اما امکان ارسال آن وجود ندارد. احتمالا حجم فایل بیش از حد مجاز است.\n\n"
                                    f"🎬 عنوان: {title}\n"
                                    f"📦 حجم: {file_size_mb:.1f} MB",
                                    chat_id,
                                    processing_msg.message_id,
                                    reply_markup=None
                                )
                        
                        # پاکسازی فایل
                        try:
                            os.remove(video_path)
                            # پاک کردن فایل کیفیت پایین اگر وجود داشته باشد
                            lower_quality_path = f'{TEMP_DOWNLOAD_DIR}/{filename}_low.mp4'
                            if os.path.exists(lower_quality_path):
                                os.remove(lower_quality_path)
                        except Exception as cleanup_error:
                            logger.error(f"خطا در پاکسازی فایل: {cleanup_error}", exc_info=True)
                    else:
                        bot.edit_message_text(
                            "❌ خطا در دانلود ویدیو. فایل دانلود شده یافت نشد.",
                            chat_id,
                            processing_msg.message_id,
                            reply_markup=None
                        )
            except Exception as e:
                if download_id in bot.downloads and bot.downloads[download_id]['status'] != 'cancelled':
                    bot.downloads[download_id]['status'] = 'failed'
                    logger.error(f"خطا در دانلود یوتیوب: {e}", exc_info=True)
                    
                    error_msg = str(e)
                    # ترجمه برخی خطاهای رایج به فارسی
                    if "Video unavailable" in error_msg:
                        error_msg = "ویدیو در دسترس نیست"
                    elif "Private video" in error_msg:
                        error_msg = "این ویدیو خصوصی است"
                    elif "sign in" in error_msg.lower():
                        error_msg = "این ویدیو نیاز به ورود به حساب کاربری دارد"
                    
                    bot.edit_message_text(
                        f"⚠️ خطا در دانلود ویدیو: {error_msg}",
                        chat_id,
                        processing_msg.message_id,
                        reply_markup=None
                    )
        
        # اجرای دانلود در یک ترد جداگانه
        download_thread = threading.Thread(target=do_download)
        download_thread.daemon = True
        download_thread.start()
        
        # ذخیره اطلاعات ترد
        bot.downloads[download_id]['process'] = download_thread
            
    except Exception as e:
        logger.error(f"خطا در تنظیم دانلود یوتیوب: {e}", exc_info=True)
        bot.edit_message_text(
            f"⚠️ خطا در دانلود ویدیو: {str(e)}",
            chat_id,
            processing_msg.message_id,
            reply_markup=None
        )

# دانلود پست اینستاگرام - نسخه پیشرفته
def process_instagram_url(message, url):
    """پردازش لینک اینستاگرام و دانلود آن با سیستم پیشرفته مدیریت خطا"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # ایجاد شناسه منحصر به فرد برای این دانلود
    download_id = f"ig_{int(time.time())}_{user_id}"
    
    # پاکسازی URL
    url = url.split("?")[0]  # حذف پارامترهای URL
    if url.endswith("/"):
        url = url[:-1]  # حذف "/" انتهایی
    
    # نمایش پیام در حال دانلود
    processing_msg = bot.reply_to(message, "📸 لینک اینستاگرام تشخیص داده شد. در حال تحلیل پست...")
    
    # ایجاد کیبورد اینلاین برای لغو دانلود
    cancel_markup = types.InlineKeyboardMarkup()
    cancel_btn = types.InlineKeyboardButton("❌ لغو دانلود", callback_data=f"cancel_{download_id}")
    cancel_markup.add(cancel_btn)
    
    # بروزرسانی پیام با دکمه لغو
    bot.edit_message_text(
        "📸 لینک اینستاگرام تشخیص داده شد. در حال تحلیل پست...",
        chat_id,
        processing_msg.message_id,
        reply_markup=cancel_markup
    )
    
    # ذخیره اطلاعات دانلود در حافظه برای دسترسی از طریق callback
    if not hasattr(bot, 'downloads'):
        bot.downloads = {}
    
    bot.downloads[download_id] = {
        'status': 'analyzing',
        'message_id': processing_msg.message_id,
        'chat_id': chat_id,
        'url': url,
        'user_id': user_id,
        'start_time': time.time(),
        'process': None,
        'file_paths': []
    }
    
    try:
        # ایجاد پوشه موقت برای ذخیره فایل‌ها
        url_hash = url.replace("/", "_").replace(":", "_")
        temp_dir = f"{TEMP_DOWNLOAD_DIR}/insta_{url_hash}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # ابتدا اطلاعات پست را بدون دانلود دریافت می‌کنیم
        ydl_opts_info = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'skip_download': True,  # فقط اطلاعات را دریافت می‌کنیم
            'noprogress': True
        }
        
        try:
            with YoutubeDL(ydl_opts_info) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                
                if info_dict is None:
                    bot.edit_message_text(
                        "❌ خطا در دریافت اطلاعات پست. این لینک معتبر نیست یا دسترسی به آن محدود شده است.",
                        chat_id,
                        processing_msg.message_id,
                        reply_markup=None
                    )
                    return
                
                # اطلاعات پست
                title = info_dict.get('title', 'پست اینستاگرام')
                uploader = info_dict.get('uploader', 'نامشخص')
                is_collection = info_dict.get('playlist_count', 1) > 1
                media_count = info_dict.get('playlist_count', 1)
                
                # نمایش اطلاعات پست
                info_text = (
                    f"📊 <b>اطلاعات پست اینستاگرام:</b>\n\n"
                    f"👤 <b>کاربر:</b> {uploader}\n"
                    f"{'🖼 <b>تعداد رسانه‌ها:</b> ' + str(media_count) if is_collection else ''}\n\n"
                    f"🔄 <b>در حال دانلود رسانه‌ها...</b>"
                )
                
                # بروزرسانی پیام
                bot.edit_message_text(
                    info_text,
                    chat_id,
                    processing_msg.message_id,
                    parse_mode="HTML",
                    reply_markup=cancel_markup
                )
        except Exception as e:
            logger.error(f"خطا در تحلیل اطلاعات پست اینستاگرام: {e}", exc_info=True)
            # ادامه دادن به دانلود، زیرا ممکن است هنوز دانلود موفق باشد
        
        # ذخیره وضعیت جدید
        bot.downloads[download_id]['status'] = 'downloading'
        
        # دانلود پست در یک تابع جداگانه
        def do_download():
            try:
                # استفاده از yt-dlp برای دانلود پست اینستاگرام
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                    'ignoreerrors': True,
                    'noplaylist': False,  # دانلود همه رسانه‌ها در مجموعه
                    'noprogress': True,
                    'retries': 5,  # تعداد تلاش‌های مجدد
                    'fragment_retries': 5,  # تعداد تلاش‌های مجدد برای هر قطعه
                    'skip_unavailable_fragments': True,  # رد کردن قطعات غیرقابل دسترس
                }
                
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if info is None:
                        bot.edit_message_text(
                            "❌ خطا در دانلود پست اینستاگرام. لطفاً از لینک دیگری استفاده کنید.",
                            chat_id,
                            processing_msg.message_id,
                            reply_markup=None
                        )
                        return
                    
                    # بررسی وضعیت دانلود
                    if download_id in bot.downloads and bot.downloads[download_id]['status'] == 'cancelled':
                        # دانلود لغو شده است
                        try:
                            # پاکسازی فایل‌های موقت
                            for file in os.listdir(temp_dir):
                                os.remove(os.path.join(temp_dir, file))
                            os.rmdir(temp_dir)
                        except Exception as cleanup_error:
                            logger.error(f"خطا در پاکسازی: {cleanup_error}", exc_info=True)
                        return
                    
                    # جستجوی فایل‌های دانلود شده
                    media_files = []
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        if os.path.isfile(file_path) and not file.endswith('.txt'):
                            media_files.append(file_path)
                            # ذخیره مسیر فایل‌ها برای استفاده در صورت لغو
                            bot.downloads[download_id]['file_paths'].append(file_path)
                    
                    if not media_files:
                        bot.edit_message_text(
                            "❌ فایل رسانه‌ای در پست اینستاگرام یافت نشد.",
                            chat_id,
                            processing_msg.message_id,
                            reply_markup=None
                        )
                        return
                    
                    # بروزرسانی وضعیت دانلود
                    bot.downloads[download_id]['status'] = 'sending'
                    
                    # ارسال فایل‌ها
                    bot.edit_message_text(
                        f"✅ دانلود با موفقیت انجام شد. در حال ارسال {len(media_files)} فایل...",
                        chat_id,
                        processing_msg.message_id,
                        reply_markup=None
                    )
                    
                    media_group = []
                    sent_count = 0
                    
                    # جداسازی فایل‌ها به ویدیو و تصاویر
                    videos = [f for f in media_files if f.endswith(('.mp4', '.mov'))]
                    images = [f for f in media_files if f.endswith(('.jpg', '.jpeg', '.png'))]
                    
                    # اگر فقط یک رسانه وجود دارد، با کپشن کامل ارسال می‌کنیم
                    if len(media_files) == 1:
                        file_path = media_files[0]
                        caption = f"📸 <b>پست اینستاگرام</b>\n\n"
                        if 'title' in locals():
                            caption += f"✏️ <b>{title}</b>\n\n"
                        if 'uploader' in locals():
                            caption += f"👤 کاربر: {uploader}\n"
                        caption += f"🔗 <a href='{url}'>لینک اصلی</a>"
                        
                        try:
                            if file_path.endswith(('.mp4', '.mov')):
                                with open(file_path, 'rb') as video_file:
                                    bot.send_video(
                                        chat_id,
                                        video_file,
                                        caption=caption,
                                        parse_mode="HTML",
                                        supports_streaming=True
                                    )
                            elif file_path.endswith(('.jpg', '.jpeg', '.png')):
                                with open(file_path, 'rb') as photo_file:
                                    bot.send_photo(
                                        chat_id,
                                        photo_file,
                                        caption=caption,
                                        parse_mode="HTML"
                                    )
                            sent_count += 1
                        except Exception as send_error:
                            logger.error(f"خطا در ارسال فایل: {send_error}", exc_info=True)
                    else:
                        # اگر بیش از 10 رسانه وجود دارد، پیام هشدار نمایش دهیم
                        if len(media_files) > 10:
                            bot.send_message(
                                chat_id,
                                f"⚠️ این پست حاوی {len(media_files)} رسانه است. تنها 10 مورد اول ارسال خواهد شد."
                            )
                        
                        # ارسال ویدیوها و تصاویر به صورت جداگانه (زیرا نمی‌توان آنها را در یک گروه ارسال کرد)
                        
                        # ارسال ویدیوها
                        for file_path in videos[:10]:  # محدودیت 10 فایل
                            try:
                                with open(file_path, 'rb') as video_file:
                                    caption = f"📸 پست اینستاگرام ({sent_count+1}/{min(len(media_files), 10)})\n\n🔗 {url}"
                                    bot.send_video(
                                        chat_id,
                                        video_file,
                                        caption=caption,
                                        supports_streaming=True
                                    )
                                sent_count += 1
                            except Exception as send_error:
                                logger.error(f"خطا در ارسال ویدیو: {send_error}", exc_info=True)
                                continue
                        
                        # ارسال تصاویر (حداکثر 10 تصویر در یک گروه رسانه‌ای)
                        if images:
                            try:
                                # تقسیم تصاویر به گروه‌های 10 تایی
                                for i in range(0, min(len(images), 10), 10):
                                    batch = images[i:i+10]
                                    media = []
                                    
                                    for idx, file_path in enumerate(batch):
                                        # برای اولین تصویر کپشن اضافه می‌کنیم
                                        caption = ""
                                        if idx == 0:
                                            caption = f"📸 پست اینستاگرام\n\n🔗 {url}"
                                        
                                        with open(file_path, 'rb') as f:
                                            media.append(
                                                types.InputMediaPhoto(
                                                    f.read(),
                                                    caption=caption
                                                )
                                            )
                                    
                                    if media:
                                        bot.send_media_group(chat_id, media)
                                        sent_count += len(media)
                            except Exception as media_error:
                                logger.error(f"خطا در ارسال گروه رسانه‌ای: {media_error}", exc_info=True)
                                
                                # در صورت خطا، سعی می‌کنیم تصاویر را تک به تک ارسال کنیم
                                for file_path in images[:10 - sent_count]:
                                    try:
                                        with open(file_path, 'rb') as photo_file:
                                            caption = f"📸 پست اینستاگرام ({sent_count+1}/{min(len(media_files), 10)})\n\n🔗 {url}"
                                            bot.send_photo(
                                                chat_id,
                                                photo_file,
                                                caption=caption
                                            )
                                        sent_count += 1
                                    except Exception as send_error:
                                        logger.error(f"خطا در ارسال تصویر: {send_error}", exc_info=True)
                                        continue
                    
                    # حذف پیام "در حال دانلود"
                    try:
                        bot.delete_message(chat_id, processing_msg.message_id)
                    except Exception as delete_error:
                        logger.error(f"خطا در حذف پیام: {delete_error}", exc_info=True)
                    
                    # پاکسازی فایل‌های موقت
                    try:
                        for file in os.listdir(temp_dir):
                            os.remove(os.path.join(temp_dir, file))
                        os.rmdir(temp_dir)
                    except Exception as cleanup_error:
                        logger.error(f"خطا در پاکسازی نهایی: {cleanup_error}", exc_info=True)
                    
                    # بروزرسانی وضعیت دانلود
                    bot.downloads[download_id]['status'] = 'completed'
                    
            except Exception as e:
                if download_id in bot.downloads and bot.downloads[download_id]['status'] != 'cancelled':
                    bot.downloads[download_id]['status'] = 'failed'
                    
                    error_msg = str(e)
                    # ترجمه برخی خطاهای رایج به فارسی
                    if "Private" in error_msg:
                        error_msg = "این پست خصوصی است و قابل دسترسی نیست"
                    elif "sign in" in error_msg.lower():
                        error_msg = "این پست نیاز به ورود به حساب کاربری دارد"
                    elif "not found" in error_msg.lower():
                        error_msg = "پست مورد نظر یافت نشد"
                    
                    logger.error(f"خطا در دانلود اینستاگرام: {e}", exc_info=True)
                    bot.edit_message_text(
                        f"⚠️ خطا در دانلود پست اینستاگرام: {error_msg}",
                        chat_id,
                        processing_msg.message_id,
                        reply_markup=None
                    )
        
        # اجرای دانلود در یک ترد جداگانه
        download_thread = threading.Thread(target=do_download)
        download_thread.daemon = True
        download_thread.start()
        
        # ذخیره اطلاعات ترد
        bot.downloads[download_id]['process'] = download_thread
        
    except Exception as e:
        logger.error(f"خطا در تنظیم دانلود اینستاگرام: {e}", exc_info=True)
        bot.edit_message_text(
            f"⚠️ خطا در دانلود پست اینستاگرام: {str(e)}",
            chat_id,
            processing_msg.message_id,
            reply_markup=None
        )

# دستور /start
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """پاسخ به دستور /start و /help با رابط کاربری پیشرفته"""
    # ایجاد کیبورد اینلاین با دکمه‌های مختلف و طراحی بهتر
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # دکمه‌های اصلی
    help_btn = types.InlineKeyboardButton("📚 راهنمای استفاده", callback_data="download_help")
    quality_btn = types.InlineKeyboardButton("📊 انتخاب کیفیت", callback_data="select_quality")
    status_btn = types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="server_status")
    
    # دکمه‌های ویژگی‌های جدید
    youtube_btn = types.InlineKeyboardButton("🎬 دانلود یوتیوب", callback_data="youtube_info")
    instagram_btn = types.InlineKeyboardButton("📸 دانلود اینستاگرام", callback_data="instagram_info")
    hashtag_btn = types.InlineKeyboardButton("🔍 جستجوی هشتگ", callback_data="hashtag_search")
    
    # دکمه مشاوره و پرسش و پاسخ
    questions_btn = types.InlineKeyboardButton("❓ پرسش و پاسخ", callback_data="faq")
    
    # اضافه کردن دکمه‌ها به کیبورد
    markup.add(youtube_btn, instagram_btn)
    markup.add(quality_btn, hashtag_btn)
    markup.add(help_btn, status_btn)
    markup.add(questions_btn)
    
    # متن پیام خوش‌آمدگویی با طراحی بهتر
    welcome_text = (
        f"👋 <b>سلام {message.from_user.first_name}!</b>\n\n"
        "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
        "🔸 <b>قابلیت‌های ربات:</b>\n"
        "• <b>دانلود ویدیو از یوتیوب</b> با کیفیت‌های مختلف\n"
        "• <b>دانلود پست‌های اینستاگرام</b> (ویدیو و تصاویر)\n"
        "• <b>جستجوی هشتگ</b> در کانال‌های تلگرام\n"
        "• <b>امکان انتخاب کیفیت ویدیو</b> برای صرفه‌جویی در حجم\n"
        "• <b>پشتیبانی از زبان فارسی</b> و رابط کاربری آسان\n\n"
        "🔹 <b>روش استفاده:</b>\n"
        "کافیست لینک ویدیوی مورد نظر خود را از یوتیوب یا اینستاگرام ارسال کنید.\n\n"
        "📌 <b>از منوی شیشه‌ای زیر برای مدیریت ربات استفاده کنید:</b>"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=markup
    )

# دستور /status
@bot.message_handler(commands=['status'])
def handle_status(message):
    """نمایش وضعیت سرور با اطلاعات جامع‌تر"""
    try:
        import platform
        import datetime
        
        # تبدیل زمان به فرمت قابل خواندن
        def format_uptime(seconds):
            days, remainder = divmod(seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            result = ""
            if days > 0:
                result += f"{int(days)} روز "
            if hours > 0 or days > 0:
                result += f"{int(hours)} ساعت "
            if minutes > 0 or hours > 0 or days > 0:
                result += f"{int(minutes)} دقیقه "
            result += f"{int(seconds)} ثانیه"
            
            return result
        
        # دریافت وضعیت سرور - بخش اول: اطلاعات پایه
        system_info = {
            'hostname': platform.node(),
            'system': f"{platform.system()} {platform.release()}",
            'python_version': platform.python_version(),
            'bot_version': "1.5.0",  # نسخه ربات
            'uptime': time.time() - START_TIME
        }
        
        # جمع‌آوری اطلاعات سیستم به فرمت HTML
        status_message = (
            f"🖥️ <b>وضعیت سرور و ربات</b>\n\n"
            f"🔹 <b>سیستم:</b> {system_info['system']}\n"
            f"🔸 <b>نسخه پایتون:</b> {system_info['python_version']}\n"
            f"🤖 <b>نسخه ربات:</b> {system_info['bot_version']}\n\n"
            f"⏱️ <b>زمان اجرا:</b> {format_uptime(system_info['uptime'])}\n\n"
        )
        
        # CPU و حافظه
        if psutil:
            try:
                # CPU
                cpu_usage = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                status_message += (
                    f"📊 <b>CPU:</b>\n"
                    f"  استفاده: {cpu_usage}%\n"
                    f"  تعداد هسته: {cpu_count}\n\n"
                )
                
                # حافظه
                ram = psutil.virtual_memory()
                status_message += (
                    f"📊 <b>حافظه:</b>\n"
                    f"  کل: {ram.total / (1024**3):.2f} GB\n"
                    f"  استفاده: {ram.used / (1024**3):.2f} GB ({ram.percent}%)\n"
                    f"  آزاد: {ram.available / (1024**3):.2f} GB\n\n"
                )
                
                # دیسک
                disk = psutil.disk_usage('/')
                status_message += (
                    f"📊 <b>دیسک:</b>\n"
                    f"  کل: {disk.total / (1024**3):.2f} GB\n"
                    f"  استفاده: {disk.used / (1024**3):.2f} GB ({disk.percent}%)\n"
                    f"  آزاد: {disk.free / (1024**3):.2f} GB\n\n"
                )
                
                # اطلاعات شبکه
                try:
                    net_io = psutil.net_io_counters()
                    status_message += (
                        f"🌐 <b>شبکه:</b>\n"
                        f"  دریافت: {net_io.bytes_recv / (1024**2):.2f} MB\n"
                        f"  ارسال: {net_io.bytes_sent / (1024**2):.2f} MB\n\n"
                    )
                except Exception as net_error:
                    logger.error(f"خطا در دریافت اطلاعات شبکه: {net_error}")
                
                # اطلاعات پردازش ربات
                try:
                    current_process = psutil.Process()
                    status_message += (
                        f"🤖 <b>پردازش ربات:</b>\n"
                        f"  CPU: {current_process.cpu_percent(interval=0.1):.2f}%\n"
                        f"  حافظه: {current_process.memory_info().rss / (1024**2):.2f} MB\n"
                        f"  ترد‌ها: {current_process.num_threads()}\n\n"
                    )
                except Exception as proc_error:
                    logger.error(f"خطا در دریافت اطلاعات پردازش: {proc_error}")
            
            except Exception as resource_error:
                logger.error(f"خطا در دریافت اطلاعات منابع: {resource_error}")
                status_message += "⚠️ <b>خطا در دریافت اطلاعات منابع سیستم</b>\n\n"
        else:
            status_message += "⚠️ <b>اطلاعات منابع سیستم در دسترس نیست (psutil نصب نشده)</b>\n\n"
        
        # آمار ربات
        try:
            # آماری که از ربات جمع‌آوری می‌کنیم
            if hasattr(bot, 'downloads'):
                active_downloads = len([d for d in bot.downloads.values() if d['status'] in ('analyzing', 'downloading', 'sending')])
                total_downloads = len(bot.downloads)
                youtube_downloads = len([d for d in bot.downloads.values() if d['url'] and 'youtube' in d['url']])
                instagram_downloads = len([d for d in bot.downloads.values() if d['url'] and 'instagram' in d['url']])
                
                status_message += (
                    f"📈 <b>آمار ربات:</b>\n"
                    f"  دانلودهای فعال: {active_downloads}\n"
                    f"  کل دانلودها: {total_downloads}\n"
                )
                
                if youtube_downloads > 0 or instagram_downloads > 0:
                    status_message += (
                        f"  دانلودهای یوتیوب: {youtube_downloads}\n"
                        f"  دانلودهای اینستاگرام: {instagram_downloads}\n\n"
                    )
            else:
                status_message += (
                    f"📈 <b>آمار ربات:</b>\n"
                    f"  دانلودی انجام نشده است\n\n"
                )
        except Exception as bot_stats_error:
            logger.error(f"خطا در دریافت آمار ربات: {bot_stats_error}")
        
        # زمان سرور
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_message += f"🕒 <b>زمان سرور:</b> {current_time}\n\n"
        
        # وضعیت کلی
        status_message += f"🟢 <b>وضعیت کلی:</b> فعال و سالم"
        
        # ایجاد دکمه به‌روزرسانی و دکمه‌های عملیات
        markup = types.InlineKeyboardMarkup(row_width=2)
        refresh_btn = types.InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="server_status")
        help_btn = types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
        quality_btn = types.InlineKeyboardButton("📊 انتخاب کیفیت", callback_data="select_quality")
        
        markup.add(refresh_btn)
        markup.add(help_btn, quality_btn)
        
        # ارسال پیام
        bot.send_message(
            message.chat.id,
            status_message,
            parse_mode="HTML",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"خطای کلی در دریافت وضعیت سرور: {e}", exc_info=True)
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
            
            # ایجاد دکمه‌های بازگشت به منوی اصلی
            markup = types.InlineKeyboardMarkup(row_width=2)
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
            youtube_btn = types.InlineKeyboardButton("🎬 دانلود یوتیوب", callback_data="youtube_info")
            markup.add(youtube_btn, back_btn)
            
            bot.send_message(
                call.message.chat.id,
                help_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        
        # اطلاعات دانلود یوتیوب
        elif call.data == "youtube_info":
            youtube_text = (
                "🎬 <b>دانلود از یوتیوب</b>\n\n"
                "<b>🔹 انواع لینک‌های پشتیبانی شده:</b>\n"
                "• لینک‌های معمولی ویدیو یوتیوب\n"
                "• لینک‌های کوتاه (youtu.be)\n"
                "• لینک‌های shorts\n\n"
                "<b>🔸 نکات مهم:</b>\n"
                "• در حال حاضر کیفیت پیش‌فرض 360p است\n"
                "• ربات تلاش می‌کند بهترین نسخه ممکن از ویدیو را با توجه به محدودیت‌های تلگرام دانلود کند\n"
                "• در صورت بیشتر بودن حجم ویدیو از حد مجاز، کیفیت پایین‌تر انتخاب می‌شود\n\n"
                "<b>🔄 روش استفاده:</b>\n"
                "لینک یوتیوب را کپی کرده و به ربات ارسال کنید. ربات به صورت خودکار لینک را تشخیص داده و پردازش می‌کند."
            )
            
            # مثال لینک یوتیوب
            example_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            
            # ایجاد دکمه‌های میانبر
            markup = types.InlineKeyboardMarkup(row_width=2)
            try_btn = types.InlineKeyboardButton("🔄 امتحان با مثال", callback_data="try_example_youtube")
            quality_btn = types.InlineKeyboardButton("📊 انتخاب کیفیت", callback_data="select_quality")
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
            
            markup.add(try_btn, quality_btn)
            markup.add(back_btn)
            
            bot.send_message(
                call.message.chat.id,
                youtube_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        
        # اطلاعات دانلود اینستاگرام
        elif call.data == "instagram_info":
            instagram_text = (
                "📸 <b>دانلود از اینستاگرام</b>\n\n"
                "<b>🔹 انواع محتوای پشتیبانی شده:</b>\n"
                "• پست‌های معمولی (عکس و ویدئو)\n"
                "• استوری‌ها (با دسترسی‌های مناسب)\n"
                "• ریلز\n"
                "• IGTV\n\n"
                "<b>🔸 نکات مهم:</b>\n"
                "• برای دانلود پست‌های خصوصی باید دسترسی لازم به حساب را داشته باشید\n"
                "• در صورت داشتن چند عکس یا ویدئو در یک پست، همه آنها دانلود می‌شوند\n"
                "• در مواردی ممکن است به دلیل محدودیت‌های اینستاگرام، دانلود با خطا مواجه شود\n\n"
                "<b>🔄 روش استفاده:</b>\n"
                "لینک پست اینستاگرام را کپی کرده و به ربات ارسال کنید. ربات به صورت خودکار لینک را تشخیص داده و پردازش می‌کند."
            )
            
            # مثال لینک اینستاگرام
            example_url = "https://www.instagram.com/p/sample_post/"
            
            # ایجاد دکمه‌های میانبر
            markup = types.InlineKeyboardMarkup(row_width=2)
            try_btn = types.InlineKeyboardButton("🔄 امتحان با مثال", callback_data="try_example_instagram")
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
            markup.add(try_btn)
            markup.add(back_btn)
            
            bot.send_message(
                call.message.chat.id,
                instagram_text,
                parse_mode="HTML",
                reply_markup=markup
            )
            
        # اطلاعات جستجوی هشتگ
        elif call.data == "hashtag_search":
            hashtag_text = (
                "🔍 <b>جستجوی هشتگ</b>\n\n"
                "<b>🔹 قابلیت‌های جستجوی هشتگ:</b>\n"
                "• جستجوی هشتگ در کانال‌های ثبت شده\n"
                "• ذخیره پیام‌های مرتبط با هشتگ\n"
                "• امکان دسته‌بندی محتوا با هشتگ‌ها\n\n"
                "<b>🔸 دستورات مرتبط با هشتگ:</b>\n"
                "• <code>/add_hashtag #نام_هشتگ توضیحات</code> - افزودن هشتگ جدید\n"
                "• <code>/remove_hashtag #نام_هشتگ</code> - حذف هشتگ\n"
                "• <code>/list_hashtags</code> - نمایش لیست هشتگ‌ها\n"
                "• <code>/search_hashtag #نام_هشتگ</code> - جستجوی پیام‌های مرتبط با هشتگ\n\n"
                "<b>🔹 مدیریت کانال‌ها:</b>\n"
                "• <code>/add_channel @نام_کانال</code> - افزودن کانال برای جستجو\n"
                "• <code>/remove_channel @نام_کانال</code> - حذف کانال\n"
                "• <code>/list_channels</code> - نمایش لیست کانال‌ها\n\n"
                "<b>🔄 روش استفاده:</b>\n"
                "1. ابتدا کانال‌های مورد نظر را با دستور add_channel اضافه کنید\n"
                "2. سپس با دستور search_hashtag# هشتگ مورد نظر را جستجو کنید"
            )
            
            # ایجاد دکمه‌های میانبر
            markup = types.InlineKeyboardMarkup(row_width=2)
            add_channel_btn = types.InlineKeyboardButton("➕ افزودن کانال", callback_data="add_channel_cmd")
            list_hashtags_btn = types.InlineKeyboardButton("📋 لیست هشتگ‌ها", callback_data="list_hashtags_cmd")
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
            
            markup.add(add_channel_btn, list_hashtags_btn)
            markup.add(back_btn)
            
            bot.send_message(
                call.message.chat.id,
                hashtag_text,
                parse_mode="HTML",
                reply_markup=markup
            )
            
        # پرسش و پاسخ
        elif call.data == "faq":
            faq_text = (
                "❓ <b>پرسش و پاسخ</b>\n\n"
                "<b>🔹 سوالات متداول:</b>\n\n"
                "1️⃣ <b>چرا ویدیو دانلود نمی‌شود؟</b>\n"
                "• اطمینان حاصل کنید که لینک معتبر است\n"
                "• ممکن است ویدیو خصوصی باشد یا محدودیت سنی داشته باشد\n"
                "• در برخی موارد، سرویس‌دهنده ویدیو دسترسی را محدود می‌کند\n\n"
                "2️⃣ <b>چرا کیفیت ویدیو پایین است؟</b>\n"
                "• محدودیت حجم فایل در تلگرام (50 مگابایت)\n"
                "• انتخاب خودکار کیفیت پایین‌تر برای اطمینان از موفقیت دانلود\n\n"
                "3️⃣ <b>آیا استفاده از ربات هزینه دارد؟</b>\n"
                "• خیر، استفاده از ربات کاملاً رایگان است\n\n"
                "4️⃣ <b>آیا ربات اطلاعات کاربران را ذخیره می‌کند؟</b>\n"
                "• فقط اطلاعات مورد نیاز برای عملکرد ربات ذخیره می‌شود\n"
                "• هیچ اطلاعات شخصی به اشتراک گذاشته نمی‌شود\n\n"
                "5️⃣ <b>در صورت بروز مشکل با چه کسی تماس بگیرم؟</b>\n"
                "• از دستور /feedback برای ارسال بازخورد یا گزارش مشکل استفاده کنید"
            )
            
            # ایجاد دکمه‌های میانبر
            markup = types.InlineKeyboardMarkup(row_width=2)
            support_btn = types.InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
            
            markup.add(support_btn, back_btn)
            
            bot.send_message(
                call.message.chat.id,
                faq_text,
                parse_mode="HTML",
                reply_markup=markup
            )
            
        # بازگشت به منوی اصلی
        elif call.data == "return_to_menu":
            handle_start_help(call.message)
            
        # ارسال فرم پشتیبانی
        elif call.data == "support":
            support_text = (
                "🆘 <b>پشتیبانی و گزارش مشکلات</b>\n\n"
                "برای ارسال گزارش مشکل یا درخواست پشتیبانی، لطفاً از دستور زیر استفاده کنید:\n\n"
                "<code>/feedback متن پیام شما</code>\n\n"
                "پیام شما به تیم پشتیبانی ارسال خواهد شد و در اسرع وقت بررسی می‌شود."
            )
            
            # ایجاد دکمه بازگشت
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
            markup.add(back_btn)
            
            bot.send_message(
                call.message.chat.id,
                support_text,
                parse_mode="HTML",
                reply_markup=markup
            )
            
        # کاربر دستور "افزودن کانال" را زده است
        elif call.data == "add_channel_cmd":
            bot.send_message(
                call.message.chat.id,
                "➕ <b>افزودن کانال</b>\n\n"
                "برای افزودن کانال به لیست جستجوی هشتگ، از دستور زیر استفاده کنید:\n\n"
                "<code>/add_channel @نام_کانال</code>\n\n"
                "توجه: ربات باید در کانال مورد نظر عضو باشد.",
                parse_mode="HTML"
            )
            
        # کاربر دستور "لیست هشتگ‌ها" را زده است
        elif call.data == "list_hashtags_cmd":
            bot.send_message(
                call.message.chat.id,
                "🔄 در حال دریافت لیست هشتگ‌ها...",
                parse_mode="HTML"
            )
            # ارسال دستور لیست هشتگ‌ها به تابع مربوطه
            list_hashtags_command(call.message)

        # انتخاب کیفیت ویدیو
        elif call.data == "select_quality":
            quality_text = (
                "📊 <b>انتخاب کیفیت ویدیو</b>\n\n"
                "لطفاً کیفیت مورد نظر خود را انتخاب کنید:"
            )
            
            # ایجاد دکمه‌های انتخاب کیفیت
            markup = types.InlineKeyboardMarkup(row_width=3)
            low_btn = types.InlineKeyboardButton("240p (کم حجم)", callback_data="set_quality_240p")
            medium_btn = types.InlineKeyboardButton("360p (استاندارد)", callback_data="set_quality_360p")
            high_btn = types.InlineKeyboardButton("720p (HD)", callback_data="set_quality_720p")
            back_btn = types.InlineKeyboardButton("🔙 بازگشت", callback_data="return_to_menu")
            
            markup.add(low_btn, medium_btn, high_btn)
            markup.add(back_btn)
            
            bot.send_message(
                call.message.chat.id,
                quality_text,
                parse_mode="HTML",
                reply_markup=markup
            )
            
        # تنظیم کیفیت ویدیو
        elif call.data.startswith("set_quality_"):
            quality = call.data.replace("set_quality_", "")
            
            # ذخیره تنظیمات کیفیت برای کاربر
            user_id = call.from_user.id
            
            # ایجاد یا بروزرسانی تنظیمات کاربر
            if not hasattr(bot, 'user_settings'):
                bot.user_settings = {}
                
            if user_id not in bot.user_settings:
                bot.user_settings[user_id] = {}
                
            bot.user_settings[user_id]['video_quality'] = quality
            
            # نمایش پیام تایید
            bot.send_message(
                call.message.chat.id,
                f"✅ کیفیت ویدیو با موفقیت به <b>{quality}</b> تغییر یافت.\n\n"
                f"این تنظیم برای همه دانلودهای بعدی شما اعمال خواهد شد.",
                parse_mode="HTML",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="return_to_menu")
                )
            )
            
        # امتحان لینک نمونه یوتیوب
        elif call.data == "try_example_youtube":
            # ارسال یک لینک نمونه یوتیوب به عنوان مثال
            example_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            
            bot.send_message(
                call.message.chat.id,
                f"🔄 لینک نمونه یوتیوب:\n{example_url}\n\n"
                "برای دانلود، لینک را کپی کرده و به صورت جداگانه ارسال کنید."
            )
            
        # امتحان لینک نمونه اینستاگرام
        elif call.data == "try_example_instagram":
            # ارسال یک لینک نمونه اینستاگرام به عنوان مثال
            example_url = "https://www.instagram.com/p/sample_post/"
            
            bot.send_message(
                call.message.chat.id,
                f"🔄 لینک نمونه اینستاگرام:\n{example_url}\n\n"
                "برای دانلود واقعی، یک لینک معتبر اینستاگرام را کپی کرده و ارسال کنید."
            )
            
        # لغو دانلود
        elif call.data.startswith("cancel_"):
            download_id = call.data[7:]  # حذف "cancel_" از ابتدای متن
            
            # بررسی وجود دانلود
            if hasattr(bot, 'downloads') and download_id in bot.downloads:
                download_info = bot.downloads[download_id]
                download_info['status'] = 'cancelled'
                
                # حذف دکمه‌های اینلاین و نمایش پیام لغو
                try:
                    bot.edit_message_text(
                        "❌ دانلود با موفقیت لغو شد.",
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=None
                    )
                except Exception as edit_error:
                    logger.error(f"خطا در بروزرسانی پیام لغو: {edit_error}", exc_info=True)
                
                # پاکسازی فایل‌های موقت
                if 'file_path' in download_info and download_info['file_path']:
                    try:
                        if os.path.exists(download_info['file_path']):
                            os.remove(download_info['file_path'])
                    except Exception as file_error:
                        logger.error(f"خطا در پاکسازی فایل: {file_error}", exc_info=True)
            else:
                bot.answer_callback_query(
                    call.id,
                    "این دانلود یافت نشد یا قبلاً لغو شده است.",
                    show_alert=True
                )
        
        # انتخاب کیفیت
        elif call.data.startswith("quality_"):
            parts = call.data.split("_")
            quality = parts[1]
            download_id = "_".join(parts[2:])  # بقیه متن، شناسه دانلود است
            
            # بررسی وجود دانلود
            if hasattr(bot, 'downloads') and download_id in bot.downloads:
                download_info = bot.downloads[download_id]
                download_info['quality'] = quality
                
                # بروزرسانی پیام با اطلاعات جدید
                bot.edit_message_text(
                    f"🎬 <b>در حال دانلود ویدیو...</b>\n\n"
                    f"📊 کیفیت انتخاب شده: <b>{quality}</b>\n"
                    f"🔄 وضعیت: در حال دانلود...",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="HTML",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("❌ لغو دانلود", callback_data=f"cancel_{download_id}")
                    )
                )
            else:
                bot.answer_callback_query(
                    call.id,
                    "این دانلود یافت نشد یا قبلاً لغو شده است.",
                    show_alert=True
                )
    
    except Exception as e:
        logger.error(f"خطا در پردازش callback: {e}", exc_info=True)
        try:
            bot.send_message(call.message.chat.id, f"⚠️ خطا در پردازش عملیات: {str(e)}")
        except:
            logger.error("خطا در ارسال پیام خطا", exc_info=True)

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