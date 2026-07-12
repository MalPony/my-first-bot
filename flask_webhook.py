from flask import Flask, request
import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Update

# --- ПОЛУЧАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
TOKEN = os.getenv('BOT_TOKEN')

# --- FSM И БОТ ---
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# --- СОСТОЯНИЯ ---
class Form(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()


# --- КЛАВИАТУРА ---
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пройти опрос 📝", callback_data="start_survey")],
        [InlineKeyboardButton(text="Отменить ❌", callback_data="cancel")]
    ])


# --- ОБРАБОТЧИКИ БОТА ---

@dp.message(CommandStart())
async def process_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! 👋 Я бот-анкетер.\nНажми на кнопку, чтобы я задал тебе пару вопросов.",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data == "start_survey")
async def start_survey(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Form.waiting_for_name)
    await callback.message.answer("Как тебя зовут? 👤")


@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("Опрос отменен. Возвращаемся в начало.", reply_markup=get_main_keyboard())


@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Опрос отменен.", reply_markup=get_main_keyboard())


@dp.message(Form.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.waiting_for_age)
    await message.answer(f"Приятно познакомиться, {message.text}! 😊\nСколько тебе лет?")


@dp.message(Form.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введи число (например, 25). Попробуй еще раз:")
        return
    
    await state.update_data(age=message.text)
    data = await state.get_data()
    
    await message.answer(
        f"Отлично! Я всё запомнил:\n"
        f"👤 Имя: {data['name']}\n"
        f"🎂 Возраст: {data['age']}\n\n"
        f"Спасибо за ответы!",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


@dp.message(StateFilter('*'))
async def dummy_handler(message: Message):
    await message.answer("Я сейчас занят опросом. Напиши /cancel, чтобы отменить, или ответь на мой вопрос.")


# --- FLASK ПРИЛОЖЕНИЕ ---
app = Flask(__name__)

# Создаем event loop ОДИН РАЗ при импорте модуля
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


@app.route('/')
def health_check():
    """Health check для Bothost"""
    return 'OK', 200


@app.route('/health')
def health():
    """Альтернативный health check"""
    return {'status': 'healthy'}, 200


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Этот endpoint принимает POST-запросы от Telegram.
    """
    print("=" * 50)
    print("ПОЛУЧЕН ЗАПРОС НА /webhook")
    print("=" * 50)
    
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            print(f"Получен JSON: {json_string[:200]}...")
            
            # Парсим JSON в объект Update
            update = Update.model_validate(json.loads(json_string))
            print(f"Update распарсен: {update.update_id}")
            
            # Запускаем асинхронную обработку
            print("Запускаем обработку...")
            loop.run_until_complete(dp.feed_update(bot=bot, update=update))
            print("Обработка завершена!")
            
            return 'OK', 200
        except Exception as e:
            print(f"❌ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
            return 'Error', 500
    
    print("❌ Неверный content-type")
    return 'Bad Request', 400


# --- УБИРАЕМ ЗАПУСК GUNICORN ---
# Bothost сам запустит Flask через свой WSGI-сервер
# if __name__ == '__main__':
#     ...
