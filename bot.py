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
    ReplyKeyboardRemove,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не найдена")

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

if not RENDER_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL не найдена")

WEBHOOK_PATH = "/telegram/webhook"
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
    )
)


# =========================================================
# ПРОФЕССИИ
# =========================================================

PROFESSIONS = {

    "designer": {
        "name": "🎨 Дизайнер",
        "title": "База клиентов для дизайнеров",

        "intro": (
            "<b>🎨 Дизайнер</b>\n\n"
            "Ты зашел в раздел базы клиентов для дизайнеров.\n\n"
            "Если ты умеешь создавать дизайн, одна из главных "
            "задач на фрилансе - постоянно находить людей и "
            "бизнесы, которым нужны твои услуги.\n\n"
            "Самая частая проблема фрилансера - не отсутствие "
            "навыков, а отсутствие стабильного потока клиентов.\n\n"
            "Можно часами искать заказы самостоятельно, "
            "перебирать Telegram-чаты, каналы, группы и сайты. "
            "INKLAB создан для того, чтобы сократить это время.\n\n"
            "<b>Ты получаешь готовую базу источников, где "
            "можно искать заказы и потенциальных клиентов.</b>\n\n"
            "Это не означает, что клиенты начнут писать тебе "
            "автоматически. Но у тебя появляется главное - "
            "готовые места для регулярного поиска.\n\n"
            "Чем системнее ты работаешь с базой, тем проще "
            "поддерживать постоянный поток предложений и "
            "новых контактов.\n\n"
            "<b>Не ищи каждый раз с нуля. Используй готовую "
            "систему и направляй время на работу с клиентами.</b>"
        )
    },

    "smm": {
        "name": "📱 SMM",
        "title": "База клиентов для SMM",

        "intro": (
            "<b>📱 SMM</b>\n\n"
            "Ты зашел в раздел базы клиентов для SMM-специалистов.\n\n"
            "Для SMM-специалиста важно не только хорошо вести "
            "социальные сети, но и постоянно находить бизнесы, "
            "которым нужны твои услуги.\n\n"
            "Проблема многих фрилансеров - поиск клиентов "
            "занимает слишком много времени.\n\n"
            "INKLAB собирает источники в одном месте, чтобы "
            "тебе не приходилось самостоятельно искать новые "
            "чаты, каналы, группы и площадки.\n\n"
            "<b>Ты получаешь готовую основу для регулярного "
            "поиска потенциальных клиентов.</b>\n\n"
            "Это не обещание автоматических заказов. "
            "База дает тебе инструменты и источники, "
            "а результат зависит от твоей активности, "
            "предложения и общения с клиентами.\n\n"
            "<b>Твоя задача - регулярно использовать базу "
            "и превращать найденные контакты в реальные сделки.</b>"
        )
    },

    "target": {
        "name": "🎯 Таргетолог",
        "title": "База клиентов для таргетологов",

        "intro": (
            "<b>🎯 Таргетолог</b>\n\n"
            "Ты зашел в раздел базы клиентов для таргетологов.\n\n"
            "Таргетологу постоянно нужны новые проекты и бизнесы, "
            "которым необходимо привлечение клиентов и настройка рекламы.\n\n"
            "Вместо того чтобы каждый день искать источники "
            "самостоятельно, ты получаешь готовую подборку "
            "мест, где можно искать потенциальных заказчиков.\n\n"
            "<b>Главная ценность базы - экономия времени "
            "на поиске источников.</b>\n\n"
            "Ты можешь регулярно открывать базу, находить "
            "подходящие предложения и связываться с потенциальными "
            "клиентами.\n\n"
            "Чем больше качественных контактов ты обрабатываешь "
            "и чем лучше умеешь продавать свои услуги, тем больше "
            "возможностей появляется для получения заказов.\n\n"
            "<b>INKLAB превращает поиск клиентов из хаотичного "
            "занятия в понятный рабочий процесс.</b>"
        )
    },

    "marketer": {
        "name": "📈 Маркетолог",
        "title": "База клиентов для маркетологов",

        "intro": (
            "<b>📈 Маркетолог</b>\n\n"
            "Ты зашел в раздел базы клиентов для маркетологов.\n\n"
            "Маркетологу постоянно приходится искать новые проекты, "
            "бизнесы и компании, которым нужны продвижение, "
            "продажи и развитие.\n\n"
            "Главная проблема - хорошие источники разбросаны "
            "по множеству разных площадок.\n\n"
            "INKLAB помогает собрать этот поиск в одном месте.\n\n"
            "<b>Вместо бесконечного поиска источников ты получаешь "
            "готовую базу для ежедневной работы.</b>\n\n"
            "База не гарантирует получение заказа сама по себе. "
            "Она дает тебе больше возможностей для поиска, "
            "а результат зависит от того, как ты используешь "
            "источники и общаешься с потенциальными клиентами.\n\n"
            "<b>Твоя задача - находить подходящие проекты, "
            "делать сильное предложение и доводить общение "
            "до сделки.</b>"
        )
    },

    "copywriter": {
        "name": "✍️ Копирайтер",
        "title": "База клиентов для копирайтеров",

        "intro": (
            "<b>✍️ Копирайтер</b>\n\n"
            "Ты зашел в раздел базы клиентов для копирайтеров.\n\n"
            "Копирайтеру важно не ждать случайных заказов, "
            "а иметь понятный список источников, где можно "
            "регулярно искать новые проекты.\n\n"
            "INKLAB собирает такие источники в одном месте.\n\n"
            "<b>Ты экономишь время на поиске и получаешь "
            "готовую основу для ежедневной работы.</b>\n\n"
            "В зависимости от тарифа ты получишь разные объемы "
            "источников и дополнительные материалы для поиска "
            "и общения с потенциальными клиентами.\n\n"
            "База сама не гарантирует заказы. Ее задача - "
            "дать тебе больше качественных возможностей для поиска.\n\n"
            "<b>Чем регулярнее ты работаешь с источниками, "
            "тем больше потенциальных клиентов можешь находить.</b>"
        )
    }
}


