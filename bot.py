import asyncio
import logging
import os
import sys
import json
import uuid
from decimal import Decimal

from aiohttp import web, ClientSession, BasicAuth

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile
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

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")

if not RENDER_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL не найдена")

WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

PORT = int(os.getenv("PORT", "10000"))

# YooKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
YOOKASSA_API_URL = "https://api.yookassa.ru/v3"
YOOKASSA_RETURN_URL = f"{RENDER_URL}/payment/return"
YOOKASSA_USE_RECEIPT = os.getenv("YOOKASSA_USE_RECEIPT", "false").lower() == "true"

# Пути к картинкам внутри репозитория GitHub/Render.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WELCOME_IMAGE = os.path.join(BASE_DIR, "inklab_welcome.png")
CLIENTS_IMAGE = os.path.join(BASE_DIR, "inklab_clients.png")

PDF_DIR = BASE_DIR

# Все PDF, которые лежат в корне репозитория GitHub/Render.
PDF_FILES = {
    # Платные базы: профессия -> тариф -> PDF
    "designer": {
        "start": os.path.join(PDF_DIR, "INKLAB_DESIGNER_START_199.pdf"),
        "pro": os.path.join(PDF_DIR, "INKLAB_DESIGNER_PRO_349.pdf"),
        "max": os.path.join(PDF_DIR, "INKLAB_DESIGNER_MAX_890.pdf"),
    },
    "smm": {
        "start": os.path.join(PDF_DIR, "INKLAB_SMM_START_199.pdf"),
        "pro": os.path.join(PDF_DIR, "INKLAB_SMM_PRO_349.pdf"),
        "max": os.path.join(PDF_DIR, "INKLAB_SMM_MAX_890.pdf"),
    },
    "target": {
        "start": os.path.join(PDF_DIR, "INKLAB_TARGETOLOG_START_199.pdf"),
        "pro": os.path.join(PDF_DIR, "INKLAB_TARGETOLOG_PRO_349.pdf"),
        "max": os.path.join(PDF_DIR, "INKLAB_TARGETOLOG_MAX_890.pdf"),
    },
    "marketer": {
        "start": os.path.join(PDF_DIR, "INKLAB_MARKETER_START_199.pdf"),
        "pro": os.path.join(PDF_DIR, "INKLAB_MARKETER_PRO_349.pdf"),
        "max": os.path.join(PDF_DIR, "INKLAB_MARKETER_MAX_890.pdf"),
    },
    "copywriter": {
        "start": os.path.join(PDF_DIR, "INKLAB_COPYWRITER_START_199.pdf"),
        "pro": os.path.join(PDF_DIR, "INKLAB_COPYWRITER_PRO_349.pdf"),
        "max": os.path.join(PDF_DIR, "INKLAB_COPYWRITER_MAX_890.pdf"),
    },

    # Бесплатная брошюра.
    "free": os.path.join(PDF_DIR, "INKLAB_FREE_GUIDE.pdf"),

    # Отдельный цифровой продукт за 99 ₽.
    "search_system": os.path.join(PDF_DIR, "INKLAB_SEARCH_SYSTEM_99.pdf"),
}



def log_image_status():
    for label, path in (("WELCOME", WELCOME_IMAGE), ("CLIENTS", CLIENTS_IMAGE)):
        if os.path.isfile(path):
            logging.info("INKLAB image %s found: %s", label, path)
        else:
            logging.error("INKLAB image %s NOT FOUND: %s", label, path)


def log_pdf_status():
    """Проверяет наличие всех PDF и пишет результат в логи Render."""
    for key, value in PDF_FILES.items():
        if isinstance(value, dict):
            for tariff_key, path in value.items():
                if os.path.isfile(path):
                    logging.info(
                        "INKLAB PDF found: %s/%s -> %s",
                        key,
                        tariff_key,
                        path,
                    )
                else:
                    logging.error(
                        "INKLAB PDF NOT FOUND: %s/%s -> %s",
                        key,
                        tariff_key,
                        path,
                    )
        else:
            if os.path.isfile(value):
                logging.info("INKLAB PDF found: %s -> %s", key, value)
            else:
                logging.error("INKLAB PDF NOT FOUND: %s -> %s", key, value)


async def yookassa_request(method: str, path: str, *, json_data=None, idempotence_key=None):
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        raise RuntimeError("Переменные YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY не настроены")

    headers = {"Content-Type": "application/json"}
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key

    async with ClientSession() as session:
        async with session.request(
            method,
            f"{YOOKASSA_API_URL}{path}",
            auth=BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            headers=headers,
            json=json_data,
            timeout=30,
        ) as response:
            body = await response.text()
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {"raw": body}
            if response.status >= 400:
                raise RuntimeError(
                    f"YooKassa HTTP {response.status}: "
                    f"{data.get('description') or body}"
                )
            return data


