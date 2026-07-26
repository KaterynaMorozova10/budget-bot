import os
import re
import datetime
import json
import telebot
import gspread

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8663061397:AAFHdqhcaK2uVfht809n1ESuYTIbrk7FvBc") 
SPREADSHEET_ID = "1-_QYOaap7Hr8aDfuPUgRJYbImzTDCcc2BDR4ZjiRD24"

bot = telebot.TeleBot(BOT_TOKEN)

creds_json = os.environ.get("GOOGLE_CREDENTIALS")
if creds_json:
    creds_dict = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds_dict)
else:
    gc = gspread.service_account(filename="credentials.json")


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Привет! Я бот учета доходов и трат.\n\n"
        "Запись расходов:\n"
        "`продукты 500` или `такси 120`\n\n"
        "Запись доходов (со знаком +):\n"
        "`зарплата +5000` или `аванс +1000`\n\n"
        "Команда /stats — отчет и баланс за текущий месяц"
    )

@bot.message_handler(commands=['stats'])
def get_stats(message):
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        data = worksheet.get_all_records()
        
        now = datetime.datetime.now()
        current_month = now.strftime("%Y-%m")
        
        total_income = 0
        total_expense = 0
        user_totals = {}
        category_totals = {}
        
        for row in data:
            date_str = str(row.get('Дата', ''))
            if date_str.startswith(current_month):
                amount = float(row.get('Сумма', 0))
                user = row.get('Имя', 'Неизвестный')
                category = row.get('Категория', 'Другое').capitalize()
                entry_type = str(row.get('Тип', 'Расход'))
                
                if entry_type == 'Доход':
                    total_income += amount
                else:
                    total_expense += amount
                    user_totals[user] = user_totals.get(user, 0) + amount
                    category_totals[category] = category_totals.get(category, 0) + amount
                
        report = f"📊 **Отчет за месяц ({now.strftime('%m.%Y')}):**\n\n"
        report += f"💵 **Доходы:** +{total_income:,.0f} грн\n"
        report += f"💸 **Расходы:** -{total_expense:,.0f} грн\n"
        report += f"⚖️ **Баланс:** {total_income - total_expense:,.0f} грн\n\n"
        
        report += "**Расходы по категориям:**\n"
        for cat, amt in category_totals.items():
            report += f"• {cat}: {amt:,.0f} грн\n"
            
        report += "\n**Расходы по людям:**\n"
        for usr, amt in user_totals.items():
            report += f"👤 {usr}: {amt:,.0f} грн\n"
            
        bot.reply_to(message, report, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении статистики: {e}")

@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    text = message.text.strip()
    # Регулярка теперь ищет знак плюс перед суммой (+500 или 500)
    match = re.match(r"^([a-zA-яА-яЕёІіЇїЄє\s]+)\s+(\+)?(\d+(?:[\.,]\d+)?)$", text)
    
    if match:
        category = match.group(1).strip()
        is_income = bool(match.group(2))  # Если был плюс — это доход
        amount = float(match.group(3).replace(',', '.'))
        user_name = message.from_user.first_name or "Пользователь"
        date_today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        entry_type = "Доход" if is_income else "Расход"
        
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.sheet1
            # Записываем: Дата, Имя, Категория, Сумма, Тип
            worksheet.append_row([date_today, user_name, category, amount, entry_type])
            
            icon = "💵 Доход" if is_income else "💸 Расход"
            bot.reply_to(
                message, 
                f"Записано! ✅\n"
                f"Тип: {icon}\n"
                f"👤 {user_name}\n"
                f"📂 {category.capitalize()}: {amount:,.0f} грн"
            )
        except Exception as e:
            bot.reply_to(message, f"Ошибка сохранения в таблицу: {e}")

if __name__ == '__main__':
    bot.polling(none_stop=True)
