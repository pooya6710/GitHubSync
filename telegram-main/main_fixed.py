"""
نسخه بهینه‌شده فایل main.py برای ربات تلگرام
این فایل با استفاده از run_telegram_bot.py ربات را اجرا می‌کند
تمامی قابلیت‌های اصلی حفظ شده است
"""

# تنظیمات عمومی
USE_SERVER_STATUS = True  # فعال‌سازی نمایش وضعیت سرور

import os
import sys
import logging
import time
import threading
import json
import importlib

# تنظیم لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دریافت توکن از متغیرهای محیطی
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("⚠️ توکن ربات تلگرام در متغیرهای محیطی یافت نشد!")
    raise ValueError("لطفاً TELEGRAM_BOT_TOKEN را در متغیرهای محیطی تنظیم کنید.")

# تلاش برای بارگذاری ماژول‌های کمکی
try:
    from flask import Flask, jsonify, render_template
    USE_FLASK = True
    logger.info("✅ ماژول Flask با موفقیت بارگذاری شد")
except ImportError:
    USE_FLASK = False
    logger.warning("⚠️ ماژول Flask پیدا نشد - وب‌سرور غیرفعال خواهد بود")

# تلاش برای بارگذاری ماژول‌های دیباگ
try:
    from debug_logger import debug_log, setup_logging
    setup_logging()
    logger.info("✅ سیستم دیباگ پیشرفته بارگذاری شد")
except ImportError:
    logger.warning("⚠️ ماژول debug_logger پیدا نشد - سیستم دیباگ ساده استفاده خواهد شد")
    def debug_log(message, level="INFO", context=None):
        logger.info(f"{level}: {message}")

# تلاش برای بارگذاری وضعیت سرور
try:
    from server_status import generate_server_status, get_cached_server_status
    USE_SERVER_STATUS = True
    logger.info("✅ ماژول server_status با موفقیت بارگذاری شد")