# =========================================================
# ТАРИФЫ
# =========================================================

TARIFFS = {

    "start": {
        "name": "⚡ START",
        "title": "Базовый набор для старта",

        "description": (
            "<b>⚡ START</b>\n\n"
            "Подойдет, если ты хочешь начать системно искать "
            "клиентов и заказы.\n\n"
            "<b>Что будет внутри:</b>\n"
            "• основная база источников\n"
            "• Telegram-каналы\n"
            "• Telegram-чаты\n"
            "• группы и сообщества\n"
            "• площадки с заказами\n"
            "• инструкция по работе с базой\n\n"
            "<b>Главная задача START</b> - дать тебе все "
            "необходимое для начала регулярного поиска."
        )
    },

    "pro": {
        "name": "🚀 PRO",
        "title": "Расширенная база для регулярного поиска",

        "description": (
            "<b>🚀 PRO</b>\n\n"
            "Для фрилансеров, которые хотят получить больше "
            "источников и возможностей для поиска клиентов.\n\n"
            "<b>Что будет внутри:</b>\n"
            "• все возможности START\n"
            "• расширенная база источников\n"
            "• дополнительные Telegram-каналы\n"
            "• дополнительные Telegram-чаты\n"
            "• дополнительные площадки\n"
            "• источники для холодного поиска\n"
            "• рекомендации по ежедневному поиску\n"
            "• шаблоны первого сообщения клиенту\n\n"
            "<b>Главная задача PRO</b> - дать тебе больше "
            "вариантов для постоянного поиска новых проектов."
        )
    },

    "max": {
        "name": "👑 MAX",
        "title": "Полная система поиска и продаж",

        "description": (
            "<b>👑 MAX</b>\n\n"
            "Максимальный набор для тех, кто хочет использовать "
            "INKLAB не просто как базу, а как полноценный рабочий инструмент.\n\n"
            "<b>Что будет внутри:</b>\n"
            "• все возможности PRO\n"
            "• максимальная база источников\n"
            "• система поиска клиентов\n"
            "• система продаж\n"
            "• готовые скрипты сообщений\n"
            "• как правильно презентовать услуги\n"
            "• как отвечать на возражения\n"
            "• как обсуждать стоимость\n"
            "• как доводить клиента до оплаты\n"
            "• система ежедневной работы\n\n"
            "<b>Главная задача MAX</b> - дать тебе не только "
            "источники, но и понятную систему работы с клиентами."
        )
    }
}


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu():

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
            ]
        ]
    )


# =========================================================
# ПРОФЕССИИ
# =========================================================

def professions_menu():

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
            ]
        ]
    )


# =========================================================
# КНОПКА ПОСЛЕ БРОШЮРЫ
# =========================================================

def profession_intro_menu(profession_key):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Перейти к тарифам",
                    callback_data=f"tariffs_{profession_key}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="← К направлениям",
                    callback_data="clients"
                )
            ]
        ]
    )


# =========================================================
# ТАРИФЫ
# =========================================================

def tariffs_menu(profession_key):

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
            ]
        ]
    )


# =========================================================
# СТРАНИЦА ТАРИФА
# =========================================================

