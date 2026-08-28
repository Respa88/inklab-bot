import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton


# ==========================================
# НАСТРОЙКИ
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не найдена")


# ==========================================
# БОТ
# ==========================================

dp = Dispatcher()


# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👥 База клиентов"),
                KeyboardButton(text="📖 Система поиска клиентов"),
            ],
            [
                KeyboardButton(text="🎁 Бесплатно"),
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
        "Внутри INKLAB — готовые базы клиентов "
        "для специалистов разных направлений.\n\n"
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
# ПРОФЕССИИ
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
        "Здесь будет пошаговая система поиска клиентов:\n\n"
        "1. Где искать клиентов\n"
        "2. Как находить подходящие заказы\n"
        "3. Как написать первое сообщение\n"
        "4. Как презентовать свои услуги\n"
        "5. Как обсуждать стоимость\n"
        "6. Как работать с возражениями\n"
        "7. Как закрывать клиента на оплату\n\n"
        "Скоро здесь появится полная система."
    )

    await message.answer(text)


# ==========================================
# БЕСПЛАТНО
# ==========================================

@dp.message(F.text == "🎁 Бесплатно")
async def free_handler(message: Message):
    text = (
        "<b>🎁 Бесплатно</b>\n\n"
        "Полезная мини-брошюра для тех, "
        "кто хочет начать зарабатывать на фрилансе.\n\n"
        "Внутри:\n"
        "• сколько можно зарабатывать на фрилансе\n"
        "• от чего зависит доход\n"
        "• где искать первых клиентов\n"
        "• зачем нужна клиентская база\n"
        "• почему одни фрилансеры получают заказы постоянно, "
        "а другие постоянно ищут клиентов\n\n"
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
        "«База клиентов», чтобы посмотреть доступные тарифы."
    )

    await message.answer(text)


# ==========================================
# ПОДДЕРЖКА
# ==========================================

@dp.message(F.text == "💬 Поддержка")
async def support_handler(message: Message):
    text = (
        "<b>💬 Поддержка</b>\n\n"
        "Если у вас возник вопрос по оплате, "
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
# НЕИЗВЕСТНЫЕ СООБЩЕНИЯ
# ==========================================

@dp.message()
async def unknown_handler(message: Message):
    await message.answer(
        "Выберите нужный раздел в меню ниже.",
        reply_markup=main_menu()
    )


# ==========================================
# ЗАПУСК
# ==========================================

async def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
    )

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    print("INKLAB bot запущен")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
