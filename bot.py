# bot.py
import logging
import sys
import os
from datetime import datetime
import asyncio

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8651698350:AAFxhxzlMoiXA1v2k1ym-pLI2uFM7bOdjQM"  
YOUR_CHAT_ID = 837102027 
REPORTS_FILE = "reports.txt"
USERS_FILE = "users.txt"
# ================================

def save_report(user_id: int, username: str, full_name: str, text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not os.path.exists(REPORTS_FILE):
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            f.write("=== ОТЧЁТЫ ОБ ОШИБКАХ И ПРЕДЛОЖЕНИЯХ ===\n")
            f.write(f"Создано: {timestamp}\n")
            f.write("="*50 + "\n\n")
    
    with open(REPORTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]\n")
        f.write(f"Пользователь: {full_name} (@{username}) [ID: {user_id}]\n")
        f.write(f"Текст:\n{text}\n")
        f.write("-"*40 + "\n\n")
    
    logger.info(f"Сохранён отчёт от {username} ({user_id})")

def save_user(user_id: int):
    users = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = set(int(line.strip()) for line in f if line.strip())
    
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            for uid in users:
                f.write(f"{uid}\n")
        logger.info(f"Добавлен новый пользователь: {user_id}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    save_user(user.id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    save_user(user.id)
    save_report(
        user.id,
        user.username or "no_username",
        user.first_name or "unknown",
        text
    )
    
    try:
        report_preview = text[:200] + "..." if len(text) > 200 else text
        notification = f"📬 **Новый отчёт!**\n\n👤 **От:** {user.first_name}"
        
        if user.username:
            notification += f" (@{user.username})"
        
        notification += f"\n🆔 **ID:** `{user.id}`\n"
        
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
    
    await update.message.reply_text(
        "✅ **Отчёт получен!**\n\n"
        "Спасибо за обратную связь! 🙏\n"
        "Разработчик получит уведомление.",
        parse_mode='Markdown'
    )

async def send_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав на эту команду.")
        return
    
    if not os.path.exists(REPORTS_FILE):
        await update.message.reply_text("📭 Файл с отчётами не найден.")
        return
    
    try:
        with open(REPORTS_FILE, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename="reports.txt"),
                caption=f"📋 Все отчёты\nДата: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        logger.info("Файл reports.txt отправлен разработчику")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def new_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав.")
        return
    
    version_text = " ".join(context.args)
    if not version_text:
        version_text = "Вышла новая версия игры Sudoku!"
    
    message = (
        f"🎉 **{version_text}** 🎉\n\n"
        f"📥 **Скачать новую версию:**\n"
        f"`https://drive.google.com/file/d/1_rPmdG-Dna21I24xAGwEJ-SE60jhUs5c/view?usp=sharing`\n\n"
        f"Спасибо, что помогаете делать игру лучше! 🙏"
    )
    
    if not os.path.exists(USERS_FILE):
        await update.message.reply_text("📭 Нет сохранённых пользователей.")
        return
    
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        users = [int(line.strip()) for line in f if line.strip()]
    
    if not users:
        await update.message.reply_text("📭 Нет пользователей.")
        return
    
    await update.message.reply_text(f"🚀 Оповещаю {len(users)} пользователей...")
    
    success = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Ошибка {user_id}: {e}")
    
    await update.message.reply_text(f"✅ Оповещение завершено! Успешно: {success}")

async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    
    if not os.path.exists(REPORTS_FILE):
        await update.message.reply_text("📭 Нет отчётов.")
        return
    
    with open(REPORTS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    if len(content) > 4000:
        content = "...(обрезано)\n\n" + content[-4000:]
    
    await update.message.reply_text(f"📋 **Все отчёты:**\n\n```\n{content}\n```", parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    
    report_count = 0
    file_size = 0
    if os.path.exists(REPORTS_FILE):
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            report_count = f.read().count("[20")
        file_size = os.path.getsize(REPORTS_FILE) / 1024
    
    users_count = 0
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users_count = len([line for line in f if line.strip()])
    
    await update.message.reply_text(
        f"📊 **Статистика:**\n\n"
        f"📝 Отчётов: ~{report_count}\n"
        f"👥 Пользователей: {users_count}\n"
        f"💾 Размер: {file_size:.1f} КБ",
        parse_mode='Markdown'
    )

async def clear_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    if os.path.exists(REPORTS_FILE):
        os.remove(REPORTS_FILE)
        await update.message.reply_text("✅ Все отчёты удалены!")
    else:
        await update.message.reply_text("Файл не найден.")

async def post_init(application: Application):
    """Вызывается после успешного подключения"""
    logger.info("✅ Бот успешно подключился к Telegram!")
    # Отправляем уведомление разработчику, что бот запустился
    try:
        await application.bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text="✅ Бот запущен и готов к работе!"
        )
    except:
        pass

def main():
    if BOT_TOKEN == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz":
        logger.error("❌ Токен не изменён!")
        sys.exit(1)
    
    # Создаём приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reports", reports_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_reports))
    app.add_handler(CommandHandler("sendfile", send_file_command))
    app.add_handler(CommandHandler("newversion", new_version))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Добавляем обработчик успешного запуска
    app.post_init = post_init
    
    logger.info("🔄 Бот запускается...")
    
    # Важно: используем drop_pending_updates=True, чтобы очистить старые обновления
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # Это помогает избежать Conflict
    )

if __name__ == "__main__":
    # Добавляем задержку и запускаем
    import asyncio
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(2))
    main()
