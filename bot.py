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


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не найдена")

WEBHOOK_PATH = "/telegram/webhook"

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

if not RENDER_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL не найдена")

WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

PORT = int(os.getenv("PORT", "10000"))


# =========================================================
# БОТ
# =========================================================

dp = Dispatcher()

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)


# =========================================================
# ПРОФЕССИИ
# =========================================================

PROFESSIONS = {
    "designer": {
        "name": "🎨 Дизайнер",
        "title": "База клиентов для дизайнеров",
        "description": (
            "Если ты дизайнер, твоя задача — не только создавать "
            "хороший дизайн, но и постоянно находить людей, которым "
            "нужны твои услуги.\n\n"
            "INKLAB помогает сократить время на поиск клиентов. "
            "Вместо самостоятельного поиска десятков каналов, "
            "чатов и площадок ты получаешь готовую базу источников, "
            "подобранную под дизайнеров.\n\n"
            "В базе будут собраны места, где можно находить "
            "заказы, вакансии и потенциальных клиентов."
        ),
    },

    "smm": {
        "name": "📱 SMM",
        "title": "База клиентов для SMM-специалистов",
        "description": (
            "Для SMM-специалиста постоянный поток клиентов — "
            "одна из главных задач.\n\n"
            "INKLAB собирает в одном месте источники, где можно "
            "находить бизнесы и людей, которым нужны SMM-услуги.\n\n"
            "Ты экономишь время на самостоятельном поиске и "
            "получаешь готовую систему источников для ежедневной работы."
        ),
    },

    "target": {
        "name": "🎯 Таргетолог",
        "title": "База клиентов для таргетологов",
        "description": (
            "Таргетологу постоянно нужны новые проекты и бизнесы, "
            "которым необходимо привлечение клиентов.\n\n"
            "Вместо хаотичного поиска мы собираем источники, "
            "где можно находить потенциальных заказчиков и "
            "актуальные запросы на рекламу.\n\n"
            "База создана для того, чтобы поиск клиентов стал "
            "регулярной частью твоей работы."
        ),
    },

    "marketer": {
        "name": "📈 Маркетолог",
        "title": "База клиентов для маркетологов",
        "description": (
            "Маркетологу важно постоянно находить бизнесы, "
            "которым нужны новые продажи, продвижение и развитие.\n\n"
            "INKLAB собирает источники потенциальных клиентов "
            "в одном месте, чтобы тебе не приходилось каждый раз "
            "начинать поиск с нуля.\n\n"
            "Используй базу как рабочий инструмент для регулярного "
            "поиска новых проектов."
        ),
    },

    "copywriter": {
        "name": "✍️ Копирайтер",
        "title": "База клиентов для копирайтеров",
        "description": (
            "Копирайтеру важно не ждать случайных заказов, "
            "а иметь постоянный список мест для поиска работы.\n\n"
            "В INKLAB будут собраны источники, где появляются "
            "заказы на тексты, контент и другие услуги копирайтеров.\n\n"
            "Получай готовую базу и используй её для регулярного "
            "поиска новых клиентов."
        ),
    },
}


# =========================================================
# ТАРИФЫ
# =========================================================

TARIFFS = {
    "start": {
        "name": "⚡ START",
        "title": "Базовый набор для старта",
        "description": (
            "Подходит тем, кто хочет начать системно искать клиентов.\n\n"
            "<b>Внутри:</b>\n"
            "• основная база источников\n"
            "• Telegram-каналы и чаты\n"
            "• сообщества и площадки\n"
            "• источники с заказами\n"
            "• инструкция по использованию базы"
        ),
    },

    "pro": {
        "name": "🚀 PRO",
        "title": "Расширенная база для регулярного поиска",
        "description": (
            "Для фрилансеров, которые хотят больше источников "
            "и возможностей для поиска новых проектов.\n\n"
            "<b>Внутри:</b>\n"
            "• всё из START\n"
            "• расширенная база источников\n"
            "• дополнительные Telegram-каналы и чаты\n"
            "• дополнительные площадки\n"
            "• источники для холодного поиска\n"
            "• рекомендации по ежедневному поиску\n"
            "• шаблоны первого сообщения клиенту"
        ),
    },

    "max": {
        "name": "👑 MAX",
        "title": "Полная система поиска и продаж",
        "description": (
            "Максимальный набор для тех, кто хочет не просто "
            "искать клиентов, а выстроить полноценную систему.\n\n"
            "<b>Внутри:</b>\n"
            "• всё из PRO\n"
            "• максимальная база источников\n"
            "• система поиска клиентов\n"
            "• система продаж\n"
            "• готовые скрипты сообщений\n"
            "• работа с возражениями\n"
            "• как презентовать свои услуги\n"
            "• как обсуждать стоимость\n"
            "• как закрывать клиента на оплату\n"
            "• система ежедневной работы с базой"
        ),
    },
}


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

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


