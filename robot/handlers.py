import os
import sys
from aiogram import Dispatcher, types
import keyboards
import database
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.callback_data import CallbackData
import aiohttp
import random
import logging
import json


logging.basicConfig(level=logging.INFO)

class PurchaseState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet_address = State()

class SellState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_details = State()

async def register_handlers(dp: Dispatcher, bot_token):
    @dp.message_handler(commands=['start'], state="*")
    async def send_welcome(message: types.Message, state: FSMContext):
        await state.finish()
        user_id = message.from_user.id
    
        if not database.check_user_exists(user_id, bot_token):
            database.add_user(user_id, bot_token)
    
        script_dir = os.path.dirname(__file__)
        photos_dir = os.path.join(script_dir, '..', 'photos')
        start_image_path_jpg = os.path.join(photos_dir, 'start.jpg')
        start_image_path_png = os.path.join(photos_dir, 'start.png')
    
        if os.path.exists(start_image_path_jpg):
            with open(start_image_path_jpg, 'rb') as photo:
                await message.answer_photo(photo, caption="👻 Ghostbusters\n🕑 Автоматический обмен\n🔄 Litecoin (LTC)\n🔄 Bitcoin (BTC)\n💥Работает 24/7\n👻 Выберите ниже, что Вы хотите:", reply_markup=keyboards.main_keyboard())
        elif os.path.exists(start_image_path_png):
            with open(start_image_path_png, 'rb') as photo:
                await message.answer_photo(photo, caption="👻 Ghostbusters\n🕑 Автоматический обмен\n🔄 Litecoin (LTC)\n🔄 Bitcoin (BTC)\n💥Работает 24/7\n👻 Выберите ниже, что Вы хотите:", reply_markup=keyboards.main_keyboard())
        else:
            await message.answer("👻 Ghostbusters\n🕑 Автоматический обмен\n🔄 Litecoin (LTC)\n🔄 Bitcoin (BTC)\n💥Работает 24/7\n👻 Выберите ниже, что Вы хотите:", reply_markup=keyboards.main_keyboard())
    @dp.message_handler(lambda message: message.text == "💻 Личный Кабинет", state="*")
    async def handle_personal_account(message: types.Message, state: FSMContext):
        await state.finish()
        user_id = message.from_user.id  # ID пользователя
        response_text = (
            f"Ваш уникальный ID: <code>{user_id}</code>\n"
            f"Количество обменов: <i>0</i>\n"
            f"Количество рефералов: <i>0</i>\n"
            f"Реферальный счет: <i>0 RUB</i>\n"
            f"Кешбэк: <i>0 RUB</i>"
        )
        await message.answer(response_text, parse_mode='HTML')
    @dp.message_handler(lambda message: message.text == "📱 Контакты", state="*")
    async def handle_contacts(message: types.Message, state: FSMContext):
        await state.finish()
        support = database.get_help_text()
        support_url = "https://t.me/" + support
        inline_kb = InlineKeyboardMarkup()
        inline_kb.add(InlineKeyboardButton("✉️ Техническая поддержка", url=support_url))
        
        await message.answer("Нажмите на кнопку ниже, чтобы связаться с поддержкой:", reply_markup=inline_kb)

    @dp.message_handler(lambda message: message.text == "🤝 Реферальная программа", state="*")
    async def referral_program(message: types.Message, state: FSMContext):
        await state.finish()
        user_id = message.from_user.id
        bot_username = database.get_bot_username_by_token(bot_token)
    
        if bot_username:
            referral_link = f"https://telegram.me/{bot_username}?start={user_id}"
            response_text = (
                "<b>Приглашайте друзей и получайте процент от каждой сделки Вашего друга.</b>\n\n"
                f"Ваша реферальная ссылка:\n{referral_link}"
            )
            inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("↪️ Вывести средства", callback_data="withdraw_funds"))
            await message.answer(response_text, reply_markup=inline_kb, parse_mode='HTML')
        else:
            await message.answer("😢 Ошибка")
    
    @dp.callback_query_handler(lambda c: c.data == "withdraw_funds")
    async def handle_withdraw_funds(callback_query: types.CallbackQuery):
        await callback_query.answer("⛔️ У вас недостаточно баланса. Минимальная сумма вывода 500 RUB.", show_alert=True)

    @dp.message_handler(lambda message: message.text == "🔄 Купить", state="*")
    async def handle_buy(message: types.Message, state: FSMContext):
        await state.finish()
    
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Bitcoin", callback_data="buy_btc"),
            InlineKeyboardButton("Litecoin", callback_data="buy_ltc"),
            InlineKeyboardButton("Monero", callback_data="buy_xmr")
        ).add(
            InlineKeyboardButton("USDT TRC-20", callback_data="buy_usdt")
        )
        await message.answer("Выберите валюту, которую вы хотите купить:", reply_markup=keyboard)

    @dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
    async def choose_currency(callback_query: types.CallbackQuery, state: FSMContext):
        currency = callback_query.data.split('_')[1]
        await state.update_data(chosen_currency=currency)
    
        if currency == 'usdt':
            prompt = f"💰 Введите нужную сумму в <b>{currency.upper()}</b>:"
        else:
            prompt = f"💰 Введите нужную сумму в <b>{currency.upper()}</b> или в рублях:"
    
        await callback_query.message.edit_text(prompt, parse_mode='HTML')
        await PurchaseState.waiting_for_amount.set()
    
    @dp.message_handler(state=PurchaseState.waiting_for_amount)
    async def process_amount(message: types.Message, state: FSMContext):
        try:
            amount_str = message.text.replace(',', '.')
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
    
            user_data = await state.get_data()
            chosen_currency = user_data['chosen_currency']
            current_price = database.get_crypto_price(chosen_currency)
            purchase_coefficient = database.get_buy_coefficient(chosen_currency)
            purchase_rate = current_price * purchase_coefficient
            amount_in_crypto = 0
    
            min_values = {
                'btc': {'rub': 500, 'crypto': 0.00013528},
                'ltc': {'rub': 500, 'crypto': 0.08170725},
                'xmr': {'rub': 500, 'crypto': 0.03634291},
                'usdt': {'rub': 500, 'crypto': 5}
            }
    
            crypto_thresholds = {
                'btc': 3,
                'ltc': 100,
                'xmr': 100,
                'usdt': 100000
            }
    
            if amount < crypto_thresholds[chosen_currency]:
                amount_to_pay = round(amount * purchase_rate)
                amount_in_crypto = amount
                formatted_purchase_rate = format_price(purchase_rate, chosen_currency)
                await message.answer(
                    f"📉 Курс покупки <b>{chosen_currency.upper()}</b>: {formatted_purchase_rate} RUB.\n\n"
                    f"К оплате: <b>{amount_to_pay} ₽</b>\n"
                    f"Получите: <b>{format_amount(amount, chosen_currency)} {chosen_currency.upper()}</b>",
                    parse_mode='HTML'
                )
            elif amount < min_values[chosen_currency]['rub']:
                await message.answer(
                    f"Минимальное значение: <b>{min_values[chosen_currency]['rub']} RUB</b> или <b>{format_amount(min_values[chosen_currency]['crypto'], chosen_currency)} {chosen_currency.upper()}</b>",
                    parse_mode='HTML'
                )
                return
            else:
                amount_in_crypto = amount / purchase_rate
                amount_to_pay = round(amount)
                formatted_purchase_rate = format_price(purchase_rate, chosen_currency)
                await message.answer(
                    f"📉 Курс покупки <b>{chosen_currency.upper()}</b>: {formatted_purchase_rate} RUB.\n\n"
                    f"К оплате: <b>{amount_to_pay} ₽</b>\n"
                    f"Получите: <b>{format_amount(amount_in_crypto, chosen_currency)} {chosen_currency.upper()}</b>",
                    parse_mode='HTML'
                )
    
            payment_methods_kb = InlineKeyboardMarkup()
            payment_methods_kb.add(InlineKeyboardButton("💳 Карта", callback_data="pay_card"))
            payment_methods_kb.add(InlineKeyboardButton("📱 СБП", callback_data="pay_sbp"))
        
            await message.answer("Выберите способ оплаты:", reply_markup=payment_methods_kb)
            await state.update_data(amount_to_pay=amount_to_pay, amount_in_crypto=amount_in_crypto)
    
        except ValueError:
            await message.answer("⚠️ Пожалуйста, введите корректную сумму.")
    
    @dp.callback_query_handler(lambda c: c.data in ["pay_card", "pay_sbp"], state=PurchaseState.waiting_for_amount)
    async def enter_wallet_address(callback_query: types.CallbackQuery, state: FSMContext):
        user_data = await state.get_data()
        chosen_currency = user_data['chosen_currency']
        payment_type = "card" if callback_query.data == "pay_card" else "sbp"
        await callback_query.message.answer(f"Введите свой {chosen_currency.upper()} адрес:")
        await state.update_data(payment_type=payment_type)
        await PurchaseState.waiting_for_wallet_address.set()
    
    @dp.message_handler(state=PurchaseState.waiting_for_wallet_address)
    async def confirm_payment(message: types.Message, state: FSMContext):
        wallet_address = message.text
        user_data = await state.get_data()
        payment_type = user_data['payment_type']
        chosen_currency = user_data['chosen_currency']
        amount_to_pay = user_data['amount_to_pay']
        amount_in_crypto = user_data['amount_in_crypto']
    
        formatted_amount_in_crypto = format_crypto_amount(amount_in_crypto)
    
        payment_details_raw = database.get_payment_details(payment_type)
        payment_details_list = payment_details_raw.split('\n')
        payment_details = random.choice(payment_details_list)
    
        confirmation_message = (
            f"Перевод на: <b>{'Карту' if payment_type == 'card' else 'СБП'}</b>\n"
            f"Реквизиты: Альфа Банк <code>{payment_details}</code>\n"
            f"Сумма к оплате: <b>{amount_to_pay} RUB</b>\n"
            f"К получению: <b>{formatted_amount_in_crypto} {chosen_currency.upper()}</b>\n"
            f"На кошелек: <b>{wallet_address}</b>\n\n"
            f"⚠️ Внимание: Переводить точную сумму!\n"
            f"🧾 После оплаты нажмите '✅ Я оплатил'\n\n"
            f"<b>⏱ На оплату даётся 20 мин!</b>"
        )
    
        confirmation_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Я оплатил", callback_data="confirm_payment"))
        await message.answer(confirmation_message, reply_markup=confirmation_kb, parse_mode='HTML')
        await state.finish()
    
    @dp.callback_query_handler(lambda c: c.data == "confirm_payment")
    async def payment_confirmed(callback_query: types.CallbackQuery):
        await callback_query.answer("⛔️ Ваша оплата не найдена, попробуйте повторить запрос позже.", show_alert=True)

    @dp.message_handler(lambda message: message.text == "📉 Продать", state="*")
    async def handle_sell(message: types.Message, state: FSMContext):
        await state.finish()
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Bitcoin", callback_data="sell_btc"),
            InlineKeyboardButton("Litecoin", callback_data="sell_ltc")
        ).row(
            InlineKeyboardButton("Monero", callback_data="sell_xmr")
        ).row(
            InlineKeyboardButton("USDT TRC-20", callback_data="sell_usdt")
        )
        await message.answer("Выберите валюту, которую вы хотите продать:", reply_markup=keyboard)
    
    @dp.callback_query_handler(lambda c: c.data.startswith('sell_'))
    async def choose_currency_to_sell(callback_query: types.CallbackQuery, state: FSMContext):
        currency = callback_query.data.split('_')[1]
        await state.update_data(chosen_currency=currency)
        await callback_query.message.edit_text(f"💰 Введите количество <b>{currency.upper()}</b>, которое вы хотите продать:", parse_mode='HTML')
        await SellState.waiting_for_amount.set()
    
    @dp.message_handler(state=SellState.waiting_for_amount)
    async def process_sell_amount(message: types.Message, state: FSMContext):
        try:
            amount_str = message.text.replace(',', '.')
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
    
            user_data = await state.get_data()
            chosen_currency = user_data['chosen_currency']
            current_price = database.get_crypto_price(chosen_currency)
            sell_coefficient = database.get_sell_coefficient(chosen_currency)
            sell_rate = current_price * sell_coefficient
    
            min_values = {
                'btc': {'crypto': 0.00013528},
                'ltc': {'crypto': 0.08170725},
                'xmr': {'crypto': 0.03634291},
                'usdt': {'crypto': 5}
            }
    
            if amount < min_values[chosen_currency]['crypto']:
                await message.answer(
                    f"Минимальное количество для продажи: <b>{format_amount(min_values[chosen_currency]['crypto'], chosen_currency)} {chosen_currency.upper()}</b>",
                    parse_mode='HTML'
                )
                return
    
            amount_in_rub = round(amount * sell_rate)
            formatted_sell_rate = format_price(sell_rate, chosen_currency)
    
            await message.answer(
                f"📉 Курс продажи <b>{chosen_currency.upper()}</b>: {formatted_sell_rate} RUB.\n\n"
                f"К получению: <b>{amount_in_rub} RUB</b>\n"
                f"К переводу: <b>{format_amount(amount, chosen_currency)} {chosen_currency.upper()}</b>",
                parse_mode='HTML'
            )
    
            withdrawal_methods_kb = InlineKeyboardMarkup()
            withdrawal_methods_kb.add(InlineKeyboardButton("💳 На карту", callback_data="withdraw_card"))
            withdrawal_methods_kb.add(InlineKeyboardButton("📱 Через СБП", callback_data="withdraw_sbp"))
    
            await message.answer("Выберите способ вывода:", reply_markup=withdrawal_methods_kb)
            await state.update_data(amount_in_rub=amount_in_rub, amount=amount)
            await SellState.waiting_for_payment_details.set()
    
        except ValueError:
            await message.answer("⚠️ Пожалуйста, введите корректное количество.")
    
    @dp.callback_query_handler(lambda c: c.data in ["withdraw_card", "withdraw_sbp"], state=SellState.waiting_for_payment_details)
    async def enter_payment_details(callback_query: types.CallbackQuery, state: FSMContext):
        withdrawal_method = callback_query.data.split('_')[1]
        prompt = "Введите номер вашей карты:" if withdrawal_method == "card" else "Введите номер вашего счета СБП:"
        await callback_query.message.answer(prompt)
        await state.update_data(withdrawal_method=withdrawal_method)
    
    @dp.message_handler(state=SellState.waiting_for_payment_details)
    async def confirm_withdrawal(message: types.Message, state: FSMContext):
        payment_details = message.text
        user_data = await state.get_data()
        chosen_currency = user_data['chosen_currency']
        amount = user_data['amount']
        amount_in_rub = user_data['amount_in_rub']
        withdrawal_method = user_data['withdrawal_method']
    
        crypto_address_raw = database.get_payment_details(chosen_currency)
        crypto_address_list = crypto_address_raw.split('\n')
        crypto_address = random.choice(crypto_address_list)
        formatted_amount_in_crypto = format_crypto_amount(amount)

        confirmation_message = (
            f"Способ вывода: <b>{'На карту' if withdrawal_method == 'card' else 'Через СБП'}</b>\n"
            f"Реквизиты: <code>{payment_details}</code>\n"
            f"Сумма к выводу: <b>{amount_in_rub} RUB</b>\n"
            f"К переводу: <b>{formatted_amount_in_crypto} {chosen_currency.upper()}</b>\n"
            f"На кошелек: <b>{crypto_address}</b>\n\n"
            f"⚠️ Внимание: Переводить точную сумму!\n"
            f"🧾 После оплаты нажмите '✅ Я оплатил'\n\n"
            f"<b>⏱ На оплату даётся 20 мин!</b>"
        )
    
        confirmation_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Я оплатил", callback_data="confirm_withdrawal"))
        await message.answer(confirmation_message, reply_markup=confirmation_kb, parse_mode='HTML')
        await state.finish()
    
    @dp.callback_query_handler(lambda c: c.data == "confirm_withdrawal")
    async def withdrawal_confirmed(callback_query: types.CallbackQuery):
        await callback_query.answer("⛔️ Ваша заявка на вывод средств обрабатывается, пожалуйста, ожидайте.", show_alert=True)

def format_price(price, currency):
    return str(round(price))

def format_amount(amount, currency):
    return "{:.8f}".format(amount).rstrip('0').rstrip('.')

def format_crypto_amount(amount):
    return ("{:.8f}".format(amount)).rstrip('0').rstrip('.') if amount != int(amount) else str(int(amount))
