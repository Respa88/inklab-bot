import asyncio
import logging
import os
import sys

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)


# ==========================================
# НАСТРОЙКИ
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не найдена")

WEBHOOK_PATH = "/telegram/webhook"

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

if not RENDER_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL не найдена")

WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

PORT = int(os.getenv("PORT", "10000"))


# ==========================================
# БОТ
# ==========================================

dp = Dispatcher()

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)


# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👥 База клиентов"),
            ],
            [
                KeyboardButton(text="📖 Система поиска клиентов"),
            ],
            [
                KeyboardButton(text="🎁 Бесплатно"),
            ],
            [
                KeyboardButton(text="🛍 Мои покупки"),
            ],
            [
                KeyboardButton(text="💬 Поддержка"),
            ],
        ],
        resize_keyboard=True,
    )


# ==========================================
# /START
# ==========================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    text = (
        "<b>INKLAB — База клиентов</b>\n\n"
        "Находи клиентов. Получай заказы.\n\n"
        "Готовые клиентские базы для "
        "фрилансеров разных направлений.\n\n"
        "Выбери нужный раздел:"
    )

    await message.answer(
        text,
        reply_markup=main_menu()
    )


# ==========================================
# БАЗА КЛИЕНТОВ
# ==========================================

@dp.message(F.text == "👥 База клиентов")
async def clients_base_handler(message: Message):

    text = (
        "<b>👥 База клиентов</b>\n\n"
        "Выберите своё направление:"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎨 Дизайнер"),
                KeyboardButton(text="📱 SMM"),
            ],
            [
                KeyboardButton(text="🎯 Таргетолог"),
                KeyboardButton(text="📈 Маркетолог"),
            ],
            [
                KeyboardButton(text="✍️ Копирайтер"),
            ],
            [
                KeyboardButton(text="◀️ Главное меню"),
            ],
        ],
        resize_keyboard=True,
    )

    await message.answer(
        text,
        reply_markup=keyboard
    )


# ==========================================
# ВЫБОР ПРОФЕССИИ
# ==========================================

@dp.message(
    F.text.in_({
        "🎨 Дизайнер",
        "📱 SMM",
        "🎯 Таргетолог",
        "📈 Маркетолог",
        "✍️ Копирайтер",
    })
)
async def profession_handler(message: Message):

    profession = message.text

    text = (
        f"<b>{profession}</b>\n\n"
        "Выберите тариф с базой клиентов:"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🟢 START"),
                KeyboardButton(text="🔵 PRO"),
            ],
            [
                KeyboardButton(text="🟣 MAX"),
            ],
            [
                KeyboardButton(text="◀️ К направлениям"),
            ],
        ],
        resize_keyboard=True,
    )

    await message.answer(
        text,
        reply_markup=keyboard
    )


# ==========================================
# СИСТЕМА ПОИСКА КЛИЕНТОВ
# ==========================================

@dp.message(F.text == "📖 Система поиска клиентов")
async def search_system_handler(message: Message):

    text = (
        "<b>📖 Система поиска клиентов</b>\n\n"
        "Здесь будет пошаговая система:\n\n"
        "1. Где искать клиентов\n"
        "2. Как находить подходящие заказы\n"
        "3. Как написать первое сообщение\n"
        "4. Как презентовать свои услуги\n"
        "5. Как обсуждать стоимость\n"
        "6. Как работать с возражениями\n"
        "7. Как закрывать клиента на оплату\n\n"
        "Полная система скоро будет доступна."
    )

    await message.answer(text)


# ==========================================
# БЕСПЛАТНО
# ==========================================

@dp.message(F.text == "🎁 Бесплатно")
async def free_handler(message: Message):

    text = (
        "<b>🎁 Бесплатно</b>\n\n"
        "Мини-брошюра для тех, "
        "кто хочет начать зарабатывать на фрилансе.\n\n"
        "Внутри:\n"
        "• сколько можно зарабатывать\n"
        "• от чего зависит доход\n"
        "• где искать первых клиентов\n"
        "• зачем нужна клиентская база\n"
        "• как получать больше заказов\n\n"
        "Полная бесплатная версия скоро будет доступна."
    )

    await message.answer(text)


# ==========================================
# МОИ ПОКУПКИ
# ==========================================

@dp.message(F.text == "🛍 Мои покупки")
async def purchases_handler(message: Message):

    text = (
        "<b>🛍 Мои покупки</b>\n\n"
        "У вас пока нет активных покупок.\n\n"
        "Выберите направление в разделе "
        "«База клиентов», чтобы посмотреть тарифы."
    )

    await message.answer(text)


# ==========================================
# ПОДДЕРЖКА
# ==========================================

@dp.message(F.text == "💬 Поддержка")
async def support_handler(message: Message):

    text = (
        "<b>💬 Поддержка</b>\n\n"
        "Если возник вопрос по оплате, "
        "доступу или работе бота — напишите нам.\n\n"
        "Поддержка скоро будет подключена."
    )

    await message.answer(text)


# ==========================================
# НАВИГАЦИЯ
# ==========================================

@dp.message(F.text == "◀️ Главное меню")
async def back_to_main_handler(message: Message):

    await message.answer(
        "<b>INKLAB — База клиентов</b>\n\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu()
    )


@dp.message(F.text == "◀️ К направлениям")
async def back_to_professions_handler(message: Message):

    await clients_base_handler(message)


# ==========================================
# HEALTH CHECK
# ==========================================

async def health_check(request):
    return web.Response(text="INKLAB OK")


# ==========================================
# WEBHOOK
# ==========================================

async def on_startup():

    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
    )

    logging.info(
        f"Webhook установлен: {WEBHOOK_URL}"
    )


async def on_shutdown():

    await bot.delete_webhook()

    await bot.session.close()

    logging.info("Webhook удалён")


# ==========================================
# ЗАПУСК WEB SERVER
# ==========================================

async def main():

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
    )

    app = web.Application()

    # Проверка работоспособности Render
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    # Telegram webhook
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True,
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH,
    )

    # Startup / Shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    setup_application(
        app,
        dp,
        bot=bot,
    )

    logging.info("INKLAB запускается...")

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=PORT,
    )

    await site.start()

    logging.info(
        f"Web server запущен на порту {PORT}"
    )

    # Не даём процессу завершиться
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
