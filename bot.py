import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# TOKEN
# =========================

TOKEN = "8616037861:AAHSaUgFBCv1c-8WzoQpGdiYS1OtM94HIAE"

# =========================
# GROUP CHAT ID
# =========================

CHAT_ID = -5247953376

# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# =========================
# TIMEZONE
# =========================

TIMEZONE = ZoneInfo("Asia/Tashkent")

# =========================
# ADMIN
# =========================

ADMIN_USERNAME = "umidpulatov"

NOTIFY_TAGS = "@umidpulatov @kh_nosirov"

# =========================
# AGENTS
# =========================

AGENT_ORDER = [
    "sirlyinfo",
    "Muhammadhumoyun_Mudarris",
]

AGENTS = {
    "sirlyinfo": "Ozodbek",
    "Muhammadhumoyun_Mudarris": "Muhammadhumoyun",
}

AGENT_INFO = {
    "sirlyinfo": (
        "👨🏻‍💻 Ozodbek @sirlyinfo\n"
        "📞 93 798 13 04"
    ),
    "Muhammadhumoyun_Mudarris": (
        "👨🏻‍💻 Muhammadhumoyun @Muhammadhumoyun_Mudarris\n"
        "📞 88 811 88 51 • 94 115 88 51"
    ),
}

# =========================
# CHECKLIST
# =========================

CHECKLISTS = {
    "10:00": [
        "Admin panel (support) tozalandi",
        "Muammoli mijozlar jadvali to'liq tekshirildi",
        "Umid akaga checklist skrinshoti yuborildi",
    ],
    "14:00": [
        "Muammoli mijozlar jadvali to'liq tekshirildi",
        "Sotuv tablistsyasi toldirildi",
        "Umid akaga checklist skrinshoti yuborildi",
    ],
    "18:00": [
        "Muammoli mijozlar jadvali to'liq tekshirildi",
        "Sirly bug va task guruhidagi barcha bug hamda tasklar jadvalga kiritildi",
        "Umid akaga checklist skrinshoti yuborildi",
    ],
    "23:00": [
        "Bugalteriya jadvali to'ldirildi",
        "Bugalteriya kunlik holati hamkorlar telegram guruhlariga yuborildi",
    ],
    "23:30": [
        "Support va telegramdagi murojaatlar qolib ketmadi",
        "Ishlamayotgan hamkorlar ilovada sotildi holatiga o'zgartirildimi?",
        "Checklist to'liq tekshirildi",
        "To'liq tekshiirilgani haqida Sirly STAFF ga habar yuborildimi? Umid akani tag qilib",
    ],
}

CHECKLIST_TIMES = ["10:00", "14:00", "18:00", "23:00", "23:30"]

# =========================
# STATE
# =========================

state = {
    # 30-min reminder state
    "confirmations": {},
    "reminder_message_id": None,
    "reminder_sent_at": None,
    "nudge_count": 0,

    # checklist state: {time_key: {username: {task_index: bool}}}
    "checklist_confirmations": {},
    "checklist_message_ids": {},  # {time_key: message_id}

    "cycle_id": 0,
    "stopped": False,
}

# =========================
# ACTIVE AGENTS
# =========================

def get_active_agents():
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    hour = now.hour
    active = set()

    # Ozodbek: Mon-Fri 10:00-20:00, Sat 10:00-23:59, Sun OFF
    if weekday <= 4:
        if 10 <= hour < 20:
            active.add("sirlyinfo")
    elif weekday == 5:
        if hour >= 10:
            active.add("sirlyinfo")

    # Muhammadhumoyun: Mon-Fri 14:00-23:59, Sat OFF, Sun 10:00-23:59
    if weekday <= 4:
        if hour >= 14:
            active.add("Muhammadhumoyun_Mudarris")
    elif weekday == 6:
        if hour >= 10:
            active.add("Muhammadhumoyun_Mudarris")

    return active

# =========================
# ACTIVE AGENTS FOR CHECKLIST TIME
# =========================

