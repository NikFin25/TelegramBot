from . import student  # Здесь можно также добавить admin позже

def register_handlers(dp):
    student.register(dp)
