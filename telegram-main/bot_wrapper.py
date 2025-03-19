"""
ماژول wrapper برای ربات تلگرام
این ماژول یک واسط برای دسترسی به توابع اصلی ربات فراهم می‌کند
"""

import os
import sys
import time
import logging
import threading

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

def start_bot():
    """
    راه‌اندازی ربات تلگرام
    
    این تابع سعی می‌کند ربات را راه‌اندازی کند و در صورت خطا، آن را مدیریت می‌کند
    
    Returns:
        bool: وضعیت موفقیت آمیز بودن راه‌اندازی
    """
    logger.info("🚀 در حال راه‌اندازی ربات تلگرام...")
    
    try:
        # تلاش برای اجرای ربات جدید
        from run_telegram_bot import main
        threading.Thread(target=main, daemon=True).start()
        logger.info("✅ ربات در حالت جدید راه‌اندازی شد")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات جدید: {e}")
        
        try:
            # تلاش برای استفاده از نسخه پشتیبان
            logger.info("🔄 در حال تلاش برای استفاده از نسخه پشتیبان...")
            import importlib.util
            spec = importlib.util.spec_from_file_location("bot_backup", "./telegram-main/bot.py.backup")
            bot_backup = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bot_backup)
            
            if hasattr(bot_backup, 'start_bot'):
                logger.info("🔄 راه‌اندازی با نسخه پشتیبان...")
                bot_backup.start_bot()
                return True
            else:
                logger.error("⚠️ تابع start_bot در نسخه پشتیبان یافت نشد")
                return False
        except Exception as backup_error:
            logger.error(f"❌ خطا در راه‌اندازی نسخه پشتیبان: {backup_error}")
            return False

# صدور متغیرها و توابع مورد نیاز
__all__ = ['TOKEN', 'start_bot']