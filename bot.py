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

from datetime import datetime

import sqlite3
from contextlib import closing

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

dp = Dispatcher()

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)


# =========================================================
# БАЗА ДАННЫХ
# =========================================================

DB_PATH = os.getenv("DB_PATH", "inklab.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "inklab1").lstrip("@").lower()

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(db_connect()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profession TEXT,
                tariff TEXT,
                amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'paid',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

def register_user(user):
    now = datetime.utcnow().isoformat(timespec="seconds")
    with closing(db_connect()) as conn:
        conn.execute("""
            INSERT INTO users
                (user_id, username, first_name, last_name, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                last_seen=excluded.last_seen
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or "",
            now,
            now
        ))
        conn.commit()

def get_admin_stats():
    with closing(db_connect()) as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        paid = conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE status='paid'"
        ).fetchone()[0]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM purchases WHERE status='paid'"
        ).fetchone()[0]
        return users, paid, revenue

def get_users(limit=100):
    with closing(db_connect()) as conn:
        return conn.execute("""
            SELECT user_id, username, first_name, last_name,
                   first_seen, last_seen
            FROM users
            ORDER BY last_seen DESC
            LIMIT ?
        """, (limit,)).fetchall()

def is_admin(user):
    return bool(
        user
        and user.username
        and user.username.lower() == ADMIN_USERNAME
    )


# =========================================================
# ПОДДЕРЖКА
# =========================================================

# user_id администратора -> True, если он сейчас ожидает сообщение
# от пользователя в режиме поддержки.
support_mode = set()

# message_id сообщения пользователя в админском чате -> user_id.
# Это позволяет админу просто нажать "Ответить" на сообщение.
support_replies = {}


# =========================================================
# ПРОФЕССИИ
# =========================================================

PROFESSIONS = {

    "designer": {
        "name": "🎨 Дизайнер",
        "title": "База клиентов для дизайнеров",
        "intro": (
            "<b>🎨 Дизайнер</b>\n\n"
            "Здесь собрана база источников именно для дизайнеров: "
            "места, где появляются вакансии, заказы и запросы бизнеса "
            "на дизайн.\n\n"
            "<b>Зачем она нужна?</b>\n"
            "Вместо того чтобы каждый день искать с нуля Telegram-чаты, "
            "каналы, VK-сообщества и площадки, ты получаешь готовую "
            "систему источников в одном месте.\n\n"
            "С базой проще регулярно видеть новые возможности, "
            "быстрее находить подходящие проекты и не зависеть только "
            "от случайных входящих заявок.\n\n"
            "<b>Выбирай тариф ниже и используй базу как рабочий "
            "инструмент для постоянного поиска клиентов.</b>"
        )
    },

    "smm": {
        "name": "📱 SMM",
        "title": "База клиентов для SMM",
        "intro": (
            "<b>📱 SMM</b>\n\n"
            "Здесь собрана база источников для SMM-специалистов: "
            "вакансии, проекты, бизнес-сообщества и площадки, "
            "где можно находить потенциальных клиентов.\n\n"
            "<b>Зачем она нужна?</b>\n"
            "Ты экономишь время на самостоятельном поиске источников "
            "и получаешь готовые места, которые можно регулярно проверять.\n\n"
            "Это помогает быстрее находить бизнесы, которым уже сейчас "
            "нужен SMM, и выстраивать постоянный поток поиска вместо "
            "ожидания случайных заявок.\n\n"
            "<b>Выбирай тариф и используй базу как часть своей "
            "ежедневной работы.</b>"
        )
    },

    "target": {
        "name": "🎯 Таргетолог",
        "title": "База клиентов для таргетологов",
        "intro": (
            "<b>🎯 Таргетолог</b>\n\n"
            "Здесь собраны источники для таргетологов: вакансии, "
            "проекты и площадки, где бизнес ищет специалистов "
            "по рекламе и привлечению клиентов.\n\n"
            "<b>Зачем она нужна?</b>\n"
            "Не нужно каждый раз заново искать, где есть спрос. "
            "Ты получаешь готовую карту источников и можешь регулярно "
            "проверять новые предложения.\n\n"
            "Чем системнее ты работаешь с базой и качественнее "
            "презентуешь свои услуги, тем больше подходящих "
            "возможностей для получения заказов.\n\n"
            "<b>Выбирай тариф и превращай поиск клиентов "
            "в понятный рабочий процесс.</b>"
        )
    },

    "marketer": {
        "name": "📈 Маркетолог",
        "title": "База клиентов для маркетологов",
        "intro": (
            "<b>📈 Маркетолог</b>\n\n"
            "Здесь собраны источники для маркетологов: digital, "
            "performance, growth, B2B, контент, продвижение, "
            "аналитика и другие направления.\n\n"
            "<b>Зачем она нужна?</b>\n"
            "Хорошие источники спроса разбросаны по множеству площадок. "
            "INKLAB собирает их в одном месте, чтобы ты мог быстрее "
            "находить компании и проекты.\n\n"
            "Регулярная работа с базой помогает не ждать входящие заявки, "
            "а самостоятельно создавать поток новых возможностей.\n\n"
            "<b>Выбирай тариф и используй базу для ежедневного поиска.</b>"
        )
    },

    "copywriter": {
        "name": "✍️ Копирайтер",
        "title": "База клиентов для копирайтеров",
        "intro": (
            "<b>✍️ Копирайтер</b>\n\n"
            "Здесь собраны источники для копирайтеров, авторов "
            "и редакторов: заказы на статьи, коммерческие тексты, "
            "контент, SEO, сценарии и редактуру.\n\n"
            "<b>Зачем она нужна?</b>\n"
            "Вместо постоянного поиска новых площадок ты получаешь "
            "готовую основу для регулярного поиска проектов.\n\n"
            "Это позволяет быстрее замечать новые заказы, "
            "экономить время и постепенно выстраивать собственный "
            "поток клиентов.\n\n"
            "<b>Выбирай тариф и используй базу как рабочий инструмент.</b>"
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
        "price": 199,
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
        "price": 349,
        "description": (
            "<b>🚀 PRO</b>\n\n"
            "Самый выгодный вариант для фрилансера, который хочет "
            "получить больше источников и готовую систему поиска.\n\n"
            "<b>Что будет внутри:</b>\n"
            "• 30 источников поиска\n"
            "• 20 Telegram-источников\n"
            "• 5 VK-групп\n"
            "• 5 сайтов и приложений\n"
            "• система поиска клиентов\n"
            "• рекомендации по ежедневному поиску\n"
            "• шаблоны первого сообщения клиенту\n\n"
            "<b>Главная задача PRO</b> - дать тебе максимум "
            "полезного для регулярного поиска по адекватной цене."
        )
    },

    "max": {
        "name": "👑 MAX",
        "title": "Полная система поиска и продаж",
        "price": 890,
        "description": (
            "<b>👑 MAX</b>\n\n"
            "Максимальный набор для тех, кто хочет использовать "
            "INKLAB как полноценный рабочий инструмент.\n\n"
            "<b>Что будет внутри:</b>\n"
            "• все возможности PRO\n"
            "• расширенная база источников\n"
            "• дополнительные площадки\n"
            "• система поиска клиентов\n"
            "• система продаж\n"
            "• готовые скрипты сообщений\n"
            "• как презентовать услуги\n"
            "• как отвечать на возражения\n"
            "• как обсуждать стоимость\n"
            "• как доводить клиента до оплаты\n"
            "• система ежедневной работы\n"
            "• повышение чека и повторные продажи\n\n"
            "<b>Главная задача MAX</b> - дать тебе не только "
            "источники, но и расширенную систему работы с клиентами."
        )
    }
}


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 База клиентов", callback_data="clients")],
            [InlineKeyboardButton(text="📖 Система поиска клиентов", callback_data="search_system")],
            [InlineKeyboardButton(text="🎁 Бесплатно", callback_data="free")],
            [InlineKeyboardButton(text="🛍 Мои покупки", callback_data="purchases")],
            [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
        ]
    )


# =========================================================
# ПРОФЕССИИ
# =========================================================

def professions_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Дизайнер", callback_data="profession_designer")],
            [InlineKeyboardButton(text="📱 SMM", callback_data="profession_smm")],
            [InlineKeyboardButton(text="🎯 Таргетолог", callback_data="profession_target")],
            [InlineKeyboardButton(text="📈 Маркетолог", callback_data="profession_marketer")],
            [InlineKeyboardButton(text="✍️ Копирайтер", callback_data="profession_copywriter")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )


# =========================================================
# КНОПКА ПОСЛЕ БРОШЮРЫ
# =========================================================

def profession_intro_menu(profession_key):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Перейти к тарифам", callback_data=f"tariffs_{profession_key}")],
            [InlineKeyboardButton(text="← К направлениям", callback_data="clients")]
        ]
    )


# =========================================================
# ТАРИФЫ
# =========================================================

def tariffs_menu(profession_key):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ START - 199 ₽", callback_data=f"tariff_start_{profession_key}")],
            [InlineKeyboardButton(text="🚀 PRO - 349 ₽", callback_data=f"tariff_pro_{profession_key}")],
            [InlineKeyboardButton(text="👑 MAX - 890 ₽", callback_data=f"tariff_max_{profession_key}")],
            [InlineKeyboardButton(text="← К направлениям", callback_data="clients")]
        ]
    )


# =========================================================
# СТРАНИЦА ТАРИФА
# =========================================================

def tariff_detail_menu(tariff_key, profession_key):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить", callback_data=f"buy_{tariff_key}_{profession_key}")],
            [InlineKeyboardButton(text="← К тарифам", callback_data=f"tariffs_{profession_key}")]
        ]
    )


# =========================================================
# АДМИНКА
# =========================================================

def admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="💬 Ответить пользователю", callback_data="admin_support")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

def admin_stats_text():
    users, paid, revenue = get_admin_stats()
    return (
        "<b>🔐 Админ-панель INKLAB</b>\n\n"
        f"👥 Всего пользователей: <b>{users}</b>\n"
        f"💳 Оплаченных покупок: <b>{paid}</b>\n"
        f"💰 Заработано: <b>{revenue} ₽</b>\n\n"
        "Статистика сохраняется в SQLite."
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    register_user(message.from_user)

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

    await message.answer(text, reply_markup=main_menu())


# =========================================================
# БАЗА КЛИЕНТОВ
# =========================================================

@dp.callback_query(F.data == "clients")
async def clients_handler(callback: CallbackQuery):
    await callback.answer()

    text = (
        "<b>👥 База клиентов</b>\n\n"
        "Здесь собраны отдельные базы для пяти профессий:\n"
        "🎨 Дизайнер\n"
        "📱 SMM\n"
        "🎯 Таргетолог\n"
        "📈 Маркетолог\n"
        "✍️ Копирайтер\n\n"
        "В каждой базе собраны Telegram-каналы и чаты, VK-сообщества, "
        "сайты, биржи и другие площадки, где можно находить вакансии, "
        "заказы и потенциальных клиентов.\n\n"
        "<b>Почему это полезно?</b>\n"
        "Тебе не придется каждый раз искать источники с нуля. "
        "Готовая база экономит время и помогает сделать поиск клиентов "
        "регулярной частью работы.\n\n"
        "Выбери свою профессию - внутри сначала увидишь краткую "
        "информацию о пользе базы, а затем сможешь перейти к тарифам 👇"
    )

    await callback.message.edit_text(text, reply_markup=professions_menu())


# =========================================================
# ПРОФЕССИЯ
# =========================================================

@dp.callback_query(F.data.startswith("profession_"))
async def profession_handler(callback: CallbackQuery):
    await callback.answer()

    profession_key = callback.data.replace("profession_", "")
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

    profession_key = callback.data.replace("tariffs_", "")
    profession = PROFESSIONS.get(profession_key)

    if not profession:
        return

    text = (
        f"<b>{profession['title']}</b>\n\n"
        "Выбери подходящий тариф 👇\n\n"
        "🚀 <b>PRO - самый выгодный вариант:</b> 30 источников "
        "и система поиска клиентов.\n\n"
        "Чем выше тариф, тем больше источников и дополнительных "
        "инструментов ты получаешь."
    )

    await callback.message.edit_text(text, reply_markup=tariffs_menu(profession_key))


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
        f"<b>Стоимость: {tariff['price']} ₽</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=tariff_detail_menu(tariff_key, profession_key)
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
        f"<b>Стоимость: {tariff['price']} ₽</b>\n\n"
        "Система оплаты пока находится на этапе подключения.\n\n"
        "После подключения оплаты здесь будет кнопка оплаты, "
        "а после успешной оплаты бот автоматически выдаст "
        "купленный PDF и сохранит покупку в статистике."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Назад", callback_data=f"tariff_{tariff_key}_{profession_key}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)


# =========================================================
# СИСТЕМА ПОИСКА КЛИЕНТОВ
# =========================================================

@dp.callback_query(F.data == "search_system")
async def search_system_handler(callback: CallbackQuery):
    await callback.answer()

    text = (
        "<b>📖 Система поиска клиентов</b>\n\n"
        "Практическая система, которая помогает не просто находить "
        "заказы, а выстраивать весь путь от первого поиска до оплаты.\n\n"
        "<b>Внутри:</b>\n\n"
        "1️⃣ Подготовка к поиску\n"
        "2️⃣ Где искать клиентов\n"
        "3️⃣ Как находить подходящие заказы\n"
        "4️⃣ Как написать первое сообщение\n"
        "5️⃣ Как презентовать свои услуги\n"
        "6️⃣ Как обсуждать стоимость\n"
        "7️⃣ Как работать с возражениями\n"
        "8️⃣ Как доводить клиента до оплаты\n"
        "9️⃣ Как вести свои соцсети, чтобы клиенты приходили сами\n\n"
        "<b>Стоимость: 99 ₽</b>\n\n"
        "После подключения оплаты здесь будет доступна покупка "
        "и автоматическая выдача PDF."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить за 99 ₽", callback_data="buy_system")],
            [InlineKeyboardButton(text="👥 Посмотреть базы", callback_data="clients")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "buy_system")
async def buy_system_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "<b>💳 Система поиска клиентов - 99 ₽</b>\n\n"
        "Оплата будет подключена на следующем этапе.\n\n"
        "После оплаты бот автоматически отправит PDF.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="search_system")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
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
        "Бесплатный материал будет выдаваться прямо в боте."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Получить брошюру", callback_data="get_free")],
            [InlineKeyboardButton(text="👥 Посмотреть базы", callback_data="clients")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "get_free")
async def get_free_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📖 Бесплатная брошюра будет подключена после добавления её Telegram file_id."
    )


# =========================================================
# МОИ ПОКУПКИ
# =========================================================

@dp.callback_query(F.data == "purchases")
async def purchases_handler(callback: CallbackQuery):
    await callback.answer()

    with closing(db_connect()) as conn:
        rows = conn.execute("""
            SELECT profession, tariff, amount, created_at
            FROM purchases
            WHERE user_id=? AND status='paid'
            ORDER BY created_at DESC
        """, (callback.from_user.id,)).fetchall()

    if rows:
        lines = ["<b>🛍 Мои покупки</b>\n"]
        for row in rows:
            lines.append(
                f"• {row['profession']} - {row['tariff']} - {row['amount']} ₽"
            )
        text = "\n".join(lines)
    else:
        text = (
            "<b>🛍 Мои покупки</b>\n\n"
            "Пока у тебя нет оплаченных покупок.\n\n"
            "После оплаты приобретенные базы будут отображаться здесь."
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Выбрать базу", callback_data="clients")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)


# =========================================================
# ПОДДЕРЖКА
# =========================================================

@dp.callback_query(F.data == "support")
async def support_handler(callback: CallbackQuery):
    await callback.answer()

    support_mode.add(callback.from_user.id)

    text = (
        "<b>💬 Поддержка INKLAB</b>\n\n"
        "Напиши сюда свой вопрос обычным сообщением.\n\n"
        "Твоё сообщение будет передано администратору, "
        "а ответ придёт прямо сюда в этот чат.\n\n"
        "Можно спрашивать про оплату, доступ, базы или работу бота.\n\n"
        "<b>Чтобы выйти из поддержки:</b> нажми «Главное меню»."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.message(F.text)
async def support_message_handler(message: Message):
    # Сначала регистрируем любого пользователя, который написал боту.
    register_user(message.from_user)

    # Сообщения администратора обрабатываются отдельно ниже.
    if is_admin(message.from_user):
        return

    if message.from_user.id not in support_mode:
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "без username"
    name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))

    admin_text = (
        "💬 <b>Новое сообщение в поддержку</b>\n\n"
        f"👤 <b>{name or 'Пользователь'}</b>\n"
        f"🔗 {username}\n"
        f"🆔 <code>{message.from_user.id}</code>\n\n"
        f"{message.text}"
    )

    sent = await bot.send_message(
        chat_id=callback_admin_id(),
        text=admin_text
    )

    support_replies[sent.message_id] = message.from_user.id

    await message.answer(
        "✅ Сообщение отправлено в поддержку.\n\n"
        "Ответ администратора придёт сюда."
    )


def callback_admin_id():
    # Telegram Bot API не позволяет надежно отправить сообщение
    # по username без предварительного chat_id. Поэтому для админки
    # используется ADMIN_ID, который нужно указать в Render.
    value = os.getenv("ADMIN_ID")
    if not value:
        raise RuntimeError(
            "Для поддержки добавь в Render переменную ADMIN_ID "
            "с числовым Telegram ID администратора."
        )
    return int(value)


# =========================================================
# ОТВЕТ АДМИНА ПОЛЬЗОВАТЕЛЮ
# =========================================================

@dp.message(F.reply_to_message)
async def admin_reply_handler(message: Message):
    if not is_admin(message.from_user):
        return

    replied = message.reply_to_message
    user_id = support_replies.get(replied.message_id)

    if not user_id:
        # Также пытаемся найти ID прямо в сообщении поддержки.
        import re
        match = re.search(r"🆔\s*<code>(\d+)</code>", replied.text or "")
        if match:
            user_id = int(match.group(1))

    if not user_id:
        await message.answer(
            "Не удалось определить пользователя. "
            "Ответь именно на сообщение из поддержки."
        )
        return

    if message.text:
        await bot.send_message(
            chat_id=user_id,
            text=f"💬 <b>Ответ поддержки:</b>\n\n{message.text}"
        )
        await message.answer("✅ Ответ отправлен пользователю.")
    elif message.caption:
        await bot.send_message(
            chat_id=user_id,
            text=f"💬 <b>Ответ поддержки:</b>\n\n{message.caption}"
        )
        await message.answer("✅ Ответ отправлен пользователю.")
    else:
        await message.answer(
            "Пока поддержка через ответ обрабатывает только текстовые сообщения."
        )


# =========================================================
# АДМИН
# =========================================================

@dp.message(F.text == "/admin")
async def admin_command(message: Message):
    register_user(message.from_user)

    if not is_admin(message.from_user):
        await message.answer("⛔ Доступ запрещен.")
        return

    await message.answer(
        admin_stats_text(),
        reply_markup=admin_menu()
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        admin_stats_text(),
        reply_markup=admin_menu()
    )


@dp.callback_query(F.data == "admin_users")
async def admin_users_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    await callback.answer()

    rows = get_users(100)

    if not rows:
        text = "<b>👥 Пользователи</b>\n\nПока никто не заходил."
    else:
        lines = ["<b>👥 Пользователи</b>\n"]
        for i, row in enumerate(rows, 1):
            name = " ".join(filter(None, [row["first_name"], row["last_name"]]))
            username = f"@{row['username']}" if row["username"] else "без username"
            lines.append(
                f"{i}. {name or 'Без имени'} | {username}\n"
                f"ID: <code>{row['user_id']}</code>\n"
                f"Последний вход: {row['last_seen']}"
            )
        text = "\n\n".join(lines)

    await callback.message.edit_text(text, reply_markup=admin_menu())


@dp.callback_query(F.data == "admin_support")
async def admin_support_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    await callback.answer()
    support_mode.add(callback.from_user.id)

    await callback.message.answer(
        "<b>💬 Режим поддержки</b>\n\n"
        "Когда пользователь напишет в поддержку, "
        "бот пришлёт его сообщение сюда.\n\n"
        "<b>Чтобы ответить:</b> просто нажми «Ответить» "
        "на сообщении пользователя и напиши текст."
    )


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    await callback.answer()

    # Если пользователь вернулся в меню - выключаем режим поддержки.
    support_mode.discard(callback.from_user.id)

    text = (
        "<b>INKLAB - База клиентов</b>\n\n"
        "Рабочий инструмент для фрилансера, который хочет "
        "стабильно находить новых клиентов и заказы.\n\n"
        "<b>Выбери нужный раздел 👇</b>"
    )

    await callback.message.edit_text(text, reply_markup=main_menu())


# =========================================================
# HEALTH CHECK
# =========================================================

async def health_check(request):
    return web.Response(text="INKLAB OK")


# =========================================================
# WEBHOOK
# =========================================================

async def on_startup():
    init_db()

    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )

    logging.info(f"Webhook установлен: {WEBHOOK_URL}")


async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Webhook удален")


# =========================================================
# ЗАПУСК
# =========================================================

async def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout
    )

    init_db()

    app = web.Application()

    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

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

    logging.info(f"INKLAB запущен на порту {PORT}")

    await asyncio.Event().wait()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
