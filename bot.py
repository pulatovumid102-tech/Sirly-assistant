import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
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
# MESSAGE
# =========================

REMINDER_BODY = (
    "\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "💬 Mijozlardan kelgan murojaatlarni tekshiring\n\n"
    "🤝 Hamkorlardan kelgan murojaatlarni tekshiring\n\n"
    "📋 Checklistga qarang\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "Xabarni qabul qilgan bo'lsangiz: /xop"
)

# =========================
# STATE
# =========================

state = {
    "xop_received": set(),
    "xop_times": {},
    "reminder_sent_at": None,
    "warning_message_id": None,
    "cycle_id": 0,
    "stopped": False,
}

# =========================
# ACTIVE AGENTS
# =========================

def get_active_agents():

    now = datetime.now(TIMEZONE)

    weekday = now.weekday()
    hour = now.hour

    active = set()

    # Ozodbek
    # Mon-Sat 10:00-20:00

    if weekday <= 5:
        if 10 <= hour < 20:
            active.add("sirlyinfo")

    # Muhammadhumoyun
    # Mon-Fri 14:00-23:59
    # Sat 10:00-23:59

    if weekday <= 4:
        if hour >= 14:
            active.add("Muhammadhumoyun_Mudarris")

    elif weekday == 5:
        if hour >= 10:
            active.add("Muhammadhumoyun_Mudarris")

    return active

# =========================
# REMINDER MESSAGE
# =========================

def get_reminder_message():

    active = get_active_agents()

    if not active:
        return ""

    agent_block = "\n\n".join(
        AGENT_INFO[u]
        for u in AGENT_ORDER
        if u in active
    )

    return agent_block + REMINDER_BODY

# =========================
# NEXT QUARTER
# =========================

def seconds_until_next_quarter():

    now = datetime.now(TIMEZONE)

    elapsed = (
        now.minute * 60
        + now.second
        + now.microsecond / 1_000_000
    )

    next_quarter_start = (
        ((now.minute // 15) + 1) * 15 * 60
    )

    return max(next_quarter_start - elapsed, 1.0)

# =========================
# DELETE WARNING
# =========================

async def delete_warning(bot):

    msg_id = state.get("warning_message_id")

    if msg_id:

        try:
            await bot.delete_message(
                chat_id=CHAT_ID,
                message_id=msg_id
            )

        except Exception:
            pass

        state["warning_message_id"] = None

# =========================
# CANCEL JOBS
# =========================

def cancel_jobs_by_name(job_queue, name):

    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()

# =========================
# NEXT REMINDER
# =========================

def schedule_next_quarter_reminder(
    job_queue,
    cycle_id
):

    cancel_jobs_by_name(
        job_queue,
        "reminder"
    )

    job_queue.run_once(
        reminder_job,
        when=seconds_until_next_quarter(),
        name="reminder",
        data={"cycle_id": cycle_id},
    )

# =========================
# NUDGE LOOP
# =========================

def start_nudge_loop(
    job_queue,
    cycle_id
):

    cancel_jobs_by_name(
        job_queue,
        "nudge"
    )

    job_queue.run_repeating(
        nudge_job,
        interval=60,
        first=60,
        name="nudge",
        data={"cycle_id": cycle_id},
    )

# =========================
# REMINDER JOB
# =========================

async def reminder_job(
    context: ContextTypes.DEFAULT_TYPE
):

    cycle_id = context.job.data["cycle_id"]

    if (
        cycle_id != state["cycle_id"]
        or state["stopped"]
    ):
        return

    # reset
    state["xop_received"] = set()
    state["xop_times"] = {}
    state["reminder_sent_at"] = None
    state["warning_message_id"] = None

    active = get_active_agents()

    if active:

        message = get_reminder_message()

        if message:

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=message
            )

            state["reminder_sent_at"] = datetime.now(
                TIMEZONE
            )

        start_nudge_loop(
            context.job_queue,
            state["cycle_id"]
        )

    # next cycle
    schedule_next_quarter_reminder(
        context.job_queue,
        state["cycle_id"]
    )

# =========================
# NUDGE JOB
# =========================

async def nudge_job(
    context: ContextTypes.DEFAULT_TYPE
):

    cycle_id = context.job.data["cycle_id"]

    if (
        cycle_id != state["cycle_id"]
        or state["stopped"]
    ):
        return

    active = get_active_agents()

    pending = active - state["xop_received"]

    if not pending:
        return

    agent_block = "\n\n".join(
        AGENT_INFO[u]
        for u in AGENT_ORDER
        if u in pending
    )

    await delete_warning(context.bot)

    sent = await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"{agent_block}\n\n"
            "━━━━━━━━━━━━━━\n\n"
            "⚠️ Aloqaga chiqing.\n\n"
            "━━━━━━━━━━━━━━\n\n"
            "Agar xabarni qabul qilgan bo'lsangiz: /xop"
        ),
    )

    state["warning_message_id"] = sent.message_id

