# handlers/admin.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import get_db_session, User, Application, Event
from config import ADMIN_IDS

router = Router()

class FindStudent(StatesGroup):
    query = State()

# =============================
# 1. Главное админ-меню
# =============================
async def show_admin_menu(message: Message):
    """Показывает клавиатуру администратора."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Пользователи", callback_data="admin_users")
    kb.button(text="🔍 Поиск студента", callback_data="admin_find_user")
    kb.button(text="📊 Отчёты", callback_data="admin_stats")
    kb.button(text="🧹 Очистить заявки", callback_data="admin_clear_apps")
    kb.adjust(1)
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=kb.as_markup())


# =============================
# 2. Вход в админ-панель
# =============================
@router.message(Command("admin"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав администратора.")
        return
    await show_admin_menu(message)


# =============================
# 3. Просмотр списка пользователей
# =============================
@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    session = get_db_session()
    users = session.query(User).order_by(User.id).all()
    if not users:
        await callback.answer("Пользователи не найдены.")
        session.close()
        return

    for user in users[:50]:
        kb = InlineKeyboardBuilder()
        kb.button(text="❌ Удалить", callback_data=f"admin_delete_user_{user.id}")
        await callback.message.answer(
            f"👤 <b>{user.full_name}</b> — <a href='tg://user?id={user.telegram_id}'>[написать]</a>\n"
            f"🏫 Группа: {user.group.name if user.group else '—'}\n"
            f"🆔 Telegram ID: <code>{user.telegram_id}</code>",
            reply_markup=kb.as_markup()
        )
    await callback.answer("✅ Список пользователей отправлен.")
    session.close()

@router.callback_query(F.data == "admin_find_user")
async def admin_find_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔎 Введите ФИО, группу или Telegram ID для поиска:")
    await state.set_state(FindStudent.query)

@router.message(FindStudent.query)
async def process_find_student(message: Message, state: FSMContext):
    text = message.text.strip()
    session = get_db_session()

    results = session.query(User).filter(
        (User.full_name.ilike(f"%{text}%")) |
        (User.telegram_id == text if text.isdigit() else False) |
        (User.group.has(name=text.upper()))
    ).all()

    if not results:
        await message.answer("❌ Пользователь не найден.")
    else:
        for user in results[:10]:  # ограничим до 10
            kb = InlineKeyboardBuilder()
            kb.button(text="❌ Удалить", callback_data=f"admin_delete_user_{user.id}")
            await message.answer(
                f"👤 <b>{user.full_name}</b> — <a href='tg://user?id={user.telegram_id}'>[написать]</a>\n"
                f"🏫 Группа: {user.group.name if user.group else '—'}\n"
                f"🆔 Telegram ID: <code>{user.telegram_id}</code>",
                reply_markup=kb.as_markup()
            )

    await state.clear()
    session.close()


# =============================
# 4. Удаление пользователя вручную
# =============================
@router.callback_query(F.data.startswith("admin_delete_user_"))
async def admin_delete_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    session = get_db_session()
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        # Удаляем связанные заявки перед удалением пользователя
        session.query(Application).filter_by(user_id=user.id).delete()
        session.delete(user)
        session.commit()
        await callback.answer("✅ Пользователь удалён.", show_alert=True)
        await callback.message.edit_text("❌ Пользователь удалён.")
    else:
        await callback.answer("❌ Пользователь не найден.")
    session.close()


# =============================
# 5. Статистика проекта
# =============================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    session = get_db_session()
    total_users = session.query(User).count()
    total_apps = session.query(Application).count()
    total_events = session.query(Event).count()
    active_events = session.query(Event).filter_by(is_active=1).count()

    text = (
        "📊 <b>Статистика проекта</b>\n\n"
        f"👨‍🎓 Зарегистрировано студентов: <b>{total_users}</b>\n"
        f"✉ Подано заявок: <b>{total_apps}</b>\n"
        f"🎉 Всего мероприятий: <b>{total_events}</b>\n"
        f"🟢 Активных мероприятий: <b>{active_events}</b>"
    )
    await callback.message.answer(text)
    await callback.answer()
    session.close()


# =============================
# 6. Очистка всех заявок
# =============================
@router.callback_query(F.data == "admin_clear_apps")
async def admin_clear_apps(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="admin_clear_confirm")
    kb.button(text="❌ Отмена", callback_data="admin_clear_cancel")
    kb.adjust(2)
    await callback.message.answer("⚠ Вы действительно хотите удалить <b>ВСЕ</b> заявки?", reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data == "admin_clear_cancel")
async def admin_clear_cancel(callback: CallbackQuery):
    await callback.answer("Очистка отменена.", show_alert=False)
    await show_admin_menu(callback.message)

@router.callback_query(F.data == "admin_clear_confirm")
async def admin_clear_confirm(callback: CallbackQuery):
    session = get_db_session()
    deleted = session.query(Application).delete()
    session.commit()
    session.close()
    await callback.answer(f"✅ Удалено заявок: {deleted}", show_alert=True)
    await show_admin_menu(callback.message)


# =============================
# 7. Сброс всех FSM состояний /admin_reset_all_fsm
# =============================
@router.message(Command("admin_reset_all_fsm"))
async def admin_reset_all_fsm(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав администратора.")
        return

    await state.clear()
    await message.answer("✅ Все FSM-состояния текущего пользователя сброшены.")


# =============================
# 8. Регистрация роутера
# =============================

def register(dp):
    dp.include_router(router)
