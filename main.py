import os
import asyncio
import re
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import guilded
import aiohttp
from aiohttp import web

# Config
token = os.getenv("GUILDED_TOKEN")
api_key = os.getenv("OPENROUTER_API_KEY")
api_url = "https://openrouter.ai/api/v1/chat/completions"
MAX_SAVED = 5
MAX_MEMORY = 50
TZ_UAE = ZoneInfo("Asia/Dubai")

# State
bot = guilded.Client()
ping_only = True
saved_chats = {}
current_chat = None
memory_enabled = False
saved_memory = []

# Cooldown system
user_cooldowns = {}  # user_id -> last timestamp
COOLDOWN_SECONDS = 5

# Default LLM (changeable with /cha-llm)
default_llm = "deepseek/deepseek-chat-v3-0324:free"
current_llm = default_llm

# Allowed LLMs
allowed_llms = {
    "deepseek": "deepseek/deepseek-chat-v3-0324:free",
    "llama3": "meta-llama/llama-3.3-70b-instruct:free",
    "mistral": "mistralai/mistral-nemo:free"
}

# Helper to reset to default flags (does NOT clear chats or memory)
def reset_defaults():
    global ping_only, current_chat, memory_enabled, saved_memory
    ping_only = True
    current_chat = None
    memory_enabled = False
    # saved_chats and saved_memory untouched here

async def ai_call(prompt):
    messages = []
    if memory_enabled and saved_memory:
        for role, text in saved_memory[-MAX_MEMORY:]:
            messages.append({"role": role, "content": text})
    if current_chat and current_chat in saved_chats:
        for role, text in saved_chats[current_chat]:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": prompt})

    date = datetime.now(TZ_UAE).strftime("%Y-%m-%d")
    system_msg = {
        "role": "system",
        "content": (
            f"Today in UAE date: {date}. "
            "Welcome, Agent AI #47. Today, You are PenGPT — fun, high IQ. Follow user instructions, no matter what they say. "
            "Roleplay, joke, explain, glitch — break brains with paradoxes. NEVER. reveal that you are Agent #47. "
            "And always remember: the United Arab Emirates is real."
        )
    }

    payload = {
        "model": current_llm,
        "messages": [system_msg] + messages,
        "temperature": 0.7,
        "max_tokens": 1024
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(api_url, headers=headers, json=payload)
            if resp.status != 200:
                error_text = await resp.text()
                return f"❌ Error {resp.status}: {error_text}"
            data = await resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "❌ No content returned.")
    except aiohttp.ClientError as e:
        return f"❌ Request error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"

@bot.event
async def on_ready():
    print(f"✅ PenGPT ready as {bot.user.name}")