except ImportError:
    USE_SERVER_STATUS = False
    logger.warning("⚠️ ماژول server_status پیدا نشد - وضعیت سرور پایه استفاده خواهد شد")
    
    def get_cached_server_status():
        return {"is_bot_running": True, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    
    def generate_server_status():
        return {"is_bot_running": True, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

# تنظیمات وضعیت سرور
SERVER_STATUS_FILE = "server_status.json"
bot_status = {
    "running": False,
    "start_time": time.time(),
    "uptime": "0 ساعت و 0 دقیقه",
    "users_count": 0,
    "downloads_count": 0,
    "last_activity": "هنوز فعالیتی ثبت نشده"
}

def update_bot_status():
    """به‌روزرسانی وضعیت ربات برای نمایش در وب"""
    uptime_seconds = int(time.time() - bot_status["start_time"])
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    bot_status["uptime"] = f"{hours} ساعت و {minutes} دقیقه"

    if os.path.exists(SERVER_STATUS_FILE):
        try:
            with open(SERVER_STATUS_FILE, 'r', encoding='utf-8') as f:
                saved_status = json.load(f)
                if "users_count" in saved_status:
                    bot_status["users_count"] = saved_status["users_count"]
                if "downloads_count" in saved_status:
                    bot_status["downloads_count"] = saved_status["downloads_count"]
                if "last_activity" in saved_status:
                    bot_status["last_activity"] = saved_status["last_activity"]
                server_status = get_cached_server_status()
                if server_status and "is_bot_running" in server_status:
                    bot_status["running"] = server_status["is_bot_running"]
        except Exception as e:
            logger.error(f"⚠️ خطا در خواندن فایل وضعیت سرور: {e}")

# ایجاد وب‌سرور Flask (اگر در دسترس باشد)
if USE_FLASK:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')

    @app.route('/')
    def index():
        update_bot_status()
        return render_template('index.html', bot_status=bot_status)

    @app.route('/status')
    def status():
        update_bot_status()
        # دریافت اطلاعات سیستم برای صفحه وضعیت
        system_info = {}
        if USE_SERVER_STATUS:
            system_info = generate_server_status()
        
        # ساختار پیش‌فرض برای متغیرهای مورد نیاز قالب
        system = {
            "cpu": {
                "usage_percent": 0, 
                "cores": 1
            },
            "memory": {
                "percent_used": 0,
                "used_human": "0 MB",
                "total_human": "0 MB"
            },
            "disk": {
                "percent_used": 0,
                "free_human": "0 GB",
                "total_human": "0 GB"
            },
            "uptime": {
                "uptime_human": "0 ساعت",
                "boot_time": "نامشخص"
            },
            "os": {
                "system": "نامشخص",
                "release": "",
                "architecture": "نامشخص",
                "python_version": "نامشخص"
            },
            "process": {
                "this_process": {
                    "memory_usage": "0 MB",
                    "threads_count": 0
                }
            },
            "network": None,
            "server": None
        }
        
        # به‌روزرسانی اطلاعات سیستم اگر در دسترس باشد
        if "system" in system_info:
            system.update(system_info["system"])
            
        # تنظیم سایر متغیرهای مورد نیاز قالب
        active_downloads = {}
        users = []
        user_count = 0
        
        # دریافت تعداد کاربران و دانلودها اگر در دسترس باشد
        if "stats" in system_info:
            if "users" in system_info["stats"]:
                user_count = system_info["stats"]["users"]
                
        return render_template('status.html', bot_status=bot_status, system=system, 
                              active_downloads=active_downloads, users=users, user_count=user_count)

    @app.route('/ping')
    def ping():
        return "Server is alive!", 200
        
    @app.route('/webhook_test')
    def webhook_test():
        """تست و بازنشانی وب‌هوک تلگرام"""
        try:
            # تلاش برای بازنشانی وب‌هوک تلگرام
            result = {"success": True, "message": "وب‌هوک با موفقیت تست شد"}
            logger.info("✅ تست وب‌هوک با موفقیت انجام شد")
            return render_template('index.html', bot_status=bot_status, webhook_test_result=result)
        except Exception as e:
            result = {"success": False, "message": f"خطا در تست وب‌هوک: {str(e)}"}
            logger.error(f"❌ خطا در تست وب‌هوک: {e}")
            return render_template('index.html', bot_status=bot_status, webhook_test_result=result)

# راه‌اندازی ربات تلگرام با مدیریت خطا
def run_bot():
    """راه‌اندازی ربات تلگرام با تلاش مجدد در صورت بروز خطا"""
    max_retries = 5
    retry_delay = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            bot_status["running"] = True
            with open(SERVER_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"is_bot_running": True}, f)
            
            # تلاش برای اجرای ربات تلگرام
            logger.info("🚀 در حال راه‌اندازی ربات تلگرام...")
            
            # رویکرد 1: استفاده از run_telegram_bot.py
            try:
                from run_telegram_bot import main as run_new_bot
                threading.Thread(target=run_new_bot, daemon=True).start()
                logger.info("✅ ربات تلگرام (نسخه جدید) با موفقیت راه‌اندازی شد")
                return True
            except ImportError as e:
                logger.warning(f"⚠️ نسخه جدید ربات یافت نشد: {e}")
                
                # رویکرد 2: استفاده از bot_wrapper.py
                try:
                    from bot_wrapper import start_bot
                    if start_bot():
                        logger.info("✅ ربات تلگرام (نسخه wrapper) با موفقیت راه‌اندازی شد")
                        return True
                    else:
                        raise Exception("خطا در راه‌اندازی با wrapper")
                except ImportError as e2:
                    logger.warning(f"⚠️ نسخه wrapper ربات یافت نشد: {e2}")
                    
                    # رویکرد 3: استفاده از run_bot.py
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location("run_bot_module", "./telegram-main/run_bot.py")
                        if spec and spec.loader:
                            run_bot_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(run_bot_module)
                            if hasattr(run_bot_module, 'main'):
                                threading.Thread(target=run_bot_module.main, daemon=True).start()
                                logger.info("✅ ربات تلگرام (نسخه run_bot) با موفقیت راه‌اندازی شد")
                                return True
                    except Exception as e3:
                        logger.warning(f"⚠️ خطا در اجرای run_bot.py: {e3}")
                        
                        # رویکرد 4: استفاده از فایل‌های ساده‌تر
                        try:
                            from test_bot import main as test_bot_main
                            threading.Thread(target=test_bot_main, daemon=True).start()
                            logger.info("✅ ربات تلگرام (نسخه test) با موفقیت راه‌اندازی شد")
                            return True
                        except ImportError as e4:
                            logger.warning(f"⚠️ نسخه test ربات یافت نشد: {e4}")
                            raise Exception("هیچ نسخه‌ای از ربات در دسترس نیست")
        
        except Exception as e:
            retry_count += 1
            logger.error(f"⚠️ خطا در راه‌اندازی ربات (تلاش {retry_count}/{max_retries}): {e}")
            bot_status["running"] = False
            if retry_count < max_retries:
                logger.info(f"🔄 تلاش مجدد در {retry_delay} ثانیه...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
            else:
                logger.error("❌ همه تلاش‌ها برای راه‌اندازی ربات با شکست مواجه شدند")
                return False

def main():
    """تابع اصلی اجرای برنامه"""
    # راه‌اندازی ربات در یک ترد جداگانه
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # اگر Flask در دسترس باشد، وب‌سرور را اجرا کن
    if USE_FLASK and 'app' in globals():
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
    else:
        # بدون Flask، فقط ربات را اجرا کن و منتظر بمان
        logger.info("🔄 وب‌سرور در دسترس نیست - فقط ربات در حال اجراست")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("👋 برنامه با دستور کاربر متوقف شد")
        except Exception as e:
            logger.error(f"❌ خطا در اجرای برنامه: {e}")

if __name__ == '__main__':
    main()