# =========================
# START
# =========================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if (
        update.effective_user.username
        != ADMIN_USERNAME
    ):
        return

    state["stopped"] = False

    state["xop_received"] = set()
    state["xop_times"] = {}
    state["reminder_sent_at"] = None
    state["warning_message_id"] = None

    state["cycle_id"] += 1

    cancel_jobs_by_name(
        context.job_queue,
        "reminder"
    )

    cancel_jobs_by_name(
        context.job_queue,
        "nudge"
    )

    now = datetime.now(TIMEZONE)

    next_q_total = (
        ((now.minute // 15) + 1) * 15
    )

    next_q_hour = (
        (now.hour + next_q_total // 60) % 24
    )

    next_q_min = next_q_total % 60

    schedule_next_quarter_reminder(
        context.job_queue,
        state["cycle_id"]
    )

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "Bot ishga tushdi.\n"
            f"Birinchi eslatma: "
            f"{next_q_hour:02d}:"
            f"{next_q_min:02d}"
        ),
    )

# =========================
# XOP
# =========================

async def xop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if state["stopped"]:
        return

    username = update.effective_user.username

    if not username:
        return

    active = get_active_agents()

    if username not in active:

        await update.message.reply_text(
            "Bu xabar support uchun yuborilgan 🙂"
        )

        return

    if username in state["xop_received"]:
        return

    xop_time = datetime.now(TIMEZONE)

    state["xop_received"].add(username)

    state["xop_times"][username] = xop_time

    name = AGENTS.get(
        username,
        username
    )

    sent_at = (
        state["reminder_sent_at"]
        or xop_time
    )

    mins = int(
        (
            xop_time - sent_at
        ).total_seconds() // 60
    )

    confirmation = (
        f"✅ {name} "
        f"xabarni {mins} daqiqada "
        f"qabul qildi."
    )

    await delete_warning(context.bot)

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=confirmation
    )

    if not (
        active - state["xop_received"]
    ):

        cancel_jobs_by_name(
            context.job_queue,
            "nudge"
        )

# =========================
# STOP
# =========================

async def umidstop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if (
        update.effective_user.username
        != ADMIN_USERNAME
    ):
        return

    state["stopped"] = True

    state["cycle_id"] += 1

    cancel_jobs_by_name(
        context.job_queue,
        "reminder"
    )

    cancel_jobs_by_name(
        context.job_queue,
        "nudge"
    )

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "Bot toxtatildi.\n"
            "(@umidpulatov tomonidan)"
        ),
    )

# =========================
# MAIN
# =========================

def main():

    application = Application.builder().token(TOKEN).build()

    # AUTO START
    state["cycle_id"] += 1

    schedule_next_quarter_reminder(
        application.job_queue,
        state["cycle_id"]
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        CommandHandler(
            "xop",
            xop_command
        )
    )

    application.add_handler(
        CommandHandler(
            "umidstop",
            umidstop_command
        )
    )

    logger.info("Bot starting...")

    application.run_polling(
        drop_pending_updates=True
    )

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