def tariff_detail_menu(tariff_key, profession_key):

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
                    callback_data=f"tariffs_{profession_key}"
                )
            ]
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    # Удаляем старую нижнюю клавиатуру Telegram
    await message.answer(
        "Меню обновлено.",
        reply_markup=ReplyKeyboardRemove()
    )

    text = (
        "<b>INKLAB - База клиентов</b>\n\n"
        "Рабочий инструмент для фрилансера, который хочет "
        "стабильно находить новых клиентов и заказы.\n\n"
        "Вместо того чтобы каждый день тратить часы на "
        "самостоятельный поиск вакансий, чатов, каналов "
        "и площадок, ты получаешь готовую базу источников "
        "под свою профессию.\n\n"
        "Внутри будут собраны места, где можно находить:\n"
        "• вакансии и заказы\n"
        "• запросы на услуги\n"
        "• предложения о сотрудничестве\n"
        "• потенциальных клиентов\n\n"
        "<b>Выбираешь направление → получаешь подходящую "
        "базу → регулярно используешь ее для поиска.</b>\n\n"
        "INKLAB помогает сократить время на поиск источников "
        "и сделать поиск клиентов понятной частью твоей работы.\n\n"
        "<b>Выбери нужный раздел 👇</b>"
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
        "Для каждой профессии мы собираем отдельную базу "
        "источников для поиска клиентов и заказов.\n\n"
        "Выбери свое направление, чтобы посмотреть "
        "подробную информацию 👇"
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

    await callback.message.edit_text(
        profession["intro"],
        reply_markup=profession_intro_menu(profession_key)
    )


# =========================================================
# ПЕРЕХОД К ТАРИФАМ
# =========================================================

@dp.callback_query(F.data.startswith("tariffs_"))
async def tariffs_handler(callback: CallbackQuery):

    await callback.answer()

    profession_key = callback.data.replace(
        "tariffs_",
        ""
    )

    profession = PROFESSIONS.get(profession_key)

    if not profession:
        return

    text = (
        f"<b>{profession['title']}</b>\n\n"
        "Выбери подходящий тариф 👇\n\n"
        "Чем выше тариф, тем больше источников и "
        "дополнительных инструментов ты получаешь."
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
        f"<b>{profession['name']}</b>\n\n"
        f"{tariff['description']}\n\n"
        "<b>Стоимость:</b> будет добавлена после "
        "подключения системы оплаты."
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
        "Здесь будет безопасная оплата, после которой "
        "доступ к приобретенной базе будет выдаваться автоматически.\n\n"
        "<b>На следующем этапе подключим оплату "
        "и автоматическую выдачу доступа.</b>"
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
            ]
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
        "Пошаговая система для фрилансера, которая поможет "
        "организовать регулярный поиск новых клиентов.\n\n"
        "<b>Внутри:</b>\n\n"
        "1️⃣ Подготовка к поиску\n"
        "2️⃣ Где искать клиентов\n"
        "3️⃣ Как находить подходящие заказы\n"
        "4️⃣ Как написать первое сообщение\n"
        "5️⃣ Как презентовать свои услуги\n"
        "6️⃣ Как обсуждать стоимость\n"
        "7️⃣ Как работать с возражениями\n"
        "8️⃣ Как доводить клиента до оплаты\n\n"
        "Полную систему добавим отдельным материалом."
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
        "Полезный материал для тех, кто хочет понять, "
        "как устроен заработок на фрилансе и почему "
        "поиск клиентов является одной из главных задач.\n\n"
        "<b>Внутри:</b>\n"
        "• сколько можно зарабатывать на фрилансе\n"
        "• от чего зависит доход\n"
        "• где искать первых клиентов\n"
        "• зачем нужна клиентская база\n"
        "• почему нельзя постоянно ждать входящие заявки\n"
        "• как организовать регулярный поиск\n"
        "• как постепенно увеличивать количество заказов\n\n"
        "Полную бесплатную брошюру добавим позже."
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
            ]
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
        "Здесь будут отображаться все приобретенные "
        "базы и доступы.\n\n"
        "После подключения оплаты и системы выдачи доступа "
        "ты сможешь открывать купленные базы прямо отсюда."
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
            ]
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
        "Напиши в поддержку - мы поможем "
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
        "<b>INKLAB - База клиентов</b>\n\n"
        "Рабочий инструмент для фрилансера, который хочет "
        "стабильно находить новых клиентов и заказы.\n\n"
        "<b>Выбери нужный раздел 👇</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu()
    )


# =========================================================
# HEALTH CHECK
# =========================================================

async def health_check(request):

    return web.Response(
        text="INKLAB OK"
    )


# =========================================================
# WEBHOOK
# =========================================================

async def on_startup():

    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )

    logging.info(
        f"Webhook установлен: {WEBHOOK_URL}"
    )


async def on_shutdown():

    await bot.delete_webhook()

    await bot.session.close()

    logging.info(
        "Webhook удален"
    )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout
    )

    app = web.Application()

    app.router.add_get(
        "/",
        health_check
    )

    app.router.add_get(
        "/health",
        health_check
    )

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH
    )

    dp.startup.register(
        on_startup
    )

    dp.shutdown.register(
        on_shutdown
    )

    setup_application(
        app,
        dp,
        bot=bot
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=PORT
    )

    await site.start()

    logging.info(
        f"INKLAB запущен на порту {PORT}"
    )

    await asyncio.Event().wait()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
