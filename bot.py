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
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 База клиентов",
                    callback_data="clients"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Система поиска клиентов",
                    callback_data="search_system"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎁 Бесплатно",
                    callback_data="free"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛍 Мои покупки",
                    callback_data="purchases"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Поддержка",
                    callback_data="support"
                )
            ],
        ]
    )


# ==========================================
# МЕНЮ ПРОФЕССИЙ
# ==========================================

def professions_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎨 Дизайнер",
                    callback_data="profession_designer"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 SMM",
                    callback_data="profession_smm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Таргетолог",
                    callback_data="profession_target"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📈 Маркетолог",
                    callback_data="profession_marketer"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✍️ Копирайтер",
                    callback_data="profession_copywriter"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Главное меню",
                    callback_data="main_menu"
                )
            ],
        ]
    )


# ==========================================
# МЕНЮ ТАРИФОВ
# ==========================================

def tariffs_menu(profession: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 START",
                    callback_data=f"tariff_start_{profession}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔵 PRO",
                    callback_data=f"tariff_pro_{profession}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟣 MAX",
                    callback_data=f"tariff_max_{profession}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К направлениям",
                    callback_data="clients"
                )
            ],
        ]
    )


# ==========================================
# НАЗВАНИЯ ПРОФЕССИЙ
# ==========================================

PROFESSIONS = {
    "designer": "🎨 Дизайнер",
    "smm": "📱 SMM",
    "target": "🎯 Таргетолог",
    "marketer": "📈 Маркетолог",
    "copywriter": "✍️ Копирайтер",
}


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

@dp.callback_query(F.data == "clients")
async def clients_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>👥 База клиентов</b>\n\n"
        "Выберите своё направление:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=professions_menu()
    )


# ==========================================
# ВЫБОР ПРОФЕССИИ
# ==========================================

@dp.callback_query(F.data.startswith("profession_"))
async def profession_handler(callback: CallbackQuery):

    await callback.answer()

    profession_key = callback.data.replace(
        "profession_",
        ""
    )

    profession = PROFESSIONS.get(
        profession_key,
        "Профессия"
    )

    text = (
        f"<b>{profession}</b>\n\n"
        "Выберите тариф с базой клиентов:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=tariffs_menu(profession_key)
    )


# ==========================================
# ТАРИФЫ
# ==========================================

@dp.callback_query(F.data.startswith("tariff_"))
async def tariff_handler(callback: CallbackQuery):

    await callback.answer()

    parts = callback.data.split("_")

    tariff = parts[1]
    profession_key = parts[2]

    profession = PROFESSIONS.get(
        profession_key,
        "Профессия"
    )

    tariff_name = tariff.upper()

    text = (
        f"<b>{profession} — {tariff_name}</b>\n\n"
        "Здесь будет описание тарифа.\n\n"
        "Внутри:\n"
        "• клиентская база\n"
        "• источники заказов\n"
        "• полезные материалы\n\n"
        "<b>Стоимость:</b> скоро\n\n"
        "После подключения оплаты здесь появится "
        "кнопка покупки."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Купить",
                    callback_data=f"buy_{tariff}_{profession_key}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К тарифам",
                    callback_data=f"profession_{profession_key}"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )


# ==========================================
# СИСТЕМА ПОИСКА КЛИЕНТОВ
# ==========================================

@dp.callback_query(F.data == "search_system")
async def search_system_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>📖 Система поиска клиентов</b>\n\n"
        "Пошаговая система поиска клиентов:\n\n"
        "1. Где искать клиентов\n"
        "2. Как находить подходящие заказы\n"
        "3. Как написать первое сообщение\n"
        "4. Как презентовать свои услуги\n"
        "5. Как обсуждать стоимость\n"
        "6. Как работать с возражениями\n"
        "7. Как закрывать клиента на оплату\n\n"
        "Полная система будет добавлена позже."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Главное меню",
                    callback_data="main_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )


# ==========================================
# БЕСПЛАТНО
# ==========================================

@dp.callback_query(F.data == "free")
async def free_handler(callback: CallbackQuery):

    await callback.answer()

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
        "Полная бесплатная версия будет добавлена позже."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Главное меню",
                    callback_data="main_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )


# ==========================================
# МОИ ПОКУПКИ
# ==========================================

@dp.callback_query(F.data == "purchases")
async def purchases_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>🛍 Мои покупки</b>\n\n"
        "У вас пока нет активных покупок.\n\n"
        "После покупки ваши базы будут "
        "отображаться здесь."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Выбрать базу",
                    callback_data="clients"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← Главное меню",
                    callback_data="main_menu"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )


# ==========================================
# ПОДДЕРЖКА
# ==========================================

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>💬 Поддержка</b>\n\n"
        "Если у вас возник вопрос по оплате, "
        "доступу или работе бота — напишите нам.\n\n"
        "Контакт поддержки будет добавлен позже."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Главное меню",
                    callback_data="main_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )


# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>INKLAB — База клиентов</b>\n\n"
        "Находи клиентов. Получай заказы.\n\n"
        "Готовые клиентские базы для "
        "фрилансеров разных направлений.\n\n"
        "Выбери нужный раздел:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu()
    )


# ==========================================
# ПОКУПКА — ПОКА ЗАГЛУШКА
# ==========================================

@dp.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>💳 Покупка</b>\n\n"
        "Система оплаты будет подключена "
        "на следующем этапе.\n\n"
        "После подключения оплаты здесь "
        "появится безопасная форма покупки."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data="clients"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )


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

    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True,
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH,
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    setup_application(
        app,
        dp,
        bot=bot,
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=PORT,
    )

    await site.start()

    logging.info(
        f"INKLAB Web Service запущен на порту {PORT}"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
