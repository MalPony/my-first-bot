import asyncio
import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- НАСТРОЙКА ЛОГОВ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ПОЛУЧАЕМ ТОКЕН ---
TOKEN = os.getenv('BOT_TOKEN')
logger.info(f"🔑 Токен получен: {'ДА' if TOKEN else 'НЕТ'}")

# --- ПОЛУЧАЕМ URL ДЛЯ ВЕБХУКА ---
# Bothost дает нам URL вида https://xxx.bothost.tech
WEBHOOK_HOST = os.getenv('WEBHOOK_URL', 'https://bot-1783861378-1686-botcreater.bothost.tech')
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

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


# --- ВЕБ-СЕРВЕР (AIOHTTP) ---
async def on_startup(bot: Bot):
    """Устанавливает вебхук при старте сервера"""
    logger.info(f"🚀 Устанавливаем webhook на: {WEBHOOK_URL}")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    logger.info("✅ Вебхук установлен!")


async def on_shutdown(bot: Bot):
    """Удаляет вебхук при остановке сервера"""
    logger.info("🛑 Удаляем вебхук...")
    await bot.delete_webhook()
    logger.info("✅ Вебхук удален!")


# --- Health check ---
async def health_check(request):
    """Health check для Bothost"""
    logger.info("📍 Health check запрос получен!")
    return web.Response(text='OK', status=200)


def main():
    """Запуск сервера"""
    # Создаем aiohttp приложение
    app = web.Application()
    
    # Регистрируем health check
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Регистрируем обработчик webhook от aiogram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настраиваем lifecycle (startup/shutdown)
    setup_application(app, dp, bot=bot, on_startup=on_startup, on_shutdown=on_shutdown)
    
    # Запускаем сервер
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 Запускаем aiohttp server на 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == '__main__':
    main()
