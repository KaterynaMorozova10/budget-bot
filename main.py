import os
import re
import datetime
import json
import threading
from flask import Flask
import telebot
import gspread

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- НАСТРОЙКА БОТА И GOOGLE ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8663061397:AAFHdqhcaK2uVfht809n1ESuYTIbrk7FvBc")
SPREADSHEET_ID = "1-_QYOaap7Hr8aDfuPUgRJYbImzTDCcc2BDR4ZjiRD24"

ALLOWED_USERS = [549359241, 340848070]

bot = telebot.TeleBot(BOT_TOKEN)

# Подключение ключей Google
if os.path.exists('/etc/secrets/credentials.json'):
    gc = gspread.service_account(filename='/etc/secrets/credentials.json')
elif os.environ.get("GOOGLE_CREDENTIALS"):
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDENTIALS"))
    gc = gspread.service_account_from_dict(creds_dict)
else:
    gc = gspread.service_account(filename="credentials.json")


def is_allowed(message):
    if message.from_user.id not in ALLOWED_USERS:
        bot.reply_to(message, "⛔ У вас нет доступа к этому боту.")
        return False
    return True


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_allowed(message):
        return
        
    bot.reply_to(
        message, 
        "Привет! Я бот учета доходов и трат.\n\n"
        "**Запись расходов:**\n"
        "`продукты 500` или `такси 120`\n\n"
        "**Запись доходов (со знаком +):**\n"
        "`зарплата +5000` или `аванс +1000`\n\n"
        "**Команды статистики /stats:**\n"
        "• `/stats` — отчет за текущий месяц\n"
        "• `/stats 07.2026` — отчет за конкретный месяц (ММ.ГГГГ)\n"
        "• `/stats 01.08.2026 05.08.2026` — отчет за период",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stats'])
def get_stats(message):
    if not is_allowed(message):
        return
        
    try:
        args = message.text.strip().split()[1:]
        now = datetime.datetime.now()
        
        if len(args) == 2:
            try:
                start_date = datetime.datetime.strptime(args[0], "%d.%m.%Y").date()
                end_date = datetime.datetime.strptime(args[1], "%d.%m.%Y").date()
                period_title = f"с {args[0]} по {args[1]}"
            except ValueError:
                bot.reply_to(message, "❌ Формат дат: `/stats 01.08.2026 05.08.2026`", parse_mode="Markdown")
                return

        elif len(args) == 1:
            try:
                dt = datetime.datetime.strptime(args[0], "%m.%Y")
                start_date = dt.date().replace(day=1)
                if dt.month == 12:
                    end_date = datetime.date(dt.year + 1, 1, 1) - datetime.timedelta(days=1)
                else:
                    end_date = datetime.date(dt.year, dt.month + 1, 1) - datetime.timedelta(days=1)
                period_title = f"за {args[0]}"
            except ValueError:
                bot.reply_to(message, "❌ Формат месяца: `/stats 08.2026`", parse_mode="Markdown")
                return

        else:
            start_date = now.date().replace(day=1)
            if now.month == 12:
                end_date = datetime.date(now.year + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.date(now.year, now.month + 1, 1) - datetime.timedelta(days=1)
            period_title = f"за текущий месяц ({now.strftime('%m.%Y')})"

        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        rows = worksheet.get_all_values()
        
        if not rows or len(rows) < 2:
            bot.reply_to(message, "ℹ️ Таблица пуста.")
            return

        headers = [h.strip().lower() for h in rows[0]]
        
        def get_idx(name):
            for i, h in enumerate(headers):
                if name in h:
                    return i
            return -1

        date_idx = get_idx('дата')
        name_idx = get_idx('имя')
        cat_idx = get_idx('категор')
        sum_idx = get_idx('сумм')
        type_idx = get_idx('тип')

        total_income = 0.0
        total_expense = 0.0
        user_totals = {}
        category_totals = {}
        
        for row in rows[1:]:
            if not row or len(row) <= max(date_idx, sum_idx):
                continue
                
            date_raw = row[date_idx].strip() if date_idx != -1 else ''
            if not date_raw:
                continue
                
            try:
                row_date = datetime.datetime.strptime(date_raw.split()[0], "%Y-%m-%d").date()
            except ValueError:
                continue

            if start_date <= row_date <= end_date:
                raw_sum = row[sum_idx].strip().replace('\xa0', '').replace(' ', '').replace(',', '.') if sum_idx != -1 else '0'
                try:
                    amount = float(raw_sum)
                except ValueError:
                    amount = 0.0

                user = row[name_idx].strip() if name_idx != -1 and len(row) > name_idx else 'Неизвестный'
                category = row[cat_idx].strip().capitalize() if cat_idx != -1 and len(row) > cat_idx else 'Другое'
                if not category:
                    category = 'Другое'
                
                entry_type = row[type_idx].strip() if type_idx != -1 and len(row) > type_idx else 'Расход'
                
                if entry_type == 'Доход':
                    total_income += amount
                else:
                    total_expense += amount
                    user_totals[user] = user_totals.get(user, 0.0) + amount
                    category_totals[category] = category_totals.get(category, 0.0) + amount
                
        report = f"📊 **Отчет {period_title}:**\n\n"
        report += f"💵 **Доходы:** +{total_income:,.2f} грн\n"
        report += f"💸 **Расходы:** -{total_expense:,.2f} грн\n"
        report += f"⚖️ **Баланс:** {total_income - total_expense:,.2f} грн\n\n"
        
        if category_totals:
            report += "**Расходы по категориям:**\n"
            for cat, amt in category_totals.items():
                report += f"• {cat}: {amt:,.2f} грн\n"
            report += "\n"
            
        if user_totals:
            report += "**Расходы по людям:**\n"
            for usr, amt in user_totals.items():
                report += f"👤 {usr}: {amt:,.2f} грн\n"
                
        if not category_totals and total_income == 0:
            report += "ℹ️ За выбранный период записей не найдено."
            
        bot.reply_to(message, report, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении статистики: {e}")

@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    if not is_allowed(message):
        return
        
    text = message.text.strip()
    match = re.match(r"^([a-zA-яА-яЕёІіЇїЄє\s]+)\s+(\+)?(\d+(?:[\.,]\d+)?)$", text)
    
    if match:
        category = match.group(1).strip()
        is_income = bool(match.group(2))
        amount = float(match.group(3).replace(',', '.'))
        user_name = message.from_user.first_name or "Пользователь"
        date_today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        entry_type = "Доход" if is_income else "Расход"
        
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.sheet1
            worksheet.append_row([date_today, user_name, category, amount, entry_type])
            
            icon = "💵 Доход" if is_income else "💸 Расход"
            bot.reply_to(
                message, 
                f"Записано! ✅\n"
                f"Тип: {icon}\n"
                f"👤 {user_name}\n"
                f"📂 {category.capitalize()}: {amount:,.2f} грн"
            )
        except Exception as e:
            bot.reply_to(message, f"Ошибка сохранения в таблицу: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.polling(none_stop=True)
