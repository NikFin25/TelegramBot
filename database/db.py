# db.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()

# Модель группы
class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)  # Название группы, например: "21-СПО-ИСиП-02"

    users = relationship("User", back_populates="group")  # Связь: группа → список пользователей

# Модель пользователя
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)  # ID пользователя в Telegram
    full_name = Column(String(100))             # ФИО
    group_id = Column(Integer, ForeignKey('groups.id'))  # Внешний ключ на группу

    group = relationship("Group", back_populates="users")  # Связь: пользователь → группа

# Подключение к SQLite-базе
engine = create_engine('sqlite:///database/bot_database.db')

# Создание таблиц, если они ещё не существуют
Base.metadata.create_all(engine)

# Создание сессии для работы с БД
Session = sessionmaker(bind=engine)

def get_db_session():
    return Session()

def get_or_create_group(session, group_name: str):
    """Ищет или создаёт новую группу"""
    group = session.query(Group).filter_by(name=group_name).first()
    if not group:
        group = Group(name=group_name)
        session.add(group)
        session.commit()
    return group

def register_user(telegram_id: int, full_name: str, group_name: str):
    """Создание нового пользователя с привязкой к группе"""
    session = get_db_session()
    try:
        group = get_or_create_group(session, group_name)

        # Проверка: если пользователь уже зарегистрирован — не создаём заново
        existing = session.query(User).filter_by(telegram_id=telegram_id).first()
        if existing:
            return False

        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            group=group  # связываем напрямую объект Group
        )
        session.add(user)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Ошибка при регистрации: {e}")
        return False
    finally:
        session.close()