async def create_yookassa_payment(
    *, user_id: int, amount: int, description: str,
    product_type: str, profession_key: str = "",
    tariff_key: str = "", email: str | None = None
):
    metadata = {
        "user_id": str(user_id),
        "product_type": product_type,
        "profession_key": profession_key,
        "tariff_key": tariff_key,
    }

    payment_data = {
        "amount": {
            "value": f"{Decimal(amount):.2f}",
            "currency": "RUB",
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": YOOKASSA_RETURN_URL,
        },
        "description": description[:128],
        "metadata": metadata,
    }

    if YOOKASSA_USE_RECEIPT:
        if not email:
            raise RuntimeError("Для чека ЮKassa нужен email покупателя")
        payment_data["receipt"] = {
            "customer": {"email": email},
            "items": [{
                "description": description[:128],
                "quantity": 1.0,
                "amount": {
                    "value": f"{Decimal(amount):.2f}",
                    "currency": "RUB",
                },
                "vat_code": 1,
                "payment_mode": "full_prepayment",
                "payment_subject": "service",
            }],
        }

    return await yookassa_request(
        "POST", "/payments", json_data=payment_data,
        idempotence_key=str(uuid.uuid4())
    )


async def get_yookassa_payment(payment_id: str):
    return await yookassa_request("GET", f"/payments/{payment_id}")


async def send_pdf_file(chat_id: int, pdf_path: str, caption: str):
    """Отправляет PDF из репозитория пользователю."""
    if not os.path.isfile(pdf_path):
        logging.error("PDF file not found: %s", pdf_path)
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Не удалось найти файл. Мы уже разбираемся с проблемой."
        )
        return False

    await bot.send_document(
        chat_id=chat_id,
        document=FSInputFile(pdf_path),
        caption=caption,
    )
    return True


def get_tariff_pdf_path(profession_key: str, tariff_key: str):
    """Возвращает путь к PDF конкретной профессии и тарифа."""
    profession_files = PDF_FILES.get(profession_key)
    if not isinstance(profession_files, dict):
        return None
    return profession_files.get(tariff_key)


async def send_tariff_pdf(user_id: int, profession_key: str, tariff_key: str):
    """
    Выдаёт купленный PDF.

    Эту функцию вызываем после подтверждения успешной оплаты.
    Она уже готова для всех 15 платных баз.
    """
    profession = PROFESSIONS.get(profession_key)
    tariff = TARIFFS.get(tariff_key)
    pdf_path = get_tariff_pdf_path(profession_key, tariff_key)

    if not profession or not tariff or not pdf_path:
        logging.error(
            "Unknown PDF mapping: profession=%s tariff=%s",
            profession_key,
            tariff_key,
        )
        await bot.send_message(
            chat_id=user_id,
            text="⚠️ Не удалось определить купленную базу."
        )
        return False

    return await send_pdf_file(
        chat_id=user_id,
        pdf_path=pdf_path,
        caption=(
            f"📦 <b>{profession['name']} — {tariff['name']}</b>\n\n"
            "Твоя база готова. Приятной работы!"
        ),
    )


async def send_menu_with_image(message: Message, image_path: str, caption: str, keyboard):
    """Отправляет баннер и текст одним Telegram-сообщением."""
    if os.path.isfile(image_path):
        return await message.answer_photo(
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=keyboard,
        )

    logging.error("Не удалось отправить изображение: %s", image_path)
    return await message.answer(caption, reply_markup=keyboard)


async def replace_callback_with_text(callback: CallbackQuery, text: str, keyboard):
    """Отправляет новый раздел отдельным сообщением, не удаляя предыдущий."""
    await callback.message.answer(text, reply_markup=keyboard)


async def replace_callback_with_image(callback: CallbackQuery, image_path: str, caption: str, keyboard):
    """Отправляет новый баннер отдельным сообщением, не удаляя предыдущий."""
    if os.path.isfile(image_path):
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        logging.error("Не удалось отправить изображение: %s", image_path)
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=caption,
            reply_markup=keyboard,
        )



# =========================================================
# БОТ
# =========================================================

from datetime import datetime, timezone, timedelta

