from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    
    keyboard.add(KeyboardButton("🔄 Купить"), KeyboardButton("📉 Продать"))
    
    keyboard.add(KeyboardButton("🤝 Реферальная программа"))
    
    keyboard.add(KeyboardButton("💻 Личный Кабинет"), KeyboardButton("📱 Контакты"))
    
    return keyboard