# =========================================================
# МЕНЮ ПРОФЕССИЙ
# =========================================================

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


# =========================================================
# МЕНЮ ТАРИФОВ
# =========================================================

def tariffs_menu(profession_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ START",
                    callback_data=f"tariff_start_{profession_key}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 PRO",
                    callback_data=f"tariff_pro_{profession_key}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👑 MAX",
                    callback_data=f"tariff_max_{profession_key}"
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


# =========================================================
# МЕНЮ ТАРИФА
# =========================================================

def tariff_detail_menu(
    tariff_key: str,
    profession_key: str
) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Купить",
                    callback_data=f"buy_{tariff_key}_{profession_key}"
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


# =========================================================
# /START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    text = (
        "<b>INKLAB — База клиентов</b>\n\n"
        "Рабочий инструмент для фрилансера, "
        "который хочет стабильно находить новых клиентов "
        "и заказы.\n\n"
        "Вместо того чтобы каждый день тратить часы "
        "на самостоятельный поиск вакансий, чатов, "
        "каналов и площадок, ты получаешь "
        "<b>готовую базу клиентов</b> под свою профессию.\n\n"
        "Внутри — источники, где можно находить:\n"
        "• вакансии и заказы\n"
        "• запросы на услуги\n"
        "• предложения о сотрудничестве\n"
        "• потенциальных клиентов\n\n"
        "Выбираешь своё направление → "
        "получаешь подходящую базу → "
        "используешь её для регулярного поиска клиентов.\n\n"
        "<b>INKLAB создан, чтобы ты тратил меньше времени "
        "на поиск и больше — на работу и заработок.</b>\n\n"
        "Выбери нужный раздел 👇"
    )

    await message.answer(
        text,
        reply_markup=main_menu()
    )


# =========================================================
# БАЗА КЛИЕНТОВ
# =========================================================

@dp.callback_query(F.data == "clients")
async def clients_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>👥 База клиентов</b>\n\n"
        "У каждого направления свои источники заказов "
        "и свои потенциальные клиенты.\n\n"
        "Мы собираем их в отдельные базы, чтобы тебе "
        "не приходилось самостоятельно искать сотни "
        "каналов, чатов и площадок.\n\n"
        "<b>Выбери свою профессию 👇</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=professions_menu()
    )


# =========================================================
# ПРОФЕССИЯ
# =========================================================

@dp.callback_query(F.data.startswith("profession_"))
async def profession_handler(callback: CallbackQuery):

    await callback.answer()

    profession_key = callback.data.replace(
        "profession_",
        ""
    )

    profession = PROFESSIONS.get(profession_key)

    if not profession:
        return

    text = (
        f"<b>{profession['title']}</b>\n\n"
        f"{profession['description']}\n\n"
        "<b>Выбери тариф и получи доступ к базе 👇</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=tariffs_menu(profession_key)
    )


# =========================================================
# ТАРИФ
# =========================================================

@dp.callback_query(F.data.startswith("tariff_"))
async def tariff_handler(callback: CallbackQuery):

    await callback.answer()

    parts = callback.data.split("_")

    if len(parts) != 3:
        return

    tariff_key = parts[1]
    profession_key = parts[2]

    tariff = TARIFFS.get(tariff_key)
    profession = PROFESSIONS.get(profession_key)

    if not tariff or not profession:
        return

    text = (
        f"<b>{tariff['name']}</b>\n"
        f"{profession['name']}\n\n"
        f"<b>{tariff['title']}</b>\n\n"
        f"{tariff['description']}\n\n"
        "<b>Стоимость:</b> будет добавлена\n\n"
        "После подключения оплаты ты сможешь "
        "сразу получить доступ к базе."
    )

    await callback.message.edit_text(
        text,
        reply_markup=tariff_detail_menu(
            tariff_key,
            profession_key
        )
    )