def get_active_agents_for_time(time_key):
    """Return active agents based on checklist time."""
    hour = int(time_key.split(":")[0])
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    active = set()

    # Ozodbek: Mon-Fri 10:00-20:00, Sat 10:00-23:59, Sun OFF
    if weekday <= 4:
        if 10 <= hour < 20:
            active.add("sirlyinfo")
    elif weekday == 5:
        if hour >= 10:
            active.add("sirlyinfo")

    # Muhammadhumoyun: Mon-Fri 14:00-23:59, Sat OFF, Sun 10:00-23:59
    if weekday <= 4:
        if hour >= 14:
            active.add("Muhammadhumoyun_Mudarris")
    elif weekday == 6:
        if hour >= 10:
            active.add("Muhammadhumoyun_Mudarris")

    return active

# =========================
# BUILD 30-MIN KEYBOARD
# =========================

def build_reminder_keyboard(active_agents, confirmations):
    keyboard = []
    for username in AGENT_ORDER:
        if username not in active_agents:
            continue
        name = AGENTS[username]
        conf = confirmations.get(username, {"mijoz": False, "hamkor": False})
        mijoz_label = f"✅ {name} - Мижозлар текширилди" if conf["mijoz"] else f"⬜ {name} - Мижозлар текширилди"
        hamkor_label = f"✅ {name} - Ҳамкорлар текширилди" if conf["hamkor"] else f"⬜ {name} - Ҳамкорлар текширилди"
        keyboard.append([InlineKeyboardButton(mijoz_label, callback_data=f"confirm_{username}_mijoz")])
        keyboard.append([InlineKeyboardButton(hamkor_label, callback_data=f"confirm_{username}_hamkor")])
    return InlineKeyboardMarkup(keyboard)

# =========================
# BUILD CHECKLIST KEYBOARD
# =========================

def build_checklist_keyboard(time_key, active_agents, checklist_confs):
    tasks = CHECKLISTS[time_key]
    keyboard = []
    for username in AGENT_ORDER:
        if username not in active_agents:
            continue
        name = AGENTS[username]
        user_conf = checklist_confs.get(username, {})
        for i, task in enumerate(tasks):
            done = user_conf.get(i, False)
            short_task = task if len(task) <= 30 else task[:30] + "..."
            icon = "✅" if done else "⬜"
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {name} — {short_task}",
                    callback_data=f"chk_{time_key.replace(':', '')}_{username}_{i}"
                )
            ])
    return InlineKeyboardMarkup(keyboard)

# =========================
# BUILD CHECKLIST TEXT
# =========================

def build_checklist_text(time_key):
    tasks = CHECKLISTS[time_key]
    task_lines = "\n".join(f"{i+1}. {task} ☑️" for i, task in enumerate(tasks))
    return (
        f"📋 {time_key} чеклист\n\n"
        f"{task_lines}\n\n"
        "━━━━━━━━━━━━━━"
    )

# =========================
# BUILD REMINDER TEXT
# =========================

def build_reminder_text(active_agents):
    agent_block = "\n\n".join(
        AGENT_INFO[u]
        for u in AGENT_ORDER
        if u in active_agents
    )
    return (
        f"{agent_block}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💬 Мижозлардан келган мурожаатларни текширдингизми? ☑️\n\n"
        "🤝 Ҳамкорлардан келган мурожаатларни текширдингизми? ☑️\n\n"
        "━━━━━━━━━━━━━━"
    )

# =========================
# ALL CONFIRMED CHECK (30-min)
# =========================

def all_confirmed(active_agents, confirmations):
    for username in active_agents:
        conf = confirmations.get(username, {})
        if not conf.get("mijoz") or not conf.get("hamkor"):
            return False
    return True

# =========================
# CHECKLIST ALL CONFIRMED
# =========================

def checklist_all_confirmed(time_key, active_agents, checklist_confs):
    tasks = CHECKLISTS[time_key]
    for username in active_agents:
        user_conf = checklist_confs.get(username, {})
        for i in range(len(tasks)):
            if not user_conf.get(i, False):
                return False
    return True

# =========================
# PENDING AGENTS (30-min)
# =========================