import sqlite3
from contextlib import closing

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    """Создаёт таблицы и безопасно обновляет старую SQLite-базу."""
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
                source TEXT DEFAULT 'payment',
                payment_id TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                product_type TEXT NOT NULL,
                profession_key TEXT,
                tariff_key TEXT,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                delivery_status TEXT NOT NULL DEFAULT 'pending',
                processing_at TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT
            )
        """)

        # Миграция существующей базы без удаления старых данных.
        purchase_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(purchases)").fetchall()
        }
        if "source" not in purchase_columns:
            conn.execute(
                "ALTER TABLE purchases ADD COLUMN source TEXT DEFAULT 'payment'"
            )
        if "payment_id" not in purchase_columns:
            conn.execute(
                "ALTER TABLE purchases ADD COLUMN payment_id TEXT"
            )

        payment_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(payments)").fetchall()
        }
        if "delivery_status" not in payment_columns:
            conn.execute(
                "ALTER TABLE payments ADD COLUMN delivery_status TEXT DEFAULT 'pending'"
            )
        if "processing_at" not in payment_columns:
            conn.execute(
                "ALTER TABLE payments ADD COLUMN processing_at TEXT"
            )

        # Один реальный платёж = максимум одна покупка.
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_payment_id
            ON purchases(payment_id)
            WHERE payment_id IS NOT NULL
        """)

        conn.commit()

def register_user(user):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
            """
            SELECT COUNT(*)
            FROM purchases
            WHERE status='paid' AND COALESCE(source, 'payment')='payment'
            """
        ).fetchone()[0]
        manual = conn.execute(
            """
            SELECT COUNT(*)
            FROM purchases
            WHERE status='granted' OR COALESCE(source, '')='admin'
            """
        ).fetchone()[0]
        revenue = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM purchases
            WHERE status='paid' AND COALESCE(source, 'payment')='payment'
            """
        ).fetchone()[0]
        return users, paid, revenue, manual

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
    if not user:
        return False

    # Основной способ проверки - числовой Telegram ID.
    # Username оставляем как резервный вариант.
    if ADMIN_ID and user.id == ADMIN_ID:
        return True

    return bool(
        user.username
        and user.username.lower().lstrip("@") == ADMIN_USERNAME
    )


# =========================================================
# ПОДДЕРЖКА
# =========================================================

# Пользователи, которые сейчас пишут в поддержку.
support_mode = set()

# message_id сообщения пользователя в админском чате -> user_id.
support_replies = {}

# user_id пользователя, которому администратор сейчас отвечает
# через кнопку "Ответить".
admin_reply_target = {}

# Админская ручная выдача пакетов: admin_id -> target_user_id / '__WAITING_ID__'
admin_grant_target = {}


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
            [InlineKeyboardButton(text="📦 Выдать базу", callback_data="grant_package")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

def admin_grant_profession_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Дизайнер", callback_data="grant_profession_designer")],
            [InlineKeyboardButton(text="📱 SMM", callback_data="grant_profession_smm")],
            [InlineKeyboardButton(text="🎯 Таргетолог", callback_data="grant_profession_target")],
            [InlineKeyboardButton(text="📈 Маркетолог", callback_data="grant_profession_marketer")],
            [InlineKeyboardButton(text="✍️ Копирайтер", callback_data="grant_profession_copywriter")],
            [InlineKeyboardButton(text="← Админ-панель", callback_data="admin_back")]
        ]
    )


def admin_grant_tariff_menu(profession_key):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ START - 199 ₽", callback_data=f"grant_tariff_start_{profession_key}")],
            [InlineKeyboardButton(text="🚀 PRO - 349 ₽", callback_data=f"grant_tariff_pro_{profession_key}")],
            [InlineKeyboardButton(text="👑 MAX - 890 ₽", callback_data=f"grant_tariff_max_{profession_key}")],
            [InlineKeyboardButton(text="← К профессиям", callback_data="grant_package")]
        ]
    )


def admin_stats_text():
    users, paid, revenue, manual = get_admin_stats()
    return (
        "<b>🔐 Админ-панель INKLAB</b>\n\n"
        f"👥 Всего пользователей: <b>{users}</b>\n"
        f"💳 Оплаченных покупок: <b>{paid}</b>\n"
        f"📦 Выдано вручную: <b>{manual}</b>\n"
        f"💰 Заработано: <b>{revenue} ₽</b>\n\n"
        "Ручные выдачи не учитываются как доход."
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    register_user(message.from_user)

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
        "<b>Выбираешь направление -> получаешь подходящую "
        "базу -> регулярно используешь ее для поиска.</b>\n\n"
        "INKLAB помогает сократить время на поиск источников "
        "и сделать поиск клиентов понятной частью твоей работы.\n\n"
        "<b>Выбери нужный раздел 👇</b>"
    )

    await send_menu_with_image(message, WELCOME_IMAGE, text, main_menu())


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

    await replace_callback_with_image(callback, CLIENTS_IMAGE, text, professions_menu())


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

    await replace_callback_with_text(
        callback,
        profession["intro"],
        profession_intro_menu(profession_key)
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

    await replace_callback_with_text(callback, text, tariffs_menu(profession_key))


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

    await replace_callback_with_text(
        callback,
        text,
        tariff_detail_menu(tariff_key, profession_key)
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

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        await replace_callback_with_text(
            callback,
            "<b>💳 Оплата</b>\n\n"
            "Система оплаты временно недоступна. Попробуй немного позже.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data=f"tariff_{tariff_key}_{profession_key}")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        return

    try:
        payment = await create_yookassa_payment(
            user_id=callback.from_user.id,
            amount=tariff["price"],
            description=f"INKLAB — {profession['name']} — {tariff['name']}",
            product_type="tariff",
            profession_key=profession_key,
            tariff_key=tariff_key,
        )
        payment_id = payment["id"]
        confirmation_url = payment["confirmation"]["confirmation_url"]

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(db_connect()) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO payments
                    (payment_id, user_id, product_type, profession_key, tariff_key, amount, status, created_at)
                VALUES (?, ?, 'tariff', ?, ?, ?, 'pending', ?)
                """,
                (payment_id, callback.from_user.id, profession_key, tariff_key, tariff["price"], now),
            )
            conn.commit()

        text = (
            "<b>💳 Оплата</b>\n\n"
            f"{profession['name']}\n"
            f"{tariff['name']}\n\n"
            f"<b>К оплате: {tariff['price']} ₽</b>\n\n"
            "Нажми кнопку ниже, чтобы перейти на защищённую страницу оплаты ЮKassa.\n\n"
            "После успешной оплаты бот автоматически отправит твою базу."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
            [InlineKeyboardButton(text="← Назад", callback_data=f"tariff_{tariff_key}_{profession_key}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await replace_callback_with_text(callback, text, keyboard)

    except Exception:
        logging.exception(
            "Ошибка создания платежа YooKassa: user_id=%s profession=%s tariff=%s",
            callback.from_user.id, profession_key, tariff_key
        )
        await replace_callback_with_text(
            callback,
            "<b>⚠️ Не удалось создать оплату</b>\n\n"
            "Попробуй ещё раз через несколько секунд. "
            "Если ошибка повторяется — напиши в поддержку.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data=f"tariff_{tariff_key}_{profession_key}")],
                [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
            ])
        )


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
        "Оплата проходит через ЮKassa. После успешной оплаты PDF "
        "автоматически придёт в этот чат."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Купить за 99 ₽", callback_data="buy_system")],
            [InlineKeyboardButton(text="👥 Посмотреть базы", callback_data="clients")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="main_menu")]
        ]
    )

    await replace_callback_with_text(callback, text, keyboard)


