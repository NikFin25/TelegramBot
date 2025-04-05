import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN

# Импортируем регистрацию хендлеров
from handlers import register_handlers

# Включаем логгирование
logging.basicConfig(level=logging.INFO)

# Создаём объект бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")  # HTML разметка в сообщениях
)

# Создаём объект диспетчера
dp = Dispatcher()

async def main():
    # Регистрируем все хендлеры
    register_handlers(dp)

    print("Бот запущен...")
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