def get_pending_agents(active_agents, confirmations):
    pending = []
    for username in AGENT_ORDER:
        if username not in active_agents:
            continue
        conf = confirmations.get(username, {})
        if not conf.get("mijoz") or not conf.get("hamkor"):
            pending.append(username)
    return pending

# =========================
# CANCEL JOBS
# =========================

def cancel_jobs_by_name(job_queue, name):
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()

# =========================
# SECONDS UNTIL NEXT 30 MIN
# =========================

def seconds_until_next_30():
    now = datetime.now(TIMEZONE)
    elapsed = now.minute * 60 + now.second + now.microsecond / 1_000_000
    next_30 = ((now.minute // 30) + 1) * 30 * 60
    return max(next_30 - elapsed, 1.0)

# =========================
# SECONDS UNTIL GIVEN TIME
# =========================

def seconds_until_time(hour, minute):
    now = datetime.now(TIMEZONE)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        # next day
        from datetime import timedelta
        target += timedelta(days=1)
    return (target - now).total_seconds()

# =========================
# SEND 30-MIN REMINDER
# =========================

async def send_reminder(bot, job_queue, cycle_id):
    active = get_active_agents()
    if not active:
        return

    state["confirmations"] = {
        username: {"mijoz": False, "hamkor": False}
        for username in active
    }
    state["reminder_message_id"] = None
    state["reminder_sent_at"] = datetime.now(TIMEZONE)
    state["nudge_count"] = 0

    text = build_reminder_text(active)
    keyboard = build_reminder_keyboard(active, state["confirmations"])

    sent = await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=keyboard,
    )
    state["reminder_message_id"] = sent.message_id

    cancel_jobs_by_name(job_queue, "nudge")
    job_queue.run_repeating(
        nudge_job,
        interval=300,
        first=300,
        name="nudge",
        data={"cycle_id": cycle_id},
    )

# =========================
# SEND CHECKLIST
# =========================

async def send_checklist(bot, time_key):
    active = get_active_agents_for_time(time_key)
    if not active:
        return

    state["checklist_confirmations"][time_key] = {
        username: {} for username in active
    }

    text = build_checklist_text(time_key)
    keyboard = build_checklist_keyboard(
        time_key, active,
        state["checklist_confirmations"][time_key]
    )

    sent = await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=keyboard,
    )
    state["checklist_message_ids"][time_key] = sent.message_id

# =========================
# REMINDER JOB
# =========================

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    cycle_id = context.job.data["cycle_id"]
    if cycle_id != state["cycle_id"] or state["stopped"]:
        return

    await send_reminder(context.bot, context.job_queue, cycle_id)

    cancel_jobs_by_name(context.job_queue, "reminder")
    context.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": cycle_id},
    )

# =========================
# CHECKLIST JOB
# =========================

async def checklist_job(context: ContextTypes.DEFAULT_TYPE):
    cycle_id = context.job.data["cycle_id"]
    time_key = context.job.data["time_key"]

    if cycle_id != state["cycle_id"] or state["stopped"]:
        return

    await send_checklist(context.bot, time_key)

    # Schedule next day same time
    hour, minute = map(int, time_key.split(":"))
    context.job_queue.run_once(
        checklist_job,
        when=seconds_until_time(hour, minute),
        name=f"checklist_{time_key}",
        data={"cycle_id": cycle_id, "time_key": time_key},
    )

# =========================
# NUDGE JOB
# =========================

async def nudge_job(context: ContextTypes.DEFAULT_TYPE):
    cycle_id = context.job.data["cycle_id"]
    if cycle_id != state["cycle_id"] or state["stopped"]:
        return

    active = get_active_agents()
    pending = get_pending_agents(active, state["confirmations"])

    if not pending:
        cancel_jobs_by_name(context.job_queue, "nudge")
        return

    if state["nudge_count"] >= 3:
        cancel_jobs_by_name(context.job_queue, "nudge")
        return

    state["nudge_count"] += 1

    agent_block = "\n\n".join(AGENT_INFO[u] for u in pending)

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"{agent_block}\n\n"
            "━━━━━━━━━━━━━━\n\n"
            f"⚠️ Юқоридаги хабарни тасдиқланг! "
            f"({state['nudge_count']}/3)\n\n"
            "━━━━━━━━━━━━━━"
        ),
    )

