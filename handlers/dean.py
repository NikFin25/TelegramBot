from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import DEAN_IDS

router = Router()

# Главное меню для деканата
@router.message(F.text == "/start")
async def show_dean_menu(message: Message):
    user_id = message.from_user.id

    # Проверяем, деканат ли это
    if user_id in DEAN_IDS:
        builder = InlineKeyboardBuilder()
        builder.button(text="📥 Заявки студентов", callback_data="view_requests")
        builder.button(text="📣 Добавить мероприятие", callback_data="add_event")
        builder.button(text="📅 Расписание", callback_data="dean_schedule")
        await message.answer("📋 Главное меню (Деканат)", reply_markup=builder.as_markup())
