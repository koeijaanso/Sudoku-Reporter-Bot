# bot.py
import logging
import sys
import os
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
# Замените на токен вашего бота
BOT_TOKEN = "8651698350:AAFxhxzlMoiXA1v2k1ym-pLI2uFM7bOdjQM"  

# Замените на ваш личный Telegram ID (число)
YOUR_CHAT_ID = 837102027 

# Папка для сохранения отчётов (будет создана автоматически)
REPORTS_FILE = "reports.txt"
# ================================

def save_report(user_id: int, username: str, full_name: str, text: str):
    """Сохраняет отчёт в файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Создаём файл, если его нет
    if not os.path.exists(REPORTS_FILE):
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            f.write("=== ОТЧЁТЫ ОБ ОШИБКАХ И ПРЕДЛОЖЕНИЯХ ===\n")
            f.write(f"Создано: {timestamp}\n")
            f.write("="*50 + "\n\n")
    
    # Сохраняем отчёт
    with open(REPORTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]\n")
        f.write(f"Пользователь: {full_name} (@{username}) [ID: {user_id}]\n")
        f.write(f"Текст:\n{text}\n")
        f.write("-"*40 + "\n\n")
    
    logger.info(f"Сохранён отчёт от {username} ({user_id})")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    user = update.effective_user
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для сбора багов и предложений.\n\n"
        "📝 **Как отправлять отчёты:**\n"
        "• Просто напиши текст\n"
        "• Или используй формат:\n"
        "  `БАГ: описание проблемы`\n"
        "  `УЛУЧШЕНИЕ: твоя идея`\n\n"
        "📌 Все отчёты отправляются разработчику автоматически.\n"
        "Спасибо за помощь в улучшении проекта! 🚀\n"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений (все пользователи могут писать)"""
    user = update.effective_user
    text = update.message.text
    
    # Сохраняем отчёт локально
    save_report(
        user.id,
        user.username or "no_username",
        user.first_name or "unknown",
        text
    )
    
    # Отправляем уведомление вам (разработчику)
    try:
        report_preview = text[:200] + "..." if len(text) > 200 else text
        notification = (
            f"📬 **Новый отчёт!**\n\n"
            f"👤 **От:** {user.first_name}"
        )
        
        if user.username:
            notification += f" (@{user.username})"
        
        notification += f"\n🆔 **ID:** `{user.id}`\n"
        
        # Определяем тип отчёта
        text_lower = text.lower()
        if "баг" in text_lower or "ошибк" in text_lower or "bug" in text_lower:
            notification += "🏷️ **Тип:** ❌ БАГ\n"
        elif "улучш" in text_lower or "предлож" in text_lower or "идея" in text_lower:
            notification += "🏷️ **Тип:** 💡 УЛУЧШЕНИЕ\n"
        
        notification += f"\n📝 **Текст:**\n{report_preview}\n"
        
        await context.bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text=notification,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление: {e}")
    
    # Отправляем подтверждение пользователю
    await update.message.reply_text(
        "✅ **Отчёт получен!**\n\n"
        "Спасибо за обратную связь! 🙏\n"
        "Разработчик получит уведомление.",
        parse_mode='Markdown'
    )

async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра всех отчётов (только для разработчика)"""
    user = update.effective_user
    
    # Проверяем, что это разработчик
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав на эту команду.")
        return
    
    # Читаем файл с отчётами
    if not os.path.exists(REPORTS_FILE):
        await update.message.reply_text("📭 Пока нет ни одного отчёта.")
        return
    
    try:
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Если файл слишком большой, отправляем последние 4000 символов
        if len(content) > 4000:
            content = "...(обрезано)\n\n" + content[-4000:]
        
        await update.message.reply_text(
            f"📋 **Все отчёты:**\n\n```\n{content}\n```",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка при чтении файла: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра статистики (только для разработчика)"""
    user = update.effective_user
    
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    
    if not os.path.exists(REPORTS_FILE):
        await update.message.reply_text("Нет отчётов")
        return
    
    # Подсчитываем количество отчётов
    with open(REPORTS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        report_count = content.count("[20")  # Примерное количество (по датам)
    
    # Размер файла
    file_size = os.path.getsize(REPORTS_FILE) / 1024  # в КБ
    
    stats_text = (
        f"📊 **Статистика:**\n\n"
        f"📝 Всего отчётов: ~{report_count}\n"
        f"💾 Размер файла: {file_size:.1f} КБ\n"
        f"📁 Файл: `{REPORTS_FILE}`"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def clear_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка всех отчётов (только для разработчика)"""
    user = update.effective_user
    
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    if os.path.exists(REPORTS_FILE):
        os.remove(REPORTS_FILE)
        await update.message.reply_text("✅ Все отчёты удалены!")
    else:
        await update.message.reply_text("Файл с отчётами не найден.")

def main():
    """Запуск бота"""
    # Проверка токена
    if BOT_TOKEN == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz":
        logger.error("❌ Токен не изменён! Замените BOT_TOKEN на свой.")
        sys.exit(1)
    
    if YOUR_CHAT_ID == 123456789:
        logger.warning("⚠️ Внимание: YOUR_CHAT_ID не изменён! Уведомления не будут отправляться.")
    
    # Создаём приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reports", reports_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_reports))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ Бот запущен и готов к работе!")
    
    # Запускаем polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import asyncio
    # Небольшая задержка, чтобы избежать конфликта при запуске
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(3))
    main()
