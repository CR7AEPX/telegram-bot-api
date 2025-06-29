import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
import json

async def schedule(bot: Bot, giveaway: dict):
    end_time = datetime.strptime(giveaway["end_time"], "%Y-%m-%d %H:%M:%S")
    user_id = giveaway["user_id"]
    text = giveaway["text"]
    channels = " ".join(giveaway["channels"])
    main_channel = giveaway["main_channel"]

    now = datetime.now()
    in_10_min = end_time - timedelta(minutes=10)
    delay_before_10_min = (in_10_min - now).total_seconds()
    delay_before_end = (end_time - now).total_seconds()

    async def send_10_min():
        await bot.send_message(user_id,
            f"🔔 Через 10 минут итоги розыгрыша:\n📌 {text}\n📅 Итоги: {end_time.strftime('%d.%m.%Y %H:%M')}")

    async def send_final():
        await bot.send_message(user_id,
            f"✅ Розыгрыш завершён!\n📌 {text}\n📎 Каналы, на которые ты подписывался: {channels}\n📍 Проверь итоги в основном канале: {main_channel}\n❗ Можешь отписаться, если не выиграл.")

    if delay_before_10_min > 0:
        asyncio.create_task(delayed_task(send_10_min, delay_before_10_min))
    if delay_before_end > 0:
        asyncio.create_task(delayed_task(send_final, delay_before_end))

async def delayed_task(callback, delay):
    await asyncio.sleep(delay)
    await callback()

async def reschedule_all(bot: Bot):
    with open("storage.json", "r") as f:
        data = json.load(f)
    for giveaway in data:
        end_time = datetime.strptime(giveaway["end_time"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < end_time:
            await schedule(bot, giveaway)