# =========================================================
# ПОКУПКА
# =========================================================

@dp.callback_query(F.data.startswith("buy_"))
async def buy_handler(callback: CallbackQuery):

    await callback.answer()

    parts = callback.data.split("_")

    if len(parts) != 3:
        return

    tariff_key = parts[1]
    profession_key = parts[2]

    tariff = TARIFFS.get(tariff_key)
    profession = PROFESSIONS.get(profession_key)

    if not tariff or not profession:
        return

    text = (
        "<b>💳 Покупка</b>\n\n"
        f"{profession['name']}\n"
        f"{tariff['name']}\n\n"
        "Сейчас система оплаты находится "
        "на этапе подключения.\n\n"
        "После подключения здесь появится "
        "безопасная оплата, после которой "
        "доступ к базе будет выдан автоматически."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Назад",
                    callback_data=f"tariff_{tariff_key}_{profession_key}"
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


# =========================================================
# СИСТЕМА ПОИСКА КЛИЕНТОВ
# =========================================================

@dp.callback_query(F.data == "search_system")
async def search_system_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>📖 Система поиска клиентов</b>\n\n"
        "Пошаговая система, которая поможет "
        "организовать регулярный поиск заказов.\n\n"
        "<b>Внутри:</b>\n\n"
        "1️⃣ Подготовка к поиску\n"
        "2️⃣ Где искать клиентов\n"
        "3️⃣ Как находить подходящие заказы\n"
        "4️⃣ Как написать первое сообщение\n"
        "5️⃣ Как презентовать свои услуги\n"
        "6️⃣ Как обсуждать стоимость\n"
        "7️⃣ Как работать с возражениями\n"
        "8️⃣ Как закрывать клиента на оплату\n\n"
        "Полная система будет добавлена "
        "на следующем этапе."
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


# =========================================================
# БЕСПЛАТНО
# =========================================================

@dp.callback_query(F.data == "free")
async def free_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>🎁 Бесплатно</b>\n\n"
        "<b>Мини-брошюра для фрилансера</b>\n\n"
        "Полезный материал для тех, кто хочет "
        "понять, как устроен заработок на фрилансе "
        "и почему поиск клиентов — одна из главных "
        "задач специалиста.\n\n"
        "<b>Внутри:</b>\n"
        "• сколько можно зарабатывать на фрилансе\n"
        "• от чего зависит доход\n"
        "• где искать первых клиентов\n"
        "• зачем нужна клиентская база\n"
        "• почему нельзя постоянно ждать входящие заявки\n"
        "• как организовать регулярный поиск\n"
        "• как постепенно увеличивать количество заказов\n\n"
        "Полная бесплатная брошюра будет добавлена "
        "на следующем этапе."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Посмотреть базы",
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


# =========================================================
# МОИ ПОКУПКИ
# =========================================================

@dp.callback_query(F.data == "purchases")
async def purchases_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>🛍 Мои покупки</b>\n\n"
        "Здесь будут отображаться все приобретённые "
        "базы и доступы.\n\n"
        "После покупки продукта ты сможешь "
        "открыть свою базу прямо из этого раздела."
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


# =========================================================
# ПОДДЕРЖКА
# =========================================================

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>💬 Поддержка</b>\n\n"
        "Возник вопрос по оплате, доступу "
        "или работе INKLAB?\n\n"
        "Напиши в поддержку — мы поможем "
        "разобраться с вопросом."
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


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):

    await callback.answer()

    text = (
        "<b>INKLAB — База клиентов</b>\n\n"
        "Рабочий инструмент для фрилансера, "
        "который хочет стабильно находить новых клиентов "
        "и заказы.\n\n"
        "Выбери нужный раздел 👇"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu()
    )


# =========================================================
# HEALTH CHECK
# =========================================================

async def health_check(request):
    return web.Response(text="INKLAB OK")


# =========================================================
# WEBHOOK
# =========================================================

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


# =========================================================
# ЗАПУСК
# =========================================================

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


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
