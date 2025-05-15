# db.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()

# Модель группы
class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)  # Название группы, например: "21-СПО-ИСиП-02"

    users = relationship("User", back_populates="group")  # Связь: группа → список пользователей
    schedule = relationship("Schedule", back_populates="group") # Связь: группа → расписание

# Модель пользователя
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)  # ID пользователя в Telegram
    full_name = Column(String(100))             # ФИО
    group_id = Column(Integer, ForeignKey('groups.id'))  # Внешний ключ на группу

    group = relationship("Group", back_populates="users")  # Связь: пользователь → группа
    applications = relationship("Application", back_populates="user")

# Модель расписания
class Schedule(Base):
    __tablename__ = 'schedule'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('groups.id'))  # Внешний ключ на группу
    subject = Column(String(100))  # Название предмета
    teacher = Column(String(100))  # Преподаватель
    day_of_week = Column(String(20))  # День недели
    time = Column(String(20))  # Время пары (например, "08:00-09:30")
    room = Column(String(50))  # Аудитория
    week_number = Column(Integer) 

    group = relationship("Group", back_populates="schedule")

# Модель заявки в декан
class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    status = Column(String, default="Новая")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="applications")

    User.applications = relationship("Application", back_populates="user")

# Модель мероприятия
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)  # 1 — активно, 0 — удалено/завершено
    created_at = Column(DateTime, default=datetime.utcnow)

    participants = relationship("EventParticipant", back_populates="event")

# Модель участника мероприятия
class EventParticipant(Base):
    __tablename__ = "event_participants"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    registered_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="participants")
    user = relationship("User")  # связь с таблицей users

# Подключение к SQLite-базе
engine = create_engine('sqlite:///database/bot_database.db')

# Создание таблиц, если они ещё не существуют
Base.metadata.create_all(engine)

# Создание сессии для работы с БД
Session = sessionmaker(bind=engine)

def get_db_session():
    return Session()

def get_today_schedule(group_name: str):
    session = Session()
    today = datetime.today().strftime('%A').upper()  # Получаем день недели
    current_week = get_current_week_number()
    
    today_schedule = session.query(Schedule).join(Group).filter(
        Group.name == group_name,
        Schedule.day_of_week == today,
        Schedule.week_number == current_week
    ).all()

    if not today_schedule:
        session.close()
        return None

    # Формируем структуру, которую ожидает student.py
    result = {
        today: [{
            'time': item.time,
            'subject': item.subject,
            'auditorium': item.room,
            'teacher': item.teacher,
            'week_number': item.week_number
        } for item in today_schedule]
    }

    session.close()
    return result if today_schedule else "❌ На сегодня нет занятий."

def get_two_weeks_schedule(group_name: str):
    session = Session()
    # Порядок дней недели для сортировки
    day_order = {
        'MONDAY': 1,
        'TUESDAY': 2,
        'WEDNESDAY': 3,
        'THURSDAY': 4,
        'FRIDAY': 5,
        'SATURDAY': 6,
        'SUNDAY': 7
    }
    
    schedule = session.query(Schedule).join(Group).filter(
        Group.name == group_name
    ).all()

    if not schedule:
        session.close()
        return None

    # Создаем структуру: {неделя: {день: [пары]}}
    result = {}
    for item in schedule:
        week_key = f"Неделя {item.week_number}"
        if week_key not in result:
            result[week_key] = {}
        
        if item.day_of_week not in result[week_key]:
            result[week_key][item.day_of_week] = []
        
        result[week_key][item.day_of_week].append({
            'time': item.time,
            'subject': item.subject,
            'auditorium': item.room,
            'teacher': item.teacher,
            'day_order': day_order.get(item.day_of_week, 8)  # Добавляем порядковый номер дня
        })
    
    session.close()
    return result

def get_current_week_number():
    # Пример реализации - можно заменить на свою логику определения недели
    # Например, можно считать, что первая неделя - нечётная, вторая - чётная
    current_week = datetime.today().isocalendar()[1]  # Номер недели в году
    return 1 if current_week % 2 else 2

def get_or_create_group(session, group_name: str):
    group_name = group_name.upper()  # Приводим к ВЕРХНЕМУ регистру
    group = session.query(Group).filter_by(name=group_name).first()
    if not group:
        group = Group(name=group_name)
        session.add(group)
        session.commit()
    return group

def register_user(telegram_id: int, full_name: str, group_name: str):
    session = get_db_session()
    group_name = group_name.upper()  # Снова приводим к верхнему регистру
    try:
        group = get_or_create_group(session, group_name)
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            group_id=group.id
        )
        session.add(user)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Ошибка регистрации: {e}")
        return False
    finally:
        session.close()

#Мероприятия
def create_event(title: str, description: str, requirements: str):
    session = get_db_session()
    try:
        new_event = Event(
            title=title,
            description=description,
            requirements=requirements
        )
        session.add(new_event)
        session.commit()
        return new_event
    except Exception as e:
        print("Ошибка при создании мероприятия:", e)
        session.rollback()
        return None
    finally:
        session.close()

def register_for_event(user_id: int, event_id: int):
    session = get_db_session()
    try:
        # Проверка: не записан ли уже
        existing = session.query(EventParticipant).filter_by(user_id=user_id, event_id=event_id).first()
        if existing:
            return False

        new_participant = EventParticipant(user_id=user_id, event_id=event_id)
        session.add(new_participant)
        session.commit()
        return True
    except Exception as e:
        print("Ошибка при записи на мероприятие:", e)
        session.rollback()
        return False
    finally:
        session.close()

