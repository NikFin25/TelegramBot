from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_db_session, register_user, User, get_today_schedule, get_two_weeks_schedule, Application
from config import DEAN_IDS

# Для каждого сотрудника деканата храним список message_id,
# чтобы потом подчистить старые сообщения со списком заявок.
DEAN_SENT_MSGS: dict[int, list[int]] = {}

router = Router()
# Состояния подачи заявки. subject — для темы заявки; description — для описания.
class ApplicationForm(StatesGroup):
    subject = State()
    description = State()

# Сценарий добавления мероприятия
class EventCreation(StatesGroup):
    title = State()
    description = State()
    requirements = State()

# Команда /start — регистрация или приветствие
@router.message(Command("start"))
async def start_handler(message: Message):

# Удаляем последние 20 сообщений (по возможности)
    bot = message.bot  # ← получаем объект бота из сообщения
    for i in range(message.message_id - 1, message.message_id - 20, -1):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=i)
        except:
            continue  # просто пропускаем ошибки, если сообщение не удалить

    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

    if user:
        await message.answer(f"С возвращением, {user.full_name}!")
        if user.role == "dean":
            await show_dean_menu(message)
        elif user.role == "admin":
            await show_dean_menu(message)
        else:
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

# Главное меню для деканата
async def show_dean_menu(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Заявки студентов", callback_data="view_requests")
    builder.button(text="📣 Добавить мероприятие", callback_data="add_event")
    builder.button(text="🎉 Мероприятия", callback_data="admin_events")

    builder.adjust(1)
    await message.answer("📋 Главное меню (Деканат)", reply_markup=builder.as_markup())

# Главное меню для студента
async def show_main_menu(message: Message):
    builder = InlineKeyboardBuilder()
    

    builder.button(text="📅 Сегодня", callback_data="today_schedule")
    builder.button(text="📅 Расписание на 2 недели", callback_data="two_weeks_schedule")
    builder.button(text="🎉 Мероприятия", callback_data="view_events")
    builder.button(text="✉ Заявка в деканат", callback_data="dean_application")
    builder.button(text="📥 Мои заявки", callback_data="my_requests")
    builder.button(text="🗑 Удалить аккаунт", callback_data="delete_account")

    # Расположение кнопок 
    builder.adjust(1)

    await message.answer("📋 Главное меню", reply_markup=builder.as_markup())

# Заявка в деканат студент
@router.callback_query(F.data == "dean_application")
async def start_application(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Введите <b>тему</b> вашей заявки:")
    await state.set_state(ApplicationForm.subject)

# Обработка ввода темы заявки
@router.message(ApplicationForm.subject)
async def receive_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await message.answer("✏ Теперь введите <b>описание</b> вашей заявки или напишите «-», если без описания:")
    await state.set_state(ApplicationForm.description)

@router.message(ApplicationForm.description)
async def receive_description(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    description = message.text if message.text.strip() != "-" else ""

    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

    if user:
        from database.db import Application
        full_name = user.full_name
        group = user.group.name if user.group else "Группа не указана"

        content = (
            f"📩 <b>Новая заявка от студента</b>\n"
            f"👤 <b>ФИО:</b> {full_name}\n"
            f"🏫 <b>Группа:</b> {group}\n\n"
            f"📌 <b>Тема:</b> {subject}\n"
            f"📝 <b>Описание:</b> {description or '—'}"
        )

        new_app = Application(
            user_id=user.id,
            content=content
        )
        session.add(new_app)
        session.commit()
        await message.answer("✅ Ваша заявка была отправлена в деканат.")
    else:
        await message.answer("❌ Не удалось отправить заявку. Пользователь не найден.")

    await state.clear()
    session.close()

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_status_buttons(app_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принята", callback_data=f"status_accept_{app_id}"),
            InlineKeyboardButton(text="🚧 В процессе", callback_data=f"status_process_{app_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отклонена", callback_data=f"status_reject_{app_id}"),
            InlineKeyboardButton(text="✅ Выполнена", callback_data=f"status_done_{app_id}")
        ]
    ])

# Просмотр заявки студента деканом
@router.callback_query(F.data == "view_requests")
async def view_requests(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    dean_id = callback.from_user.id

    # 1) Удаляем старые сообщения, если они были
    old_ids = DEAN_SENT_MSGS.get(dean_id, [])
    for mid in old_ids:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass  # сообщение уже удалено или устарело
    DEAN_SENT_MSGS[dean_id] = []  # очищаем список

    # 2) Показываем актуальные заявки
    session = get_db_session()
    apps = session.query(Application).all()

    if not apps:
        # Используем edit_text, чтобы «переписать» меню-сообщение
        await callback.message.edit_text("❌ Нет заявок.")
        await show_dean_menu(callback.message)
        session.close()
        return

    for app in apps:
        user = app.user
        msg = await callback.message.answer(
            text=(
                f"👤 <b>{user.full_name}</b> — "
                f"<a href='tg://user?id={user.telegram_id}'>[написать]</a>\n"
                f"📄 Заявка: {app.content}\n"
                f"📅 Дата: {app.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📊 Статус: {app.status}"
            ),
            reply_markup=get_status_buttons(app.id)
        )
        DEAN_SENT_MSGS[dean_id].append(msg.message_id)  # запоминаем id

    # 3) Показываем меню снова (в конце списка)
    await show_dean_menu(callback.message)
    session.close()

@router.callback_query(F.data.startswith("status_"))
async def change_status(callback: CallbackQuery):
    session = get_db_session()

    try:
        _, action, app_id = callback.data.split("_")
        app_id = int(app_id)

        status_map = {
            "accept": "Принята",
            "process": "В процессе",
            "reject": "Отклонена",
            "done": "Выполнена"
        }

        new_status = status_map.get(action)
        if not new_status:
            await callback.answer("❌ Неизвестный статус")
            return

        app = session.query(Application).filter_by(id=app_id).first()
        if not app:
            await callback.answer("❌ Заявка не найдена")
            return

        app.status = new_status
        session.commit()

        await callback.answer(f"✅ Статус изменён на «{new_status}»")

        # Уведомляем студента
        await callback.bot.send_message(
            chat_id=app.user.telegram_id,
            text=(
                f"📢 Ваша заявка обновлена!\n\n"
                f"{app.content}\n\n"
                f"📊 Новый статус: <b>{new_status}</b>"
            )
        )

    except Exception as e:
        print("Ошибка при изменении статуса:", e)
        await callback.answer("❌ Ошибка изменения статуса")
    finally:
        session.close()

#Список мероприятий для деканата
@router.callback_query(F.data == "admin_events")
async def admin_events(callback: CallbackQuery):
    session = get_db_session()
    events = session.query(Event).order_by(Event.created_at.desc()).all()

    if not events:
        await callback.message.edit_text("❌ Мероприятий нет.")
        await show_dean_menu(callback.message)
        session.close()
        return

    await callback.message.delete()

    for event in events:
        status = "🟢 Активно" if event.is_active else "⚪ Завершено"

        builder = InlineKeyboardBuilder()
        builder.button(text="📋 Участники", callback_data=f"event_participants_{event.id}")
        if event.is_active:
            builder.button(text="🗑 Удалить", callback_data=f"delete_event_{event.id}")

        await callback.message.answer(
            text=(
                f"🎉 <b>{event.title}</b>\n"
                f"📝 <b>Описание:</b> {event.description}\n"
                f"📎 <b>Требования:</b> {event.requirements}\n"
                f"📅 <b>Создано:</b> {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{status}"
            ),
            reply_markup=builder.as_markup()
        )

    await show_dean_menu(callback.message)
    session.close()


#Удаление мероприятий деканатом
@router.callback_query(F.data.startswith("delete_event_"))
async def delete_event(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    session = get_db_session()

    event = session.query(Event).filter_by(id=event_id).first()
    if not event:
        await callback.answer("❌ Мероприятие не найдено.")
    else:
        event.is_active = 0
        session.commit()
        await callback.answer("✅ Мероприятие завершено (удалено).")
        await callback.message.edit_reply_markup(reply_markup=None)

    session.close()

#Список участников мероприятия 
@router.callback_query(F.data.startswith("event_participants_"))
async def show_event_participants(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    session = get_db_session()

    event = session.query(Event).filter_by(id=event_id).first()
    participants = session.query(EventParticipant).filter_by(event_id=event_id).all()

    if not participants:
        await callback.answer("❌ Пока никто не записался.")
        session.close()
        return

    await callback.message.answer(f"👥 Участники мероприятия: <b>{event.title}</b>")

    for p in participants:
        user = p.user
        await callback.message.answer(
            f"👤 <b>{user.full_name}</b>\n"
            f"🏫 Группа: {user.group.name if user.group else '—'}\n"
            f"📅 Записан: {p.registered_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"<a href='tg://user?id={user.telegram_id}'>[написать]</a>"
        )

    session.close()


@router.callback_query(F.data == "add_event")
async def start_event_creation(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📌 Введите <b>тему мероприятия</b>:")
    await state.set_state(EventCreation.title)

@router.message(EventCreation.title)
async def get_event_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("✏ Введите <b>описание мероприятия</b>:")
    await state.set_state(EventCreation.description)

@router.message(EventCreation.description)
async def get_event_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("📎 Введите <b>требования</b> или '-' если их нет:")
    await state.set_state(EventCreation.requirements)

from database.db import create_event 

@router.message(EventCreation.requirements)
async def get_event_requirements(message: Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title")
    description = data.get("description")
    requirements = message.text if message.text.strip() != "-" else "—"

    result = create_event(title, description, requirements)

    if result:
        await message.answer("✅ Мероприятие успешно создано и доступно студентам.")
    else:
        await message.answer("❌ Ошибка при создании мероприятия.")

    await state.clear()
    await show_dean_menu(message)

#Просмотр мероприятий студентом
from database.db import get_db_session, Event, EventParticipant, register_for_event

@router.callback_query(F.data == "view_events")
async def view_events(callback: CallbackQuery):
    session = get_db_session()
    events = session.query(Event).filter_by(is_active=1).all()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    if not events:
        await callback.message.edit_text("❌ Сейчас нет активных мероприятий.")
        session.close()
        return

    await callback.message.delete()  # очищаем меню

    for event in events:
        # Проверка: записан ли пользователь
        already_registered = session.query(EventParticipant).filter_by(
            user_id=user.id, event_id=event.id
        ).first()

        button_text = "✅ Вы уже записаны" if already_registered else "📥 Записаться"
        button_state = "disabled" if already_registered else f"register_event_{event.id}"

        builder = InlineKeyboardBuilder()
        if not already_registered:
            builder.button(text=button_text, callback_data=button_state)

        await callback.message.answer(
            text=(
                f"🎉 <b>{event.title}</b>\n"
                f"📝 <b>Описание:</b> {event.description}\n"
                f"📎 <b>Требования:</b> {event.requirements}"
            ),
            reply_markup=builder.as_markup() if not already_registered else None
        )

    await show_main_menu(callback.message)
    session.close()

#Записаться на мероприятие студенту
@router.callback_query(F.data.startswith("register_event_"))
async def register_event(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    # Уже записан?
    already = session.query(EventParticipant).filter_by(user_id=user.id, event_id=event_id).first()
    if already:
        await callback.answer("Вы уже записаны на это мероприятие.")
        session.close()
        return

    # Пытаемся зарегистрировать
    success = register_for_event(user.id, event_id)
    if success:
        await callback.answer("✅ Вы успешно записались!")
        await callback.message.edit_reply_markup(reply_markup=None)
    else:
        await callback.answer("❌ Не удалось записаться.")

    session.close()


# Обработка кнопки "Сегодня"
@router.callback_query(F.data == "today_schedule")
async def today_schedule(callback: CallbackQuery):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    if user:
        # Получаем расписание на сегодня через связанную группу
        schedule = get_today_schedule(user.group.name)  # Используем user.group.name
        print("Тип schedule ДО форматирования:", type(schedule))
        if schedule:
            formatted = format_schedule(schedule)
            print("Тип schedule ПОСЛЕ форматирования:", type(formatted))
            await callback.message.edit_text(f"📅 <b>Расписание на сегодня:</b>\n{formatted}")  # Функция get_today_schedule уже возвращает форматированный текст
        else:
            await callback.message.edit_text("❌ На сегодня нет занятий.")
    await show_main_menu(callback.message)
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
    await show_main_menu(callback.message)
    session.close()

# Просмотр собственных заявок студентом
@router.callback_query(F.data == "my_requests")
async def my_requests(callback: CallbackQuery):
    session = get_db_session()
    user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()

    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        session.close()
        return

    applications = session.query(Application).filter_by(user_id=user.id).all()

    if not applications:
        await callback.message.edit_text("❌ У вас пока нет заявок.")
    else:
        # Показываем каждую заявку отдельным сообщением
        for app in applications:
            await callback.message.answer(
                text=(
                    f"📄 Заявка: {app.content}\n"
                    f"📅 Дата: {app.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📊 Статус: {app.status}"
                )
            )

    # Возвращаемся в меню
    await show_main_menu(callback.message)
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