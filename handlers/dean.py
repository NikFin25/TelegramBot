# handlers/dean.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from database.db import get_db_session, Event, Application, EventParticipant, User, create_event

DEAN_SENT_MSGS: dict[int, list[int]] = {}

router = Router()

# Сценарий добавления мероприятия
class EventCreation(StatesGroup):
    title = State()
    description = State()
    requirements = State()

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

async def show_dean_menu(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Заявки студентов", callback_data="view_requests")
    builder.button(text="📣 Добавить мероприятие", callback_data="add_event")
    builder.button(text="🎉 Мероприятия", callback_data="admin_events")
    builder.adjust(1)
    await message.answer("📋 Главное меню (Деканат)", reply_markup=builder.as_markup())

@router.callback_query(F.data == "view_requests")
async def view_requests(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    dean_id = callback.from_user.id

    old_ids = DEAN_SENT_MSGS.get(dean_id, [])
    for mid in old_ids:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    DEAN_SENT_MSGS[dean_id] = []

    session = get_db_session()
    apps = session.query(Application).all()

    if not apps:
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
        DEAN_SENT_MSGS[dean_id].append(msg.message_id)

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
