from .student import router as student_router
from .dean import router as dean_router

def register_handlers(dp):
    dp.include_router(student_router)
    dp.include_router(dean_router)