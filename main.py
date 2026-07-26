import os
import re
import datetime
import telebot
import gspread

# Берём токен
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8663061397:AAFHdqhcaK2uVfht809n1ESuYTIbrk7FvBc") 

# Ваш ID Google Таблицы
SPREADSHEET_ID = "1-_QYOaap7Hr8aDfuPUgRJYbImzTDCcc2BDR4ZjiRD24"

bot = telebot.TeleBot(BOT_TOKEN)
gc = gspread.service_account(filename="credentials.json")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Привет! Я бот учета трат.\n\n"
        "Отправляй траты в формате:\n"
        "`продукты 500` или `такси 120`\n\n"
        "Команда /stats — отчет за текущий месяц"
    )

@bot.message_handler(commands=['stats'])
def get_stats(message):
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        data = worksheet.get_all_records()
        
        now = datetime.datetime.now()
        current_month = now.strftime("%Y-%m")
        
        total_sum = 0
        user_totals = {}
        category_totals = {}
        
        for row in data:
            date_str = str(row.get('Дата', ''))
            if date_str.startswith(current_month):
                amount = float(row.get('Сумма', 0))
                user = row.get('Имя', 'Неизвестный')
                category = row.get('Категория', 'Другое').capitalize()
                
                total_sum += amount
                user_totals[user] = user_totals.get(user, 0) + amount
                category_totals[category] = category_totals.get(category, 0) + amount
                
        report = f"📊 **Отчет за месяц ({now.strftime('%m.%Y')}):**\n\n"
        report += "**По категориям:**\n"
        for cat, amt in category_totals.items():
            report += f"• {cat}: {amt:,.0f} грн\n"
            
        report += "\n**По людям:**\n"
        for usr, amt in user_totals.items():
            report += f"👤 {usr}: {amt:,.0f} грн\n"
            
        report += f"\n💰 **Всего потрачено:** {total_sum:,.0f} грн"
        
        bot.reply_to(message, report, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка при получении статистики: {e}")

@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    text = message.text.strip()
    match = re.match(r"^([a-zA-яА-яЕёІіЇїЄє\s]+)\s+(\d+(?:[\.,]\d+)?)$", text)
    
    if match:
        category = match.group(1).strip()
        amount = float(match.group(2).replace(',', '.'))
        user_name = message.from_user.first_name or "Пользователь"
        date_today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.sheet1
            worksheet.append_row([date_today, user_name, category, amount])
            
            bot.reply_to(
                message, 
                f"Записано! ✅\n"
                f"👤 {user_name}\n"
                f"📂 {category.capitalize()}: {amount:,.0f} грн"
            )
        except Exception as e:
            bot.reply_to(message, f"Ошибка сохранения в таблицу: {e}")

if __name__ == '__main__':
    bot.polling(none_stop=True)
