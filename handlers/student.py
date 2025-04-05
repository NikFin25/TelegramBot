from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_db_session, register_user, User

router = Router()

# Команда /start — регистрация или приветствие
@router.message(Command("start"))
async def start_handler(message: Message):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

    if user:
        await message.answer(f"С возвращением, {user.full_name}!")
        await show_main_menu(message)
    else:
        await message.answer(
            "Введите ваше <b>ФИО и группу</b> в формате:\n"
            "<i>Иванов Иван Иванович 21-СПО-ИСиП-02</i>"
        )
    session.close()

# Обработка ввода ФИО и группы
@router.message(F.text.regexp(r'^[А-ЯЁа-яё-]+\s[А-ЯЁа-яё-]+\s[А-ЯЁа-яё-]+\s[\dА-ЯЁа-яё-]+$'))
async def register_user_handler(message: Message):
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer("❌ Неверный формат. Введите ФИО и группу.\n\nПример:\n<b>Иванов Иван Иванович 21-СПО-ИСиП-02</b>")
        return

    full_name = " ".join(parts[:3])
    group_name = " ".join(parts[3:])

    if register_user(message.from_user.id, full_name, group_name):
        await message.answer(
            f"✅ Регистрация успешна!\n"
            f"ФИО: {full_name}\n"
            f"Группа: {group_name}"
        )
        await show_main_menu(message)
    else:
        await message.answer("❌ Ошибка регистрации. Возможно, вы уже зарегистрированы.")

# Главное меню для студента
async def show_main_menu(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить аккаунт", callback_data="delete_account")
    await message.answer("📋 Главное меню", reply_markup=builder.as_markup())

# Обработка кнопки "Удалить аккаунт"
@router.callback_query(F.data == "delete_account")
async def confirm_delete(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="cancel_delete")
    await callback.message.edit_text("Вы уверены, что хотите удалить аккаунт?", reply_markup=builder.as_markup())

# Отмена удаления — возвращаем в главное меню
@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("❌ Удаление отменено.")
    await show_main_menu(callback.message)

# Подтверждение удаления — удаляем пользователя из базы
@router.callback_query(F.data == "confirm_delete")
async def delete_user(callback: CallbackQuery):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    if user:
        session.delete(user)
        session.commit()
        await callback.message.edit_text("✅ Ваш аккаунт был удалён.")
    else:
        await callback.message.edit_text("❌ Аккаунт не найден.")

    session.close()

# Функция для регистрации этого router в основном боте
def register(dp):
    dp.include_router(router)
