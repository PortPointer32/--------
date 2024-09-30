import asyncio
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from database import get_tokens, delete_token
from handlers import register_handlers
from aiogram.utils.exceptions import BotBlocked, BotKicked, ChatNotFound, UserDeactivated, TelegramAPIError, Unauthorized

async def start_bot(token):
    try:
        bot = Bot(token)
        dp = Dispatcher(bot, storage=MemoryStorage())
        dp.middleware.setup(LoggingMiddleware())
        await register_handlers(dp, bot_token=token)
        await dp.start_polling()
    except (BotBlocked, BotKicked, ChatNotFound, UserDeactivated, TelegramAPIError, Unauthorized) as e:
        print(f"Ошибка запуска бота с токеном {token}: {e}")
        delete_token(token)

async def run_bot():
    tokens = get_tokens()
    await asyncio.gather(*(start_bot(token) for token, _ in tokens))

if __name__ == "__main__":
    asyncio.run(run_bot())