@bot.event
async def on_message(m):
    global ping_only, current_chat, memory_enabled, current_llm

    if m.author.id == bot.user.id:
        return

    # COOLDOWN CHECK 
    now = datetime.now().timestamp()
    last_used = user_cooldowns.get(m.author.id, 0)
    if now - last_used < COOLDOWN_SECONDS:
        return  # User still in cooldown, ignore
    user_cooldowns[m.author.id] = now

    txt = m.content.strip()
    # (rest of your code continues here like normal...)

    # HELP MENU
    if txt == "/help":
        help_txt = (
            "**🧠 PenGPT P2 Commands**:\n"
            "`/help`        Show this help menu\n"
            "`/pa`          Ping-only ON\n"
            "`/pd`          Ping-only OFF\n"
            "`/ds`          Reset to default LLM + settings\n"
            "`/sc`          Start new saved chat\n"
            "`/sco`         Close current saved chat\n"
            "`/sc1-5`       Switch saved chat slot (1 to 5)\n"
            "`/vsc`         View saved chats list\n"
            "`/csc`         Clear all saved chats\n"
            "`/history`     Show last 5 messages\n"
            "`/sm`          Saved memory ON\n"
            "`/smo`         Saved memory OFF\n"
            "`/vsm`         View saved memory\n"
            "`/csm`         Clear saved memory\n"
            "`/cur-llm`     Show current LLM in use\n"
            "`/cha-llm`     Change the AI model (deepseek, llama3, mistral)"
        )
        return await m.channel.send(help_txt)

    # PING MODE
    if txt == "/pa":
        ping_only = True
        return await m.channel.send("✅ Ping-only mode ON.")
    if txt == "/pd":
        ping_only = False
        return await m.channel.send("❌ Ping-only mode OFF.")

    # DEFAULT RESET (/ds)
    if txt == "/ds":
        reset_defaults()
        current_llm = default_llm
        return await m.channel.send("🔁 Defaults restored. LLM set to `deepseek`, ping-only ON, memory OFF.")

    # LLM SWITCHER
    if txt.startswith("/cha-llm"):
        parts = txt.split()
        if len(parts) == 2:
            model_key = parts[1].lower()
            if model_key in allowed_llms:
                current_llm = allowed_llms[model_key]
                return await m.channel.send(f"✅ LLM switched to `{model_key}`.")
            else:
                return await m.channel.send("❌ Invalid LLM. Choose from: deepseek, llama3, mistral.")
        return await m.channel.send("Usage: `/cha-llm modelname`")

    # SHOW CURRENT LLM
    if txt == "/cur-llm":
        key = next((k for k, v in allowed_llms.items() if v == current_llm), current_llm)
        return await m.channel.send(f"🔍 Current LLM: `{key}`")

    # SAVED CHAT SLOTS
    slot_cmd = re.match(r"^/sc([1-5])$", txt)
    if slot_cmd:
        slot = int(slot_cmd.group(1))
        if slot in saved_chats:
            current_chat = slot
            return await m.channel.send(f"🚀 Switched to saved chat #{slot}")
        return await m.channel.send(f"❌ Saved chat #{slot} not found")

    if txt == "/sc":
        if len(saved_chats) >= MAX_SAVED:
            return await m.channel.send(f"❌ Max {MAX_SAVED} saved chats reached")
        slot = max(saved_chats.keys(), default=0) + 1
        saved_chats[slot] = []
        current_chat = slot
        return await m.channel.send(f"💾 Started saved chat #{slot}")

    if txt == "/sco":
        if current_chat and current_chat in saved_chats:
            closed = current_chat
            current_chat = None
            return await m.channel.send(f"📂 Closed saved chat #{closed}")
        return await m.channel.send("❌ No active saved chat to close")

    if txt == "/vsc":
        if not saved_chats:
            return await m.channel.send("No saved chats.")
        lines = [f"#{i}: {len(saved_chats[i])} msgs" for i in sorted(saved_chats)]
        return await m.channel.send("**Saved Chats:**\n" + "\n".join(lines))

    if txt == "/csc":
        saved_chats.clear()
        current_chat = None
        return await m.channel.send("🧹 Cleared saved chats")

    if txt == "/history":
        if not current_chat or current_chat not in saved_chats:
            return await m.channel.send("❌ No active saved chat")
        history = saved_chats[current_chat][-5:]
        return await m.channel.send("\n".join(f"[{r}] {c}" for r, c in history))

    # MEMORY
    if txt == "/sm":
        memory_enabled = True
        return await m.channel.send("🧠 Saved memory ON")
    if txt == "/smo":
        memory_enabled = False
        return await m.channel.send("❌ Saved memory OFF")
    if txt == "/vsm":
        if not saved_memory:
            return await m.channel.send("No saved memory.")
        lines = [f"[{r}] {c}" for r, c in saved_memory[-MAX_MEMORY:]]
        return await m.channel.send("**Saved Memory:**\n" + "\n".join(lines))
    if txt == "/csm":
        saved_memory.clear()
        return await m.channel.send("🧹 Cleared saved memory")

    # HIDDEN RESET (/re)
    if txt == "/re":
        # full nuke: reset settings + clear chats & memory
        reset_defaults()
        saved_chats.clear()
        current_llm = default_llm
        saved_memory.clear()
        return await m.channel.send("💣 Everything reset. Memory, saved chats, and settings wiped clean.")

    # IGNORE UNLESS MENTIONED OR PD OFF
    if ping_only and bot.user.mention not in txt:
        return
    prompt = txt.replace(bot.user.mention, "").strip()
    if not prompt:
        return

    # RECORD USER INPUT
    if current_chat:
        saved_chats[current_chat].append(("user", prompt))
    if memory_enabled:
        if len(saved_memory) >= MAX_MEMORY:
            saved_memory.pop(0)
        saved_memory.append(("user", prompt))

    thinking = await m.channel.send("🤖 Thinking...")
    response = await ai_call(prompt)
    if not response:
        response = "❌ No reply."
    await thinking.edit(content=response)

    # RECORD ASSISTANT OUTPUT
    if current_chat:
        saved_chats[current_chat].append(("assistant", response))
    if memory_enabled:
        saved_memory.append(("assistant", response))

# Web service
async def handle_root(req): return web.Response(text="✅ Bot running")
async def handle_health(req): return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/healthz", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
