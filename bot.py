import logging
import asyncio
import pytz
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types, filters
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from robot import database
import aiohttp
from aiohttp import ClientSession
import json
import os
import re
from crypto import periodic_crypto_update
import subprocess
from io import StringIO

logging.basicConfig(level=logging.INFO)

API_TOKEN = '6946781842:AAE98X-uJd3Ps0_CoAT8LeGCr1v8VPV8XpU'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

database.initialize()

class Form(StatesGroup):
    token = State()

class SettingsStates(StatesGroup):
    help_text = State()
    preorder_text = State()
    edit_payment_details = State()
    edit_coefficient = State()

class MailingStates(StatesGroup):
    mailing_text = State()
    mailing_photo = State()
    daily_mailing_time = State()

class ProductAddStates(StatesGroup):
    city = State()
    category = State()
    product_name = State()
    product_description = State()
    product_price = State()
    
async def daily_mailing_task():
    moscow_tz = pytz.timezone('Europe/Moscow')
    while True:
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        now_msk = now_utc.astimezone(moscow_tz)
        mailings = database.get_daily_mailings()
        for mailing in mailings:
            mailing_time = datetime.strptime(mailing[1], "%H:%M").time()
            current_time_msk = now_msk.time()
            if current_time_msk >= mailing_time and (datetime.combine(datetime.today(), current_time_msk) - datetime.combine(datetime.today(), mailing_time)) < timedelta(minutes=1):
                tokens = database.get_tokens()
                for token in tokens:
                    bot_child = Bot(token=token[0])
                    users = database.get_users_by_token(token[0])
                    for user in users:
                        user_id = user[0]
                        try:
                            if mailing[3]:  
                                absolute_photo_path = os.path.abspath(mailing[3])
                                with open(absolute_photo_path, 'rb') as photo_file:
                                    await bot_child.send_photo(user_id, photo=photo_file, caption=mailing[2], parse_mode='HTML')
                            else:
                                await bot_child.send_message(user_id, text=mailing[2], parse_mode='HTML')
                        except Exception as e:
                            logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                        await bot_child.close()
        await asyncio.sleep(60)  

main_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.add(KeyboardButton("➕Добавить Бота"), KeyboardButton("🤖 Текущие Боты"))
main_keyboard.add(KeyboardButton("🧑🏼‍💻Настройки"))

cancel_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
cancel_keyboard.add(KeyboardButton("❌ Отмена"))

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("Привет, я создан для управления твоим Ботом.", reply_markup=main_keyboard)

@dp.message_handler(lambda message: message.text == "➕Добавить Бота", state="*")
async def add_bot(message: types.Message, state: FSMContext):
    await state.finish()  
    await Form.token.set()
    await message.answer("Отправь мне токен бота:", reply_markup=cancel_keyboard)

@dp.message_handler(state=Form.token)
async def process_token(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("Добавление бота отменено.", reply_markup=main_keyboard)
        return

    tokens = message.text.split('\n')
    for token in tokens:
        try:
            temp_bot = Bot(token=token)
            bot_user = await temp_bot.get_me()
            username = bot_user.username
            await temp_bot.close()

            database.add_token(token, username)  # Добавляем токен в базу данных
            await message.answer(f"Бот @{username} успешно добавлен.", reply_markup=main_keyboard)
        except Exception as e:
            await message.answer(f"Ошибка с токеном {token}: {e}", reply_markup=main_keyboard)

    restart_main()
    await state.finish()
    
@dp.message_handler(commands=['delcity'])
async def command_delete_city(message: types.Message):
    city_id = message.get_args()
    if city_id.isdigit():
        database.delete_city(int(city_id))
        await message.reply(f"Город с ID {city_id} и все связанные с ним категории и товары удалены.")
    else:
        await message.reply("Пожалуйста, укажите корректный ID города.")

@dp.message_handler(commands=['delcategory'])
async def command_delete_category(message: types.Message):
    category_id = message.get_args()
    if category_id.isdigit():
        database.delete_category(int(category_id))
        await message.reply(f"Категория с ID {category_id} и все связанные с ней товары удалены.")
    else:
        await message.reply("Пожалуйста, укажите корректный ID категории.")

@dp.message_handler(commands=['delproduct'])
async def command_delete_product(message: types.Message):
    product_id = message.get_args()
    if product_id.isdigit():
        database.delete_product(int(product_id))
        await message.reply(f"Товар с ID {product_id} удален.")
    else:
        await message.reply("Пожалуйста, укажите корректный ID товара.")

@dp.message_handler(lambda message: message.text == "🤖 Текущие Боты", state="*")
async def current_bots(message: types.Message, state: FSMContext):
    await state.finish()
    bots = database.get_tokens()
    bots_info = StringIO()

    for index, bot in enumerate(bots, start=1):
        token, username = bot
        bots_info.write(f"{index}. Юзернейм: @{username}, Токен:\n{token}\n\n")

    bots_info.seek(0)
    await message.answer_document(types.InputFile(bots_info, filename="bots_info.txt"))

@dp.callback_query_handler(filters.Text(startswith="delete_"))
async def delete_bot(callback_query: types.CallbackQuery):
    bot_id = callback_query.data.split('_')[1]
    database.delete_token(bot_id)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id, 
                           "Бот успешно удален, изменения вступят в силу после перезапуска основного скрипта.")
    restart_main()
                           
