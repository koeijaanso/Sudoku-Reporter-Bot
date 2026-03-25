# bot.py
import logging
import sys
import os
from datetime import datetime
import asyncio
import threading
import json

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8651698350:AAFxhxzlMoiXA1v2k1ym-pLI2uFM7bOdjQM"  
YOUR_CHAT_ID = 837102027 

# Google Sheets настройки
SHEET_NAME = "SudokuBotData"  # Имя вашей таблицы
# ================================

# Инициализация Google Sheets из секретного файла на Render
def init_google_sheets():
    """Подключение к Google Sheets из секретного файла"""
    try:
        # Проверяем наличие секретного файла (Render Secret File)
        secret_file_path = "/etc/secrets/credentials.json"  # Путь для Secret Files на Render
        creds_json = None
        
        if os.path.exists(secret_file_path):
            with open(secret_file_path, 'r') as f:
                creds_json = f.read()
            logger.info(f"Секретный файл найден по пути: {secret_file_path}")
        else:
            # Альтернативный путь (если файл загружен в корень)
            if os.path.exists("credentials.json"):
                with open("credentials.json", 'r') as f:
                    creds_json = f.read()
                logger.info("credentials.json найден в корне проекта")
            else:
                logger.warning("credentials.json не найден. Google Sheets недоступен.")
                return None
        
        # Парсим JSON
        creds_dict = json.loads(creds_json)
        
        # Создаём учётные данные
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # Подключаемся
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME)
        logger.info(f"✅ Подключено к Google Sheets: {SHEET_NAME}")
        return sheet
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        return None

# Подключаемся
sheet_conn = init_google_sheets()
if sheet_conn:
    try:
        users_worksheet = sheet_conn.worksheet("Пользователи")
        reports_worksheet = sheet_conn.worksheet("Отчёты")
        logger.info("✅ Листы найдены")
    except Exception as e:
        logger.error(f"Ошибка доступа к листам: {e}")
        users_worksheet = None
        reports_worksheet = None
else:
    users_worksheet = None
    reports_worksheet = None
    logger.warning("⚠️ Google Sheets недоступен, работаю только с локальными файлами")

def save_user_to_sheets(user_id: int, username: str, first_name: str):
    """Сохраняет пользователя в Google Sheets"""
    if not users_worksheet:
        return False
    
    try:
        # Проверяем, есть ли уже такой пользователь
        all_ids = users_worksheet.col_values(1)[1:]  # пропускаем заголовок
        if str(user_id) in all_ids:
            return True
        
        # Добавляем нового пользователя
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        users_worksheet.append_row([
            user_id, 
            first_name, 
            username or "", 
            timestamp
        ])
        logger.info(f"Пользователь {user_id} добавлен в Google Sheets")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")
        return False

def save_report_to_sheets(user_id: int, username: str, first_name: str, text: str):
    """Сохраняет отчёт в Google Sheets"""
    if not reports_worksheet:
        return False
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Определяем тип отчёта
        text_lower = text.lower()
        if "баг" in text_lower or "ошибк" in text_lower or "bug" in text_lower:
            report_type = "БАГ"
        elif "улучш" in text_lower or "предлож" in text_lower or "идея" in text_lower:
            report_type = "УЛУЧШЕНИЕ"
        else:
            report_type = "ОТЗЫВ"
        
        reports_worksheet.append_row([
            timestamp,
            user_id,
            first_name,
            username or "",
            report_type,
            text
        ])
        logger.info(f"Отчёт от {user_id} добавлен в Google Sheets")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения отчёта: {e}")
        return False

def get_all_users_from_sheets():
    """Получает список всех пользователей из Google Sheets"""
    if not users_worksheet:
        return []
    
    try:
        users_data = users_worksheet.get_all_values()
        if len(users_data) <= 1:
            return []
        return [int(row[0]) for row in users_data[1:] if row and row[0]]
    except Exception as e:
        logger.error(f"Ошибка получения пользователей: {e}")
        return []

# ========== ЛОКАЛЬНЫЕ ФАЙЛЫ КАК РЕЗЕРВ ==========
REPORTS_FILE = "reports.txt"
USERS_FILE = "users.txt"

def save_report_local(user_id: int, username: str, full_name: str, text: str):
    """Сохраняет отчёт в локальный файл (резерв)"""
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
    
    logger.info(f"Сохранён отчёт локально от {username} ({user_id})")

def save_user_local(user_id: int):
    """Сохраняет пользователя в локальный файл (резерв)"""
    users = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = set(int(line.strip()) for line in f if line.strip())
    
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            for uid in users:
                f.write(f"{uid}\n")
        logger.info(f"Добавлен новый пользователь локально: {user_id}")

def get_all_users_local():
    """Получает список пользователей из локального файла"""
    if not os.path.exists(USERS_FILE):
        return []
    
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return [int(line.strip()) for line in f if line.strip()]

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Сохраняем в Google Sheets и локально
    save_user_to_sheets(user.id, user.username or "", user.first_name or "")
    save_user_local(user.id)
    
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
    user = update.effective_user
    text = update.message.text
    
    # Сохраняем в Google Sheets и локально
    save_user_to_sheets(user.id, user.username or "", user.first_name or "")
    save_user_local(user.id)
    save_report_to_sheets(user.id, user.username or "", user.first_name or "", text)
    save_report_local(user.id, user.username or "no_username", user.first_name or "unknown", text)
    
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
        await update.message.reply_text("⛔ Нет прав.")
        return
    
    # Показываем ссылку на Google Sheets
    await update.message.reply_text(
        "📊 **Все отчёты теперь хранятся в Google Sheets!**\n\n"
        "Ссылка на таблицу: (вставьте ссылку на вашу таблицу)\n\n"
        "Локальная копия reports.txt:\n"
        f"Размер: {os.path.getsize(REPORTS_FILE) / 1024:.1f} КБ" if os.path.exists(REPORTS_FILE) else "Локальный файл не найден",
        parse_mode='Markdown'
    )