@dp.callback_query(F.data == "buy_system")
async def buy_system_handler(callback: CallbackQuery):
    await callback.answer()

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        await replace_callback_with_text(
            callback,
            "<b>💳 Система поиска клиентов — 99 ₽</b>\n\n"
            "Система оплаты временно недоступна. Попробуй немного позже.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="search_system")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        return

    try:
        payment = await create_yookassa_payment(
            user_id=callback.from_user.id,
            amount=99,
            description="INKLAB — Система поиска клиентов",
            product_type="search_system",
        )
        payment_id = payment["id"]
        confirmation_url = payment["confirmation"]["confirmation_url"]

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(db_connect()) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO payments
                    (payment_id, user_id, product_type, profession_key, tariff_key, amount, status, created_at)
                VALUES (?, ?, 'search_system', '', '', 99, 'pending', ?)
                """,
                (payment_id, callback.from_user.id, now),
            )
            conn.commit()

        await replace_callback_with_text(
            callback,
            "<b>💳 Система поиска клиентов — 99 ₽</b>\n\n"
            "Нажми кнопку ниже, чтобы перейти на страницу оплаты ЮKassa.\n\n"
            "После успешной оплаты PDF автоматически придёт сюда.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить 99 ₽", url=confirmation_url)],
                [InlineKeyboardButton(text="← Назад", callback_data="search_system")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )

    except Exception:
        logging.exception("Ошибка создания платежа search_system: user_id=%s", callback.from_user.id)
        await replace_callback_with_text(
            callback,
            "<b>⚠️ Не удалось создать оплату</b>\n\n"
            "Попробуй ещё раз через несколько секунд.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="search_system")],
                [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
            ])
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

    await replace_callback_with_text(callback, text, keyboard)


@dp.callback_query(F.data == "get_free")
async def get_free_handler(callback: CallbackQuery):
    await callback.answer()

    await send_pdf_file(
        chat_id=callback.from_user.id,
        pdf_path=PDF_FILES["free"],
        caption=(
            "🎁 <b>Бесплатный путеводитель для фрилансера</b>\n\n"
            "Держи PDF. Внутри — основы заработка на фрилансе "
            "и система регулярного поиска клиентов."
        ),
    )


# =========================================================
# МОИ ПОКУПКИ
# =========================================================

@dp.callback_query(F.data == "purchases")
async def purchases_handler(callback: CallbackQuery):
    await callback.answer()

    with closing(db_connect()) as conn:
        rows = conn.execute("""
            SELECT profession, tariff, amount, status, source, created_at
            FROM purchases
            WHERE user_id=? AND status IN ('paid', 'granted')
            ORDER BY created_at DESC
        """, (callback.from_user.id,)).fetchall()

    if rows:
        lines = ["<b>🛍 Мои покупки</b>\n"]
        for row in rows:
            lines.append(
                (
                    f"• {row['profession']} - {row['tariff']} - "
                    f"{row['amount']} ₽"
                    if row["source"] != "admin"
                    else f"• {row['profession']} - {row['tariff']} - выдано вручную"
                )
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

    await replace_callback_with_text(callback, text, keyboard)


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

    await replace_callback_with_text(callback, text, keyboard)


@dp.message(Command("admin"))
async def admin_command_handler(message: Message):
    register_user(message.from_user)
    if not is_admin(message.from_user):
        await message.answer("⛔ Доступ запрещен.")
        return
    await message.answer(admin_stats_text(), reply_markup=admin_menu())


@dp.message(F.text)
async def support_message_handler(message: Message):

    register_user(message.from_user)

    # Если админ сейчас выдаёт пакет — первое сообщение должно быть ID.
    if is_admin(message.from_user) and admin_grant_target.get(message.from_user.id) == "__WAITING_ID__":
        raw_id = message.text.strip()
        if not raw_id.isdigit():
            await message.answer(
                "⚠️ ID должен состоять только из цифр.\n\n"
                "Отправь числовой Telegram ID пользователя."
            )
            return

        admin_grant_target[message.from_user.id] = int(raw_id)
        await message.answer(
            f"✅ Пользователь выбран: <code>{int(raw_id)}</code>\n\n"
            "Теперь выбери профессию:",
            reply_markup=admin_grant_profession_menu()
        )
        return

    # Администратор отвечает пользователю через кнопку "Ответить"
    # или обычной функцией Telegram "Ответить".
    if is_admin(message.from_user):
        user_id = None

        if message.reply_to_message:
            replied = message.reply_to_message
            user_id = support_replies.get(replied.message_id)

            if not user_id:
                import re
                match = re.search(r"🆔\s*<code>(\d+)</code>", replied.text or "")
                if match:
                    user_id = int(match.group(1))

        if not user_id:
            user_id = admin_reply_target.get(message.from_user.id)

        if user_id:
            await bot.send_message(
                chat_id=user_id,
                text=f"💬 <b>Ответ поддержки:</b>\n\n{message.text}"
            )
            admin_reply_target = {}
            await message.answer("✅ Ответ отправлен пользователю.")
        return

    if message.from_user.id not in support_mode:
        return

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "без username"
    )
    name = " ".join(
        filter(None, [message.from_user.first_name, message.from_user.last_name])
    )

    admin_text = (
        "💬 <b>Новое сообщение в поддержку</b>\n\n"
        f"👤 <b>{name or 'Пользователь'}</b>\n"
        f"🔗 {username}\n"
        f"🆔 <code>{message.from_user.id}</code>\n\n"
        f"{message.text}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Ответить",
                    callback_data=f"support_reply_{message.from_user.id}"
                )
            ]
        ]
    )

    sent = await bot.send_message(
        chat_id=callback_admin_id(),
        text=admin_text,
        reply_markup=keyboard
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

# =========================================================
# БЫСТРЫЙ ОТВЕТ ИЗ ПОДДЕРЖКИ
# =========================================================

@dp.callback_query(F.data.startswith("support_reply_"))
async def support_reply_button_handler(callback: CallbackQuery):

    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    try:
        user_id = int(callback.data.replace("support_reply_", ""))
    except ValueError:
        await callback.answer("Ошибка пользователя.", show_alert=True)
        return

    admin_reply_target[callback.from_user.id] = user_id
    await callback.answer("Теперь напиши ответ сообщением.")
    await callback.message.answer(
        "✍️ <b>Напиши ответ пользователю.</b>\n\n"
        "Следующее текстовое сообщение будет отправлено ему."
    )


# =========================================================
# АДМИН
# =========================================================


@dp.callback_query(F.data == "grant_package")
async def grant_package_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    admin_grant_target[callback.from_user.id] = "__WAITING_ID__"
    await callback.answer()
    await callback.message.answer(
        "<b>📦 Выдать базу</b>\n\n"
        "Отправь сюда <b>числовой Telegram ID</b> пользователя.\n\n"
        "Затем выберешь профессию и тариф. Бот отметит пакет как "
        "оплаченный и отправит соответствующий PDF.\n\n"
        "⚠️ Пользователь должен хотя бы один раз открыть бота "
        "и нажать /start, иначе Telegram может не разрешить "
        "отправить ему документ."
    )


@dp.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    admin_grant_target.pop(callback.from_user.id, None)
    await callback.answer()
    await replace_callback_with_text(callback, admin_stats_text(), admin_menu())


@dp.callback_query(F.data.startswith("grant_profession_"))
async def grant_profession_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    target_id = admin_grant_target.get(callback.from_user.id)
    if not isinstance(target_id, int):
        await callback.answer("Сначала укажи ID пользователя.", show_alert=True)
        return

    profession_key = callback.data.replace("grant_profession_", "")
    profession = PROFESSIONS.get(profession_key)
    if not profession:
        await callback.answer("Неизвестная профессия.", show_alert=True)
        return

    await callback.answer()
    await replace_callback_with_text(
        callback,
        f"<b>📦 Выдача базы</b>\n\n"
        f"👤 ID: <code>{target_id}</code>\n"
        f"📌 Профессия: {profession['name']}\n\n"
        "Выбери тариф:",
        admin_grant_tariff_menu(profession_key)
    )


@dp.callback_query(F.data.startswith("grant_tariff_"))
async def grant_tariff_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    target_id = admin_grant_target.get(callback.from_user.id)
    if not isinstance(target_id, int):
        await callback.answer("Сначала укажи ID пользователя.", show_alert=True)
        return

    parts = callback.data.split("_")
    if len(parts) != 4:
        await callback.answer("Ошибка пакета.", show_alert=True)
        return

    tariff_key = parts[2]
    profession_key = parts[3]
    tariff = TARIFFS.get(tariff_key)
    profession = PROFESSIONS.get(profession_key)
    pdf_path = get_tariff_pdf_path(profession_key, tariff_key)

    if not tariff or not profession or not pdf_path:
        await callback.answer("Пакет не найден.", show_alert=True)
        return

    # Выданный админом пакет появляется у пользователя в «Мои покупки».
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with closing(db_connect()) as conn:
            conn.execute(
                """
                INSERT INTO purchases
                    (user_id, profession, tariff, amount, status, source, payment_id, created_at)
                VALUES (?, ?, ?, 0, 'granted', 'admin', NULL, ?)
                """,
                (target_id, profession["name"], tariff["name"], now),
            )
            conn.commit()
    except Exception:
        logging.exception(
            "Ошибка ручной выдачи: user_id=%s profession=%s tariff=%s",
            target_id, profession_key, tariff_key
        )
        await callback.answer("Ошибка записи покупки.", show_alert=True)
        return

    await callback.answer("База выдана ✅")
    sent = await send_tariff_pdf(target_id, profession_key, tariff_key)
    admin_grant_target.pop(callback.from_user.id, None)

    if sent:
        result = (
            "<b>✅ База выдана</b>\n\n"
            f"👤 ID: <code>{target_id}</code>\n"
            f"📌 {profession['name']}\n"
            f"📦 {tariff['name']}\n\n"
            "PDF отправлен пользователю."
        )
    else:
        result = (
            "<b>⚠️ База записана, но PDF не отправлен</b>\n\n"
            f"👤 ID: <code>{target_id}</code>\n"
            f"📌 {profession['name']}\n"
            f"📦 {tariff['name']}\n\n"
            "Проверь, что пользователь уже запускал бота и что PDF есть в репозитории."
        )

    await callback.message.answer(
        result,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📦 Выдать ещё базу", callback_data="grant_package")],
                [InlineKeyboardButton(text="← Админ-панель", callback_data="admin_back")]
            ]
        )
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    await callback.answer()
    await replace_callback_with_text(
        callback,
        admin_stats_text(),
        admin_menu()
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

    await replace_callback_with_text(callback, text, admin_menu())


@dp.callback_query(F.data == "admin_support")
async def admin_support_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "<b>💬 Режим поддержки</b>\n\n"
        "Когда пользователь напишет в поддержку, "
        "бот пришлёт его сообщение сюда.\n\n"
        "<b>Чтобы ответить:</b> нажми кнопку «↩️ Ответить» "
        "под сообщением пользователя и напиши текст.\n\n"
        "Также можно использовать обычную функцию Telegram «Ответить»."
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

    await replace_callback_with_image(callback, WELCOME_IMAGE, text, main_menu())


# =========================================================
# YOOKASSA WEBHOOK
# =========================================================

async def yookassa_webhook(request):
    """
    Обрабатывает payment.succeeded безопасно для повторных webhook-запросов.

    Важная схема:
    1. Проверяем реальный статус платежа через API YooKassa.
    2. Атомарно забираем платеж в обработку.
    3. Создаём покупку только один раз по payment_id.
    4. Ставим delivery_status=pending до фактической отправки PDF.
    5. Если Telegram временно не отправил PDF, возвращаем 500.
       YooKassa повторит webhook, а бот повторит доставку.
    """
    try:
        payload = await request.json()
        event = payload.get("event")
        obj = payload.get("object") or {}
        payment_id = obj.get("id")

        if event != "payment.succeeded" or not payment_id:
            return web.Response(text="OK")

        payment = await get_yookassa_payment(payment_id)

        if payment.get("status") != "succeeded" or not payment.get("paid"):
            logging.warning(
                "YooKassa webhook ignored: payment=%s status=%s paid=%s",
                payment_id, payment.get("status"), payment.get("paid")
            )
            return web.Response(text="OK")

        metadata = payment.get("metadata") or {}
        try:
            meta_user_id = int(metadata.get("user_id", "0") or "0")
        except (TypeError, ValueError):
            meta_user_id = 0

        meta_product_type = metadata.get("product_type", "")
        meta_profession_key = metadata.get("profession_key", "")
        meta_tariff_key = metadata.get("tariff_key", "")

        if not meta_user_id:
            logging.error("YooKassa payment has no valid user_id: %s", payment_id)
            return web.Response(text="OK")

        try:
            amount = int(Decimal(str(payment.get("amount", {}).get("value", "0"))))
        except Exception:
            logging.error("Invalid amount in YooKassa payment: %s", payment_id)
            return web.Response(text="OK")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # Сначала находим наш платёж и проверяем сумму.
        with closing(db_connect()) as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE payment_id=?",
                (payment_id,)
            ).fetchone()

            if not row:
                logging.error("Unknown YooKassa payment_id: %s", payment_id)
                return web.Response(text="OK")

            if amount != int(row["amount"]):
                logging.error(
                    "YooKassa amount mismatch: payment=%s expected=%s actual=%s",
                    payment_id, row["amount"], amount
                )
                return web.Response(text="OK")

            # Проверяем, что webhook соответствует тому, что бот создавал.
            if (
                int(row["user_id"]) != meta_user_id
                or (row["product_type"] or "") != meta_product_type
                or (row["profession_key"] or "") != meta_profession_key
                or (row["tariff_key"] or "") != meta_tariff_key
            ):
                logging.error(
                    "YooKassa metadata mismatch: payment=%s "
                    "db=(user=%s product=%s profession=%s tariff=%s) "
                    "api=(user=%s product=%s profession=%s tariff=%s)",
                    payment_id,
                    row["user_id"], row["product_type"],
                    row["profession_key"], row["tariff_key"],
                    meta_user_id, meta_product_type,
                    meta_profession_key, meta_tariff_key,
                )
                return web.Response(text="OK")

            # Если PDF уже доставлен, повторный webhook ничего не делает.
            if row["status"] == "paid" and row["delivery_status"] == "delivered":
                return web.Response(text="OK")

            # Если платёж уже кем-то обрабатывается, не запускаем вторую
            # параллельную отправку PDF.
            if row["status"] == "processing":
                processing_at = row["processing_at"]
                stale = False
                if processing_at:
                    try:
                        started = datetime.fromisoformat(processing_at)
                        stale = (
                            datetime.now(timezone.utc) - started
                        ).total_seconds() > 600
                    except ValueError:
                        stale = True

                if not stale:
                    logging.info(
                        "YooKassa payment already processing: %s",
                        payment_id
                    )
                    return web.Response(text="OK")

            # Атомарный claim: только один webhook получает право
            # выполнять доставку.
            cursor = conn.execute(
                """
                UPDATE payments
                SET status='processing', processing_at=?
                WHERE payment_id=?
                  AND (
                      status='pending'
                      OR (
                          status='processing'
                          AND (
                              processing_at IS NULL
                              OR processing_at < ?
                          )
                      )
                  )
                """,
                (
                    now,
                    payment_id,
                    (
                        datetime.now(timezone.utc) - timedelta(minutes=10)
                    ).replace(microsecond=0).isoformat(),
                ),
            )

            # Если статус был paid с недоставленным PDF, выше UPDATE не
            # сработает. Для такого случая отдельный claim ниже.
            if cursor.rowcount != 1:
                cursor = conn.execute(
                    """
                    UPDATE payments
                    SET status='processing', processing_at=?
                    WHERE payment_id=?
                      AND status='paid'
                      AND delivery_status='pending'
                    """,
                    (now, payment_id),
                )

            if cursor.rowcount != 1:
                return web.Response(text="OK")

            # Проверяем продукт до записи покупки.
            product_type = row["product_type"]
            profession_key = row["profession_key"] or ""
            tariff_key = row["tariff_key"] or ""

            if product_type == "tariff":
                profession = PROFESSIONS.get(profession_key)
                tariff = TARIFFS.get(tariff_key)
                if not profession or not tariff or tariff["price"] != amount:
                    logging.error(
                        "Invalid tariff metadata for payment %s",
                        payment_id
                    )
                    conn.execute(
                        """
                        UPDATE payments
                        SET status='pending', processing_at=NULL
                        WHERE payment_id=?
                        """,
                        (payment_id,),
                    )
                    conn.commit()
                    return web.Response(text="OK")

                purchase_data = (
                    int(row["user_id"]),
                    profession["name"],
                    tariff["name"],
                    amount,
                    payment_id,
                    now,
                )
                purchase_sql = """
                    INSERT OR IGNORE INTO purchases
                        (user_id, profession, tariff, amount, status,
                         source, payment_id, created_at)
                    VALUES (?, ?, ?, ?, 'paid', 'payment', ?, ?)
                """
            elif product_type == "search_system":
                if amount != 99:
                    logging.error(
                        "Invalid search_system amount for payment %s",
                        payment_id
                    )
                    conn.execute(
                        """
                        UPDATE payments
                        SET status='pending', processing_at=NULL
                        WHERE payment_id=?
                        """,
                        (payment_id,),
                    )
                    conn.commit()
                    return web.Response(text="OK")

                purchase_data = (
                    int(row["user_id"]),
                    "📖 Система поиска клиентов",
                    "99 ₽",
                    amount,
                    payment_id,
                    now,
                )
                purchase_sql = """
                    INSERT OR IGNORE INTO purchases
                        (user_id, profession, tariff, amount, status,
                         source, payment_id, created_at)
                    VALUES (?, ?, ?, ?, 'paid', 'payment', ?, ?)
                """
            else:
                logging.error(
                    "Unknown product_type for payment %s: %s",
                    payment_id, product_type
                )
                conn.execute(
                    """
                    UPDATE payments
                    SET status='pending', processing_at=NULL
                    WHERE payment_id=?
                    """,
                    (payment_id,),
                )
                conn.commit()
                return web.Response(text="OK")

            conn.execute(purchase_sql, purchase_data)
            conn.execute(
                """
                UPDATE payments
                SET status='paid', paid_at=?, processing_at=NULL,
                    delivery_status='pending'
                WHERE payment_id=?
                """,
                (now, payment_id),
            )
            conn.commit()

        # PDF отправляем вне SQLite-транзакции, чтобы не держать БД
        # заблокированной во время сетевого запроса Telegram.
        if product_type == "tariff":
            delivered = await send_tariff_pdf(
                int(row["user_id"]), profession_key, tariff_key
            )
        else:
            delivered = await send_pdf_file(
                chat_id=int(row["user_id"]),
                pdf_path=PDF_FILES["search_system"],
                caption=(
                    "📖 <b>Система поиска клиентов</b>\n\n"
                    "Оплата прошла успешно. Держи PDF и используй систему в работе."
                ),
            )

        if not delivered:
            with closing(db_connect()) as conn:
                conn.execute(
                    """
                    UPDATE payments
                    SET delivery_status='pending', processing_at=NULL
                    WHERE payment_id=?
                    """,
                    (payment_id,),
                )
                conn.commit()

            logging.error(
                "YooKassa payment paid but PDF delivery failed: %s",
                payment_id,
            )
            return web.Response(status=500, text="DELIVERY_FAILED")

        with closing(db_connect()) as conn:
            conn.execute(
                """
                UPDATE payments
                SET delivery_status='delivered', processing_at=NULL
                WHERE payment_id=?
                """,
                (payment_id,),
            )
            conn.commit()

        logging.info(
            "YooKassa payment succeeded and delivered: %s user=%s product=%s amount=%s",
            payment_id, int(row["user_id"]), product_type, amount
        )
        return web.Response(text="OK")

    except Exception:
        logging.exception("Ошибка обработки YooKassa webhook")
        return web.Response(status=500, text="ERROR")


# =========================================================
# PAYMENT RETURN
# =========================================================

async def payment_return(request):
    return web.Response(
        content_type="text/html",
        text="""<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>INKLAB</title>
<style>
body{margin:0;background:#0b0b0d;color:#fff;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}
.card{max-width:520px;padding:40px}.title{font-size:32px;font-weight:700}.text{color:#bbb;font-size:18px;line-height:1.5;margin-top:16px}
</style></head>
<body><div class="card"><div class="title">Оплата принята</div>
<div class="text">Вернись в Telegram. После подтверждения платежа ЮKassa бот автоматически проверит оплату и отправит покупку в чат.</div>
</div></body></html>"""
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
    init_db()
    log_image_status()
    log_pdf_status()
    logging.info("YooKassa credentials configured: %s", bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY))
    logging.info("SQLite migrations checked successfully.")

    await bot.set_webhook(
        url=WEBHOOK_URL
    )

    logging.info(f"Webhook установлен: {WEBHOOK_URL}")
    logging.info("INKLAB: pending Telegram updates will be processed after startup.")


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
    app.router.add_get("/payment/return", payment_return)
    app.router.add_post("/yookassa/webhook", yookassa_webhook)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=False
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
