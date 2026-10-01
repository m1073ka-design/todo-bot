import asyncio
import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()

DB = "todo.db"

def create_table():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                deadline TEXT,
                done INTEGER DEFAULT 0
            )
        """)

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Vazifa qo'shish")],
        [KeyboardButton(text="Vazifalarim")],
        [KeyboardButton(text="Statistika")]
    ],
    resize_keyboard=True
)

class Task(StatesGroup):
    name = State()
    deadline = State()

@dp.message(CommandStart())
async def start(message: Message):
    try:
        with sqlite3.connect(DB) as con:
            con.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (message.from_user.id,)
            )

        await message.answer(
            "Assalomu alaykum! Todo botga xush kelibsiz.",
            reply_markup=menu
        )
    except Exception:
        await message.answer("Xatolik yuz berdi.")

@dp.message(F.text == "Vazifa qo'shish")
async def add_task(message: Message, state: FSMContext):
    await state.set_state(Task.name)
    await message.answer("Vazifa nomini kiriting:")


@dp.message(Task.name)
async def task_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Task.deadline)
    await message.answer(
        "Muddatni KK.OO.YYYY formatida kiriting yoki "
        "\"O'tkazib yuborish\" deb yozing:"
    )


@dp.message(Task.deadline)
async def task_deadline(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()

    if text.lower() == "o'tkazib yuborish":
        deadline = None
    else:
        try:
            date = datetime.strptime(text, "%d.%m.%Y")

            if date.date() < datetime.now().date():
                await message.answer("O'tib ketgan sana qabul qilinmaydi.")
                return

            deadline = text

        except ValueError:
            await message.answer(
                "Sana noto'g'ri. KK.OO.YYYY formatida kiriting."
            )
            return

    try:
        with sqlite3.connect(DB) as con:
            con.execute(
                "INSERT INTO tasks (user_id, name, deadline) VALUES (?, ?, ?)",
                (message.from_user.id, data["name"], deadline)
            )

        await message.answer("Vazifa qo'shildi.", reply_markup=menu)
        await state.clear()

    except Exception:
        await message.answer("Xatolik yuz berdi.")

@dp.message(F.text == "Vazifalarim")
async def my_tasks(message: Message):
    try:
        with sqlite3.connect(DB) as con:
            tasks = con.execute(
                """
                SELECT id, name, deadline, done
                FROM tasks
                WHERE user_id = ?
                """,
                (message.from_user.id,)
            ).fetchall()

        if not tasks:
            await message.answer("Sizda hozircha vazifalar yo'q.")
            return

        for task_id, name, deadline, done in tasks:
            status = "✅ Bajarilgan" if done else "⏳ Bajarilmagan"
            muddat = deadline if deadline else "Muddat yo'q"

            text = (
                f"📌 {name}\n"
                f"📅 Muddat: {muddat}\n"
                f"{status}"
            )

            buttons = []

            if not done:
                buttons.append(
                    InlineKeyboardButton(
                        text="✅ Bajarildi",
                        callback_data=f"done_{task_id}"
                    )
                )

            buttons.append(
                InlineKeyboardButton(
                    text="🗑 O'chirish",
                    callback_data=f"delete_{task_id}"
                )
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[buttons]
            )

            await message.answer(text, reply_markup=keyboard)

    except Exception:
        await message.answer("Xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("done_"))
async def done_task(callback):
    task_id = int(callback.data.split("_")[1])

    try:
        with sqlite3.connect(DB) as con:
            task = con.execute(
                """
                SELECT name, deadline
                FROM tasks
                WHERE id = ? AND user_id = ?
                """,
                (task_id, callback.from_user.id)
            ).fetchone()

            if not task:
                await callback.answer("Vazifa topilmadi.")
                return

            con.execute(
                "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
                (task_id, callback.from_user.id)
            )

        name, deadline = task
        muddat = deadline if deadline else "Muddat yo'q"

        await callback.message.edit_text(
            f"📌 {name}\n"
            f"📅 Muddat: {muddat}\n"
            f"✅ Bajarilgan\n\n"
            f"🗑 O'chirish tugmasi mavjud."
        )

        await callback.answer("Vazifa bajarildi.")

    except Exception:
        await callback.answer("Xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("delete_"))
async def delete_task(callback):
    task_id = int(callback.data.split("_")[1])

    try:
        with sqlite3.connect(DB) as con:
            task = con.execute(
                """
                SELECT name
                FROM tasks
                WHERE id = ? AND user_id = ?
                """,
                (task_id, callback.from_user.id)
            ).fetchone()

            if not task:
                await callback.answer("Vazifa topilmadi.")
                return

            con.execute(
                "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                (task_id, callback.from_user.id)
            )

        await callback.message.edit_text(
            f"🗑 \"{task[0]}\" o'chirildi."
        )

        await callback.answer("Vazifa o'chirildi.")

    except Exception:
        await callback.answer("Xatolik yuz berdi.")

@dp.message(F.text == "Statistika")
async def statistics(message: Message):
    try:
        with sqlite3.connect(DB) as con:
            total = con.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id = ?",
                (message.from_user.id,)
            ).fetchone()[0]

            done = con.execute(
                """
                SELECT COUNT(*)
                FROM tasks
                WHERE user_id = ? AND done = 1
                """,
                (message.from_user.id,)
            ).fetchone()[0]

        remaining = total - done

        await message.answer(
            f"📊 Statistika\n\n"
            f"Jami: {total}\n"
            f"✅ Bajarilgan: {done}\n"
            f"⏳ Qolgan: {remaining}"
        )

    except Exception:
        await message.answer("Xatolik yuz berdi.")

async def main():
    create_table()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