# =========================
# CALLBACK — 30-MIN REMINDER
# =========================

async def handle_reminder_callback(query, username, target_username, confirm_type, context):
    if username != target_username:
        await query.answer()
        return

    active = get_active_agents()
    if username not in active:
        await query.answer()
        return

    if username not in state["confirmations"]:
        state["confirmations"][username] = {"mijoz": False, "hamkor": False}

    if state["confirmations"][username][confirm_type]:
        await query.answer()
        return

    state["confirmations"][username][confirm_type] = True

    name = AGENTS.get(username, username)
    now = datetime.now(TIMEZONE)
    time_str = now.strftime("%H:%M")

    if confirm_type == "mijoz":
        label = "жавоб берилмаган мижоз қолмаганини тасдиқлади"
    else:
        label = "жавоб берилмаган ҳамкор қолмаганини тасдиқлади"

    await query.answer("✅ Тасдиқланди!")

    msg_id = state.get("reminder_message_id")
    if msg_id:
        keyboard = build_reminder_keyboard(active, state["confirmations"])
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=CHAT_ID,
                message_id=msg_id,
                reply_markup=keyboard,
            )
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"{NOTIFY_TAGS}\n\n✅ {name} ({time_str}) — {label} ✅",
    )

    if all_confirmed(active, state["confirmations"]):
        cancel_jobs_by_name(context.job_queue, "nudge")
        sent_at = state["reminder_sent_at"] or now
        mins = int((now - sent_at).total_seconds() // 60)
        names_list = "\n".join(
            f"✅ {AGENTS[u]}" for u in AGENT_ORDER if u in active
        )
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"🎉 Барча тасдиқлади!\n\n"
                f"{names_list}\n\n"
                f"⏱ Вақт: {mins} дақиқа"
            ),
        )

# =========================
# CALLBACK — CHECKLIST
# =========================

async def handle_checklist_callback(query, username, parts, context):
    # parts: ["chk", time_str, username, task_index]
    if len(parts) != 4:
        await query.answer()
        return

    _, time_str, target_username, task_index_str = parts
    time_key = time_str[:2] + ":" + time_str[2:]  # "1000" -> "10:00"

    if username != target_username:
        await query.answer()
        return

    active = get_active_agents_for_time(time_key)
    if username not in active:
        await query.answer()
        return

    if time_key not in state["checklist_confirmations"]:
        await query.answer()
        return

    task_index = int(task_index_str)
    tasks = CHECKLISTS.get(time_key, [])
    if task_index >= len(tasks):
        await query.answer()
        return

    user_conf = state["checklist_confirmations"][time_key].get(username, {})

    if user_conf.get(task_index, False):
        await query.answer()
        return

    state["checklist_confirmations"][time_key][username][task_index] = True

    name = AGENTS.get(username, username)
    task_text = tasks[task_index]
    now = datetime.now(TIMEZONE)
    time_str_now = now.strftime("%H:%M")

    await query.answer("✅ Тасдиқланди!")

    # Update checklist keyboard
    msg_id = state["checklist_message_ids"].get(time_key)
    if msg_id:
        keyboard = build_checklist_keyboard(
            time_key, active,
            state["checklist_confirmations"][time_key]
        )
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=CHAT_ID,
                message_id=msg_id,
                reply_markup=keyboard,
            )
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"{NOTIFY_TAGS}\n\n✅ {name} ({time_str_now}) — {task_text}",
    )

# =========================
# CALLBACK HANDLER
# =========================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    username = query.from_user.username

    if state["stopped"]:
        await query.answer()
        return

    data = query.data

    if data.startswith("confirm_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            _, target_username, confirm_type = parts
            await handle_reminder_callback(
                query, username, target_username, confirm_type, context
            )

    elif data.startswith("chk_"):
        parts = data.split("_", 3)
        await handle_checklist_callback(query, username, parts, context)

    else:
        await query.answer()

# =========================
# START COMMAND
# =========================

WEEKDAY_UZ = {
    0: "Душанба",
    1: "Сешанба",
    2: "Чоршанба",
    3: "Пайшанба",
    4: "Жума",
    5: "Шанба",
    6: "Якшанба",
}

MONTH_UZ = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель",
    5: "май", 6: "июнь", 7: "июль", 8: "август",
    9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
}

