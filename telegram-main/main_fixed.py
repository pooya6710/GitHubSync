"""
نسخه بهینه‌شده فایل main.py برای ربات تلگرام
این فایل با استفاده از run_telegram_bot.py ربات را اجرا می‌کند
تمامی قابلیت‌های اصلی حفظ شده است
"""
import os
import sys
import json
import logging
import time
import threading
from flask import Flask, jsonify, render_template, request
import traceback

# بارگذاری ماژول‌های اختیاری
try:
    from debug_logger import debug_log, setup_logging
    print("✅ ماژول debug_logger با موفقیت بارگذاری شد")
except ImportError:
    print("⚠️ ماژول debug_logger یافت نشد، از لاگینگ ساده استفاده می‌شود")
    def debug_log(message, level="INFO", context=None):
        print(f"{level}: {message}")

try:
    from server_status import get_cached_server_status, generate_server_status
    print("✅ ماژول server_status با موفقیت بارگذاری شد")
except ImportError:
    print("⚠️ ماژول server_status یافت نشد، از تابع ساده استفاده می‌شود")
    def get_cached_server_status():
        return {"is_bot_running": True, "uptime": "نامشخص", "system": "نامشخص"}
    def generate_server_status():
        return {"is_bot_running": True, "uptime": "نامشخص", "system": "سیستم فعال است"}

# ایجاد اپلیکیشن فلسک
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')

# تنظیمات وضعیت سرور
SERVER_STATUS_FILE = "server_status.json"
bot_status = {
    "running": False,
    "start_time": time.time(),
    "uptime": "0 ساعت و 0 دقیقه",
    "users_count": 0,
    "downloads_count": 0,
    "last_activity": "هنوز فعالیتی ثبت نشده",
    "system": "در حال راه‌اندازی..."
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
                if "system" in saved_status:
                    bot_status["system"] = saved_status["system"]
                
                server_status = get_cached_server_status()
                if server_status and "is_bot_running" in server_status:
                    bot_status["running"] = server_status["is_bot_running"]
        except Exception as e:
            print(f"خطا در خواندن فایل وضعیت سرور: {e}")

# مسیرهای وب
@app.route('/')
def index():
    """صفحه اصلی"""
    update_bot_status()
    return render_template('index.html', bot_status=bot_status)

@app.route('/status')
def status():
    """صفحه وضعیت"""
    update_bot_status()
    return render_template('status.html', bot_status=bot_status)

@app.route('/ping')
def ping():
    """بررسی فعال بودن سرور"""
    return "Server is alive!", 200

@app.route('/webhook_test', methods=['GET', 'POST'])
def webhook_test():
    """تست و بازنشانی وب‌هوک تلگرام"""
    if request.method == 'POST':
        try:
            data = request.json
            debug_log(f"داده‌های وب‌هوک دریافت شد: {data}", "INFO")
            return jsonify({"success": True, "message": "وب‌هوک با موفقیت دریافت شد"})
        except Exception as e:
            debug_log(f"خطا در پردازش وب‌هوک: {str(e)}", "ERROR")
            return jsonify({"success": False, "error": str(e)}), 500
    else:
        return jsonify({
            "status": "آماده",
            "webhook_url": request.host_url + "webhook",
            "message": "برای تست وب‌هوک، یک درخواست POST به این URL ارسال کنید"
        })

# راه‌اندازی ربات
def run_bot():
    """راه‌اندازی ربات تلگرام با تلاش مجدد در صورت بروز خطا"""
    print("🚀 در حال راه‌اندازی ربات تلگرام...")
    max_retries = 5
    retry_delay = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            bot_status["running"] = True
            with open(SERVER_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"is_bot_running": True, "system": "سیستم فعال است"}, f)
                
            # راه‌اندازی ربات
            from run_telegram_bot import main as run_telegram_bot_main
            run_telegram_bot_main()
            print("✅ ربات تلگرام (نسخه جدید) با موفقیت راه‌اندازی شد")
            return True
            
        except Exception as e:
            retry_count += 1
            error_msg = f"⚠️ خطا در راه‌اندازی ربات (تلاش {retry_count}/{max_retries}): {e}"
            print(error_msg)
            print(traceback.format_exc())
            
            bot_status["running"] = False
            if retry_count < max_retries:
                print(f"🔄 تلاش مجدد در {retry_delay} ثانیه...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
            else:
                print("❌ همه تلاش‌ها برای راه‌اندازی ربات ناموفق بود")
                return False

def main():
    """تابع اصلی اجرای برنامه"""
    # راه‌اندازی ربات در ترد جداگانه
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # راه‌اندازی سرور فلسک
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    try:
        from flask import Flask
        print("✅ ماژول Flask با موفقیت بارگذاری شد")
    except ImportError:
        print("❌ خطا در بارگذاری ماژول Flask")
        sys.exit(1)
        
    main()