@dp.message_handler(commands=['delete'])
async def delete_everything(message: types.Message):
    database.clear_database()

    await message.answer("База данных очищена.")

@dp.message_handler(lambda message: message.text == "🧑🏼‍💻Настройки", state="*")
async def settings(message: types.Message, state: FSMContext):
    await state.finish()
    total_users_count = database.get_total_users_count()  

    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(
        InlineKeyboardButton("Помощь", callback_data="edit_help"),
        InlineKeyboardButton("Реквезиты", callback_data="payment"),
        InlineKeyboardButton("Рассылка", callback_data="settings_mailing"),
        InlineKeyboardButton("Ежедневные рассылки", callback_data="daily_mailing_check")
    )
    settings_text = "Выберите, что хотите сделать:\n\nОбщее количество пользователей: " + str(total_users_count)
    await message.answer(settings_text, reply_markup=inline_kb)

@dp.callback_query_handler(lambda c: c.data == 'settings_products')
async def add_product_start(callback_query: types.CallbackQuery):
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await bot.send_message(callback_query.from_user.id, "Введите название города:", reply_markup=markup)
    await ProductAddStates.city.set()

@dp.message_handler(state=ProductAddStates.city, content_types=types.ContentTypes.TEXT)
async def process_city(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['city'] = message.text
    await bot.send_message(message.chat.id, "Введите название категории:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.category, content_types=types.ContentTypes.TEXT)
async def process_category(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['category'] = message.text
    await bot.send_message(message.chat.id, "Введите название товара:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_name, content_types=types.ContentTypes.TEXT)
async def process_product_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['product_name'] = message.text
    await bot.send_message(message.chat.id, "Введите описание товара (или напишите '0', если описания нет):", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_description, content_types=types.ContentTypes.TEXT)
async def process_product_description(message: types.Message, state: FSMContext):
    description = message.text if message.text != '0' else None
    async with state.proxy() as data:
        data['product_description'] = description
    await bot.send_message(message.chat.id, "Введите вес и цену товара в формате *вес:цена(район1, район2)* каждый с новой строки:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_price, content_types=types.ContentTypes.TEXT)
async def process_product_price(message: types.Message, state: FSMContext):
    price_data = message.text
    price_entries = price_data.split('\n')  

    async with state.proxy() as data:
        city_id = database.add_city_if_not_exists(data['city'])
        category_id = database.add_category_if_not_exists(data['category'], city_id)
        product_id = database.add_product(data['product_name'], category_id)

        for entry in price_entries:
            try:
                
                weight_price, districts = entry.split('(')
                weight, price = weight_price.split(':')
                districts = districts.strip(')').replace(' ', '')  
                weight = float(weight.strip())
                price = float(price.strip())
                database.add_product_details(product_id, data['product_description'], weight, price, districts)
            except ValueError as e:
                await message.answer(f"Ошибка при обработке строки '{entry}': {e}")
                return

        await message.answer("Товар успешно добавлен.")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'settings_mailing')
async def mailing_start(callback_query: types.CallbackQuery):
    await bot.send_message(
        callback_query.from_user.id,
        "Введите текст сообщения для рассылки (поддерживается HTML разметка):",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await MailingStates.mailing_text.set()

@dp.message_handler(state=MailingStates.mailing_text, content_types=types.ContentTypes.TEXT)
async def process_mailing_text(message: types.Message, state: FSMContext):
    await state.update_data(mailing_text=message.text)
    skip_photo_button = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="skip_photo"))
    await message.answer("Теперь отправьте фотографию для рассылки или нажмите 'Пропустить'", reply_markup=skip_photo_button)
    await MailingStates.next()

@dp.callback_query_handler(lambda c: c.data == 'skip_photo', state=MailingStates.mailing_photo)
async def skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(mailing_photo=None)
    data = await state.get_data()
    mailing_text = data['mailing_text']
    await bot.send_message(
        callback_query.from_user.id,
        "Вы пропустили добавление фото.\n\n" + mailing_text,
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("🕝 Ежедневная рассылка", callback_data="daily_mailing")
        ).add(InlineKeyboardButton("❌ Отменить", callback_data="cancel")),
        parse_mode='HTML'
    )

@dp.message_handler(content_types=['photo'], state=MailingStates.mailing_photo)
async def process_mailing_photo(message: types.Message, state: FSMContext):
    file_info = await bot.get_file(message.photo[-1].file_id)
    file_url = f'https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}'
    file_name = f"temp_{message.photo[-1].file_id}.jpg"
    await download_file(file_url, file_name)
    await state.update_data(mailing_photo=file_name)
    data = await state.get_data()
    mailing_text = data['mailing_text']
    await message.answer(
        "Все верно?\n\n" + mailing_text,
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("🕝 Ежедневная рассылка", callback_data="daily_mailing")
        ).add(InlineKeyboardButton("❌ Отменить", callback_data="cancel")),
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == 'confirm_send', state=MailingStates.mailing_photo)
async def confirm_and_send_mailing(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mailing_text = data['mailing_text']
    mailing_photo = data.get('mailing_photo')

    tokens = database.get_tokens()
    for token in tokens:
        bot_token = token[0]
        users = database.get_users_by_token(bot_token)
        bot_child = Bot(token=bot_token)

        for user in users:
            user_id = user[0]
            try:
                if mailing_photo:
                    absolute_photo_path = os.path.abspath(mailing_photo)
                    with open(absolute_photo_path, 'rb') as photo_file:
                        await bot_child.send_photo(user_id, photo=photo_file, caption=mailing_text, parse_mode='HTML')
                else:
                    await bot_child.send_message(user_id, text=mailing_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

        await bot_child.close()

    if mailing_photo:
        os.remove(mailing_photo)  

    await bot.answer_callback_query(callback_query.id, "Рассылка выполнена.")
    await state.finish()
   
@dp.callback_query_handler(lambda c: c.data == 'daily_mailing', state=MailingStates.mailing_photo)
async def request_daily_mailing_time(callback_query: CallbackQuery, state: FSMContext):
    await bot.send_message(
        callback_query.from_user.id,
        "Введите время для ежедневной рассылки в формате ЧЧ:ММ (например, 17:00):"
    )
    await MailingStates.daily_mailing_time.set()

@dp.message_handler(state=MailingStates.daily_mailing_time, content_types=types.ContentTypes.TEXT)
async def set_daily_mailing_time(message: Message, state: FSMContext):
    time = message.text

    
    if not re.match(r"^(2[0-3]|[01]?[0-9]):([0-5]?[0-9])$", time):
        await message.reply("Пожалуйста, введите время в правильном формате (например, 17:00).")
        return

    data = await state.get_data()
    mailing_text = data['mailing_text']
    mailing_photo = data.get('mailing_photo', None)
    mailing_photo_path = os.path.abspath(mailing_photo) if mailing_photo else None

    
    database.add_daily_mailing(time, mailing_text, mailing_photo_path)

    await bot.send_message(
        message.chat.id,
        f"Ежедневная рассылка задана на {time}."
    )
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'cancel_mail', state=MailingStates.mailing_text)
async def cancel_mailing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Рассылка отменена.")
    await bot.send_message(callback_query.from_user.id, "Рассылка отменена.")

@dp.callback_query_handler(lambda c: c.data == 'daily_mailing_check')
async def check_daily_mailings(callback_query: types.CallbackQuery):
    mailings = database.get_daily_mailings()
    if not mailings:
        await bot.send_message(callback_query.from_user.id, "Ежедневные рассылки отсутствуют.")
        return

    markup = InlineKeyboardMarkup()
    for mailing in mailings:
        button_text = f"{mailing[1]} - {mailing[2][:10]}..."  
        callback_data = f"view_{mailing[0]}"  
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await bot.send_message(callback_query.from_user.id, "Вот текущие ежедневные рассылки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('view_'))
async def view_daily_mailing(callback_query: types.CallbackQuery):
    mailing_id = int(callback_query.data.split('_')[1])
    mailing = database.get_daily_mailing_by_id(mailing_id)
    
    if not mailing:
        await bot.answer_callback_query(callback_query.id, "Рассылка не найдена.")
        return

    text = f"Текст: {mailing[2]}\nВремя: {mailing[1]}"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑 Удалить", callback_data=f"deletemail_{mailing[0]}"))

    if mailing[3]:
        with open(os.path.abspath(mailing[3]), 'rb') as photo_file:
            await bot.send_photo(callback_query.from_user.id, photo=photo_file, caption=text, reply_markup=markup)
    else:
        await bot.send_message(callback_query.from_user.id, text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('deletemail_'))
async def delete_daily_mailing_handler(callback_query: types.CallbackQuery):
    mailing_id = int(callback_query.data.split('_')[1])
    mailing = database.get_daily_mailing_by_id(mailing_id)

    if mailing and mailing[3]:
        try:
            os.remove(os.path.abspath(mailing[3]))  
        except Exception as e:
            logging.error(f"Ошибка при удалении файла: {e}")

    database.delete_daily_mailing(mailing_id)

    
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

    
    mailings = database.get_daily_mailings()
    if not mailings:
        await bot.send_message(callback_query.from_user.id, "Ежедневные рассылки отсутствуют.")
        return

    markup = InlineKeyboardMarkup()
    for mailing in mailings:
        button_text = f"{mailing[1]} - {mailing[2][:10]}..."  
        callback_data = f"view_{mailing[0]}"  
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await bot.send_message(callback_query.from_user.id, "Вот текущие ежедневные рассылки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'edit_help')
async def edit_help(callback_query: types.CallbackQuery):
    current_text = database.get_help_text()
    await bot.send_message(
        callback_query.from_user.id,
        f"Введите юзернейм для помощи:\n\nТекущий:\n@{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.help_text.set()

@dp.callback_query_handler(lambda c: c.data == 'edit_preorder')
async def edit_preorder(callback_query: types.CallbackQuery):
    current_text = database.get_preorder_text()
    await bot.send_message(
        callback_query.from_user.id,
        f"Введите новый текст для предзаказа:\n\nТекущий:\n{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.preorder_text.set()

@dp.message_handler(state=SettingsStates.help_text)
async def process_new_help_text(message: types.Message, state: FSMContext):
    new_text = message.text

    new_text = new_text.replace('@', '').replace('https://t.me/', '').replace('t.me/', '')

    database.set_help_text(new_text)
    await message.answer("Юзернейм помощи обновлен.")
    await state.finish()

@dp.message_handler(state=SettingsStates.preorder_text)
async def process_new_preorder_text(message: types.Message, state: FSMContext):
    new_text = message.text
    database.set_preorder_text(new_text)
    await message.answer("Текст предзаказа обновлен.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'payment')
async def payment_options(callback_query: types.CallbackQuery):
    inline_kb = InlineKeyboardMarkup()
    inline_kb.add(
        InlineKeyboardButton("Карта", callback_data="edit_card"),
        InlineKeyboardButton("СБП", callback_data="edit_sbp"),
        InlineKeyboardButton("BTC", callback_data="edit_btc"),
        InlineKeyboardButton("Monero", callback_data="edit_xmr"),
        InlineKeyboardButton("LTC", callback_data="edit_ltc"),
        InlineKeyboardButton("USDT", callback_data="edit_usdt")
    )
    await callback_query.message.edit_text(
        "Что вы хотите изменить:",
        reply_markup=inline_kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith('edit_'))
async def edit_payment(callback_query: types.CallbackQuery):
    payment_type = callback_query.data.split('_')[1]
    await SettingsStates.edit_payment_details.set()
    await callback_query.message.answer(
        f"Выберите действие для '{payment_type.upper()}':",
        reply_markup=InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("Изменить реквизиты", callback_data=f"change_details_{payment_type}"),
            InlineKeyboardButton("Изменить коэффициент", callback_data=f"change_coefficient_{payment_type}"),
            InlineKeyboardButton("Отмена", callback_data="cancel")
        )
    )

@dp.callback_query_handler(lambda c: c.data.startswith('change_details_'), state=SettingsStates.edit_payment_details)
async def change_payment_details(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = callback_query.data.split('_')[2]
    await state.update_data(payment_type=payment_type)
    current_details = database.get_payment_details(payment_type)
    await callback_query.message.answer(
        f"Текущие реквизиты для '{payment_type.upper()}':\n{current_details}\n\nВведите новые реквизиты:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )

@dp.callback_query_handler(lambda c: c.data.startswith('change_coefficient_'), state=SettingsStates.edit_payment_details)
async def change_coefficient(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = callback_query.data.split('_')[2]
    await state.update_data(payment_type=payment_type)
    await callback_query.message.answer(
        f"Какой коэффициент для '{payment_type.upper()}' вы хотите изменить?",
        reply_markup=InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("Изменить коэффициент покупки", callback_data=f"change_buy_{payment_type}"),
            InlineKeyboardButton("Изменить коэффициент продажи", callback_data=f"change_sell_{payment_type}"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        )
    )

@dp.callback_query_handler(lambda c: c.data.startswith('change_buy_'), state=SettingsStates.edit_payment_details)
async def change_buy_coefficient(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = callback_query.data.split('_')[2]
    current_buy_coefficient = database.get_buy_coefficient(payment_type)
    await state.update_data(coefficient_type='buy', payment_type=payment_type)
    await callback_query.message.answer(
        f"Текущий коэффициент покупки для '{payment_type.upper()}': {current_buy_coefficient}\n\nВведите новый коэффициент покупки:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )

@dp.callback_query_handler(lambda c: c.data.startswith('change_sell_'), state=SettingsStates.edit_payment_details)
async def change_sell_coefficient(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = callback_query.data.split('_')[2]
    current_sell_coefficient = database.get_sell_coefficient(payment_type)
    await state.update_data(coefficient_type='sell', payment_type=payment_type)
    await callback_query.message.answer(
        f"Текущий коэффициент продажи для '{payment_type.upper()}': {current_sell_coefficient}\n\nВведите новый коэффициент продажи:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )

@dp.message_handler(state=[SettingsStates.edit_payment_details, SettingsStates.edit_coefficient])
async def process_new_details(message: types.Message, state: FSMContext):
    new_value = message.text
    user_data = await state.get_data()
    payment_type = user_data.get('payment_type')
    coefficient_type = user_data.get('coefficient_type')

    if coefficient_type == 'buy':
        database.set_buy_coefficient(payment_type, float(new_value))
        response = f"Коэффициент покупки для '{payment_type.upper()}' успешно обновлен."
    elif coefficient_type == 'sell':
        database.set_sell_coefficient(payment_type, float(new_value))
        response = f"Коэффициент продажи для '{payment_type.upper()}' успешно обновлен."
    else:
        database.set_payment_details(payment_type, new_value)
        response = f"Детали для '{payment_type.upper()}' успешно обновлены."

    await message.answer(response)
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
async def cancel_editing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Редактирование отменено.")
    await bot.send_message(callback_query.from_user.id, "Редактирование отменено.", reply_markup=main_keyboard)

async def download_file(file_url, file_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            if resp.status == 200:
                with open(file_name, 'wb') as f:
                    f.write(await resp.read())

main_process = None

def start_main():
    global main_process

    if main_process is not None:
        main_process.terminate()
        main_process.wait()

    path_to_main_py = os.path.join(os.getcwd(), 'robot', 'main.py')

    main_process = subprocess.Popen(['python3', path_to_main_py], cwd='robot')

def restart_main():
    global main_process

    if main_process is not None:
        main_process.terminate()
        main_process.wait()

    path_to_main_py = os.path.join(os.getcwd(), 'robot', 'main.py')

    main_process = subprocess.Popen(['python3', path_to_main_py], cwd='robot')

async def on_startup(_):
    start_main()
    asyncio.create_task(daily_mailing_task())
    asyncio.create_task(periodic_crypto_update())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