async def new_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
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
    
    # Берём пользователей из Google Sheets
    users = get_all_users_from_sheets()
    if not users:
        # Если нет в Google Sheets, берём из локального файла
        users = get_all_users_local()
    
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

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика + диагностика Google Sheets"""
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    
    # Диагностика Google Sheets
    gs_status = "❌ НЕ ПОДКЛЮЧЁН"
    gs_error = ""
    
    if sheet_conn:
        gs_status = "✅ ПОДКЛЮЧЁН"
    else:
        gs_error = "\n\n⚠️ Google Sheets не подключён. Проверьте:\n• credentials.json\n• Имя таблицы\n• Доступ к таблице"
    
    # Проверка секретного файла
    secret_path = "/etc/secrets/credentials.json"
    file_exists = os.path.exists(secret_path)
    file_size = os.path.getsize(secret_path) if file_exists else 0
    
    # Статистика из Google Sheets
    users_count = 0
    reports_count = 0
    
    if sheet_conn and users_worksheet and reports_worksheet:
        try:
            users_data = users_worksheet.get_all_values()
            users_count = len(users_data) - 1 if len(users_data) > 1 else 0
            
            reports_data = reports_worksheet.get_all_values()
            reports_count = len(reports_data) - 1 if len(reports_data) > 1 else 0
        except Exception as e:
            gs_error = f"\n\n⚠️ Ошибка чтения таблицы: {e}"
    else:
        # Если Google Sheets не подключён, показываем локальную статистику
        if os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "r", encoding="utf-8") as f:
                reports_count = f.read().count("[20")
        
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users_count = len([line for line in f if line.strip()])
    
    # Формируем сообщение
    message = (
        f"📊 **Статистика**\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"📝 Отчётов: {reports_count}\n\n"
        f"🔌 **Google Sheets:** {gs_status}\n"
        f"📁 Файл credentials.json: {'✅ найден' if file_exists else '❌ НЕ НАЙДЕН'}\n"
        f"📄 Размер JSON: {file_size} байт"
    )
    
    if gs_error:
        message += gs_error
    
    await update.message.reply_text(message, parse_mode='Markdown')
async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ссылку на Google Sheets"""
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав.")
        return
    
    await update.message.reply_text(
        "📊 **Все отчёты теперь в Google Sheets!**\n\n"
        "Откройте вашу таблицу:\n"
        "https://docs.google.com/spreadsheets/d/https://docs.google.com/spreadsheets/d/11AjXqhjUY3rrMzZohF9EToLtRcVYAnOs1ykZ6GOHZYs/edit?usp=sharing\n\n"
        "Там есть листы:\n"
        "• **Пользователи** — список всех, кто писал боту\n"
        "• **Отчёты** — все сообщения с багами и предложениями",
        parse_mode='Markdown'
    )

async def clear_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    await update.message.reply_text(
        "⚠️ **Очистка отчётов**\n\n"
        "Данные теперь хранятся в Google Sheets.\n"
        "Чтобы очистить таблицу, сделайте это вручную в Google Sheets.",
        parse_mode='Markdown'
    )

async def post_init(application: Application):
    logger.info("✅ Бот успешно подключился к Telegram!")
    try:
        await application.bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text="✅ Бот запущен и готов к работе!\n\n📊 Данные сохраняются в Google Sheets"
        )
    except:
        pass

# ========== FLASK ДЛЯ RENDER ==========
from flask import Flask

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "✅ Bot is running with Google Sheets", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)
    
async def check_sheets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка подключения к Google Sheets"""
    user = update.effective_user
    if user.id != YOUR_CHAT_ID:
        return
    
    # Проверяем существование файла
    secret_path = "/etc/secrets/credentials.json"
    file_exists = os.path.exists(secret_path)
    
    message = f"🔍 **Диагностика Google Sheets**\n\n"
    message += f"📁 Файл {secret_path}: {'✅ найден' if file_exists else '❌ НЕ НАЙДЕН'}\n"
    
    if file_exists:
        with open(secret_path, 'r') as f:
            content = f.read()
            message += f"📄 Размер JSON: {len(content)} символов\n"
            message += f"🔑 Содержит private_key: {'✅' if 'private_key' in content else '❌'}\n"
    
    message += f"\n📊 Таблица: `{SHEET_NAME}`\n"
    message += f"👤 Ваш ID: `{user.id}`\n"
    
    if sheet_conn:
        message += f"\n✅ Google Sheets подключён!"
    else:
        message += f"\n❌ Google Sheets НЕ подключён"
    
    await update.message.reply_text(message, parse_mode='Markdown')
async def initialize_bot(app: Application):
    """Инициализация бота с очисткой конфликтов"""
    try:
        # Удаляем вебхук и все старые обновления
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхук удалён")
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
# ========== ЗАПУСК ==========
def main():
    if BOT_TOKEN == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz":
        logger.error("❌ Токен не изменён!")
        sys.exit(1)
    
    # Запускаем Flask в фоне
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reports", reports_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("clear", clear_reports))
    app.add_handler(CommandHandler("sendfile", send_file_command))
    app.add_handler(CommandHandler("newversion", new_version))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("checksheets", check_sheets))
    
    app.post_init = post_init
    
    logger.info("🔄 Бот запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(2))
    main()
