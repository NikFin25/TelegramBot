# bot.py
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from database.db import get_db_session, register_user, User

# Включаем логгирование — полезно при отладке
logging.basicConfig(level=logging.INFO)

# Создаём объект бота и диспетчера
# Создание объекта бота с поддержкой HTML-разметки
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# Хендлер на команду /start
@dp.message(Command("start"))
async def start_handler(message: Message):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

    if user:
        # Пользователь уже зарегистрирован
        await message.answer(f"С возвращением, {user.full_name}!")
    else:
        # Пользователь новый — просим ФИО и группу
        await message.answer(
            "Введите ваше <b>ФИО и группу</b> в формате:\n"
            "<i>Иванов Иван Иванович 21-СПО-ИСиП-02</i>"
        )
    session.close()

@dp.message(F.text.regexp(r'^[А-ЯЁа-яё-]+\s[А-ЯЁа-яё-]+\s[А-ЯЁа-яё-]+\s[\dА-ЯЁа-яё-]+$'))
async def register_user_handler(message: Message):
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer("❌ Неверный формат. Введите ФИО и группу.\n\nПример:\n<b>Иванов Иван Иванович 21-СПО-ИСиП-02</b>", parse_mode="HTML")
        return
    
    full_name = " ".join(parts[:3])
    group_name = " ".join(parts[3:])  # Поддержка сложных названий групп

    print(f"Регистрация: {full_name}, {group_name}")  # Для отладки

    if register_user(message.from_user.id, full_name, group_name):
        await message.answer(
            f"✅ Регистрация успешна!\n"
            f"ФИО: {full_name}\n"
            f"Группа: {group_name}"
        )
    else:
        await message.answer("❌ Ошибка регистрации. Возможно, вы уже зарегистрированы.")

# Функция запуска бота
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

# Точка входа
if __name__ == "__main__":
    asyncio.run(main())
