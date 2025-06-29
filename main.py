import asyncio
import json
import html
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from scheduler import schedule, reschedule_all

BOT_TOKEN = "8035901285:AAGwQ0X2jPuC6sqt6utDzhPEei-ARAWePw8"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
giveaways_file = "storage.json"

class GiveawayForm(StatesGroup):
    waiting_for_forwarded_message = State()
    waiting_for_end_time = State()

def load_giveaways():
    try:
        with open(giveaways_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_giveaways(data):
    with open(giveaways_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

menu_buttons = InlineKeyboardBuilder()
menu_buttons.button(text="➕ Добавить розыгрыш", callback_data="add")
menu_buttons.button(text="📋 Список розыгрышей", callback_data="list")
menu_buttons.button(text="❌ Удалить розыгрыш", callback_data="delete")
menu_buttons.adjust(1)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я бот-напоминалка для розыгрышей!\n\n"
        "Выбери, что ты хочешь сделать:",
        reply_markup=menu_buttons.as_markup()
    )

@dp.callback_query(F.data == "add")
async def inline_add(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(GiveawayForm.waiting_for_forwarded_message)
    await query.message.edit_text("👉 Перешли мне сообщение с текстом розыгрыша (можно переслать из канала или чата).")

@dp.message(GiveawayForm.waiting_for_forwarded_message)
async def process_forwarded_message(message: Message, state: FSMContext):
    if not message.forward_from and not message.forward_from_chat:
        await message.answer("❌ Пожалуйста, перешли сообщение с розыгрышем, а не пиши его сам.")
        return

    text = message.text or message.caption or ""
    if not text:
        await message.answer("❌ В пересланном сообщении нет текста. Попробуй снова.")
        return

    channels = re.findall(r'@[\w_]+', text)
    channels = list(set(channels))

    if not channels:
        await message.answer("❗️ В тексте не найдено ни одного канала (@username).\n"
                             "Если в тексте нет каналов, их можно указать позже через /edit.")

    await state.update_data(text=text.strip(), channels=channels)

    await state.set_state(GiveawayForm.waiting_for_end_time)
    await message.answer("⏰ Теперь введи дату и время окончания (ДД.ММ.ГГГГ ЧЧ:ММ):")

@dp.message(GiveawayForm.waiting_for_end_time)
async def process_end_time(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Попробуй снова (ДД.ММ.ГГГГ ЧЧ:ММ):")
        return

    data = await state.get_data()
    giveaway = {
        "user_id": message.from_user.id,
        "text": data["text"],
        "channels": data["channels"],
        "main_channel": data["channels"][0] if data["channels"] else "",
        "end_time": dt.strftime("%Y-%m-%d %H:%M:%S")
    }

    giveaways = load_giveaways()
    giveaways.append(giveaway)
    save_giveaways(giveaways)
    await schedule(bot, giveaway)

    await message.answer("✅ Розыгрыш добавлен и запланирован!", reply_markup=menu_buttons.as_markup())
    await state.clear()

@dp.callback_query(F.data == "list")
async def inline_list(query: CallbackQuery):
    await query.answer()
    data = load_giveaways()
    user_giveaways = [g for g in data if g["user_id"] == query.from_user.id]
    if not user_giveaways:
        await query.message.edit_text("📭 У тебя пока нет активных розыгрышей.", reply_markup=menu_buttons.as_markup())
        return

    text = ""
    for idx, g in enumerate(user_giveaways):
        dt = datetime.strptime(g["end_time"], "%Y-%m-%d %H:%M:%S")
        safe_text = html.escape(g['text'][:50])
        text += (
            f"<b>ID:</b> {idx}\n"
            f"<b>Описание:</b>\n{safe_text}\n"
            f"<b>Дата:</b> До: {dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"<b>Каналы:</b> {', '.join(g['channels'])}\n\n"
        )

    await query.message.edit_text(text, reply_markup=menu_buttons.as_markup())

@dp.callback_query(F.data == "delete")
async def inline_delete(query: CallbackQuery):
    await query.answer()
    data = load_giveaways()
    user_giveaways = [g for g in data if g["user_id"] == query.from_user.id]
    if not user_giveaways:
        await query.message.edit_text("📭 У тебя нет активных розыгрышей.", reply_markup=menu_buttons.as_markup())
        return

    kb = InlineKeyboardBuilder()
    text = "<b>Выбери розыгрыш для удаления:</b>\n\n"
    for idx, g in enumerate(user_giveaways):
        dt = datetime.strptime(g["end_time"], "%Y-%m-%d %H:%M:%S")
        text += f"🎁 <b>#{idx}</b> — до {dt.strftime('%d.%m.%Y %H:%M')}\n"
        kb.button(text=f"❌ Удалить #{idx}", callback_data=f"del_{idx}")
    kb.button(text="↩ Назад", callback_data="back_menu")
    kb.adjust(1)

    await query.message.edit_text(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("del_"))
async def confirm_deletion(query: CallbackQuery):
    idx = int(query.data.split("_")[1])
    data = load_giveaways()
    user_id = query.from_user.id
    user_giveaways = [g for g in data if g["user_id"] == user_id]

    if idx >= len(user_giveaways):
        await query.answer("❌ Неверный ID.")
        return

    to_delete = user_giveaways[idx]
    data.remove(to_delete)
    save_giveaways(data)
    await query.answer("🗑 Удалено!")
    await inline_delete(query)

@dp.callback_query(F.data == "back_menu")
async def back_to_menu(query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        "👋 Привет! Я бот-напоминалка для розыгрышей!\n\nВыбери, что ты хочешь сделать:",
        reply_markup=menu_buttons.as_markup()
    )

async def main():
    await reschedule_all(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())