def get_agent_schedule_today(username):
    """Return (start_hour, end_hour) or None if day off."""
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()

    if username == "sirlyinfo":
        if weekday <= 4:
            return (10, 20)
        elif weekday == 5:
            return (10, 24)
        else:
            return None

    elif username == "Muhammadhumoyun_Mudarris":
        if weekday <= 4:
            return (14, 24)
        elif weekday == 6:
            return (10, 24)
        else:
            return None

    return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    active = get_active_agents()
    now = datetime.now(TIMEZONE)

    if not active:
        weekday_name = WEEKDAY_UZ[now.weekday()]
        date_str = f"{weekday_name}, {now.day}-{MONTH_UZ[now.month]} {now.year}"
        time_str = now.strftime("%H:%M")

        lines = [
            "🌙 Ҳозир support иш вақти эмас.
",
            f"📅 Бугун: {date_str}",
            f"🕐 Ҳозирги вақт: {time_str}
",
            "──────────────",
        ]

        for username in AGENT_ORDER:
            schedule = get_agent_schedule_today(username)
            info = AGENT_INFO[username]
            if schedule:
                start_h, end_h = schedule
                end_str = "23:59" if end_h == 24 else f"{end_h:02d}:00"
                lines.append(f"
{info}
🕐 Бугун иш вақти: {start_h:02d}:00 — {end_str}")
            else:
                lines.append(f"
{info}
😴 Бугун дам олади")
            lines.append("
──────────────")

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="
".join(lines),
        )
        return

    state["stopped"] = False
    state["cycle_id"] += 1

    cancel_jobs_by_name(context.job_queue, "reminder")
    cancel_jobs_by_name(context.job_queue, "nudge")
    for t in CHECKLIST_TIMES:
        cancel_jobs_by_name(context.job_queue, f"checklist_{t}")

    now = datetime.now(TIMEZONE)
    next_q_total = ((now.minute // 30) + 1) * 30
    next_q_hour = (now.hour + next_q_total // 60) % 24
    next_q_min = next_q_total % 60

    # Schedule 30-min reminder
    context.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": state["cycle_id"]},
    )

    # Schedule checklist jobs
    for time_key in CHECKLIST_TIMES:
        hour, minute = map(int, time_key.split(":"))
        context.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(hour, minute),
            name=f"checklist_{time_key}",
            data={"cycle_id": state["cycle_id"], "time_key": time_key},
        )

    active_text = "\n".join(
        f"🟢 {AGENTS[u]}" for u in AGENT_ORDER if u in active
    )

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "✅ Бот ишга тушди\n\n"
            f"👨🏻‍💻 Актив supportlar:\n"
            f"{active_text}\n\n"
            f"⏰ Биринчи эслатма: "
            f"{next_q_hour:02d}:{next_q_min:02d}"
        ),
    )

# =========================
# STOP COMMAND
# =========================

async def umidstop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    state["stopped"] = True
    state["cycle_id"] += 1

    cancel_jobs_by_name(context.job_queue, "reminder")
    cancel_jobs_by_name(context.job_queue, "nudge")
    for t in CHECKLIST_TIMES:
        cancel_jobs_by_name(context.job_queue, f"checklist_{t}")

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🛑 Бот тўхтатилди.\n"
            "(@umidpulatov томонидан)"
        ),
    )

# =========================
# MAIN
# =========================

def main():
    application = Application.builder().token(TOKEN).build()

    state["cycle_id"] += 1

    # Auto-start 30-min reminder
    application.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": state["cycle_id"]},
    )

    # Auto-start checklist jobs
    for time_key in CHECKLIST_TIMES:
        hour, minute = map(int, time_key.split(":"))
        application.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(hour, minute),
            name=f"checklist_{time_key}",
            data={"cycle_id": state["cycle_id"], "time_key": time_key},
        )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("umidstop", umidstop_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
