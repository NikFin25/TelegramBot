from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_db_session, register_user, User, get_today_schedule, get_two_weeks_schedule

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
    builder.button(text="📅 Сегодня", callback_data="today_schedule")
    builder.button(text="📅 Расписание на 2 недели", callback_data="two_weeks_schedule")
    builder.button(text="🗑 Удалить аккаунт", callback_data="delete_account")
    await message.answer("📋 Главное меню", reply_markup=builder.as_markup())

# Обработка кнопки "Сегодня"
@router.callback_query(F.data == "today_schedule")
async def today_schedule(callback: CallbackQuery):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    if user:
        # Получаем расписание на сегодня через связанную группу
        schedule = get_today_schedule(user.group.name)  # Используем user.group.name
        if schedule:
            await callback.message.edit_text(schedule)  # Функция get_today_schedule уже возвращает форматированный текст
        else:
            await callback.message.edit_text("❌ На сегодня нет занятий.")
    session.close()

# Обработка кнопки "Расписание на 2 недели"
@router.callback_query(F.data == "two_weeks_schedule")
async def two_weeks_schedule(callback: CallbackQuery):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    if user:
        schedule = get_two_weeks_schedule(user.group.name)
        if schedule:
            formatted = format_schedule(schedule, two_weeks=True)
            # Разбиваем длинное сообщение на части, если оно слишком большое
            if len(formatted) > 4000:
                parts = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
                for part in parts:
                    await callback.message.answer(part)
            else:
                await callback.message.edit_text(f"📅 <b>Расписание на 2 недели:</b>\n{formatted}")
        else:
            await callback.message.edit_text("❌ Расписание на две недели не найдено.")
    session.close()

# Функция для формирования расписания в текстовом формате
def format_schedule(schedule, two_weeks=False):
    if not schedule:
        return "Расписание не найдено"
    
    formatted_schedule = ""
    
    if two_weeks:
        # Определяем порядок дней недели
        day_order = {
            'MONDAY': 1,
            'TUESDAY': 2,
            'WEDNESDAY': 3,
            'THURSDAY': 4,
            'FRIDAY': 5,
            'SATURDAY': 6,
            'SUNDAY': 7
        }
        
        # Русские названия дней
        day_names = {
            'MONDAY': 'Понедельник',
            'TUESDAY': 'Вторник',
            'WEDNESDAY': 'Среда',
            'THURSDAY': 'Четверг',
            'FRIDAY': 'Пятница',
            'SATURDAY': 'Суббота',
            'SUNDAY': 'Воскресенье'
        }

        # Форматирование для двух недель
        for week, days in schedule.items():
            formatted_schedule += f"\n📌 <b>{week}:</b>\n"
            
            # Сортируем дни по порядку
            sorted_days = sorted(days.items(), key=lambda x: x[1][0]['day_order'])
            
            for day, classes in sorted_days:
                day_name = day_names.get(day, day)
                formatted_schedule += f"\n<b>📅 {day_name}:</b>\n"
                for class_info in classes:
                    formatted_schedule += (
                        f"🕒 {class_info['time']} - {class_info['subject']}\n"
                        f"   🏫 {class_info['auditorium']} | 👨‍🏫 {class_info['teacher']}\n"
                    )
    else:
        # Форматирование для одного дня (оставляем как было)
        for day, classes in schedule.items():
            formatted_schedule += f"\n<b>📅 {day}:</b>\n"
            for class_info in classes:
                formatted_schedule += (
                    f"🕒 {class_info['time']} - {class_info['subject']}\n"
                    f"   🏫 {class_info['auditorium']} | 👨‍🏫 {class_info['teacher']}\n"
                )
    
    return formatted_schedule
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
