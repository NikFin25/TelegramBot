import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Получаем ID из .env и преобразуем их в список int
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
DEAN_IDS = list(map(int, os.getenv("DEAN_IDS", "").split(",")))