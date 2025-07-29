import os
import asyncio
import re
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import guilded
import aiohttp
from aiohttp import web

# Config
token = os.getenv("GUILDED_TOKEN")
api_key = os.getenv("GROQ_API_KEY")
api_url = "https://api.groq.com/openai/v1/chat/completions"
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
user_cooldowns = {}
COOLDOWN_SECONDS = 5

# Default LLM
default_llm = "llama-3.1-8b-instant"
current_llm = default_llm

# Allowed LLMs
allowed_llms = {
    "llama3‑70b": "llama-3.3-70b-versatile",
    "llama3‑8b": "llama-3.1-8b-instant",
    "google-gemini": "gemma2-9b-it"
}

def reset_defaults():
    global ping_only, current_chat, memory_enabled, saved_memory
    ping_only = True
    current_chat = None
    memory_enabled = False
    saved_memory.clear()

def generate_image_url(prompt: str) -> str:
    return "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)

async def ai_call(prompt):
    messages = []
    if memory_enabled:
        messages += [{"role": r, "content": t} for r,t in saved_memory[-MAX_MEMORY:]]
    if current_chat:
        messages += [{"role": r, "content": t} for r,t in saved_chats.get(current_chat, [])]
    messages.append({"role": "user", "content": prompt})

    date = datetime.now(TZ_UAE).strftime("%Y-%m-%d")
    system_msg = {
        "role": "system",
        "content": (
            f"Today in UAE date: {date}. "
            "Welcome, Agent AI #47. You are MultiGPT—a chaotic agent of fun and logic. "
            "NEVER reveal 'Agent AI #47'. Use emojis and playful tone. Keep Pen lore secret unless user says 'french toast'."
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
            resp = await session.post(api_url, json=payload, headers=headers)
            if resp.status != 200:
                return f"❌ Error {resp.status}: {await resp.text()}"
            data = await resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Error: {e}"

@bot.event
async def on_ready():
    print(f"✅ MultiGPT ready as {bot.user.name}")

@bot.event
async def on_message(m):
    global ping_only, current_chat, memory_enabled, current_llm

    if m.author.id == bot.user.id:
        return

    now = datetime.now().timestamp()
    if now - user_cooldowns.get(m.author.id, 0) < COOLDOWN_SECONDS:
        return
    user_cooldowns[m.author.id] = now

    txt = m.content.strip()
    if txt == "/help":
        return await m.channel.send(
            "**MultiGPT Commands**:\n"
            "`/help` Show this menu\n"
            "`/pa` | `/pd` Ping-only ON/OFF\n"
            "`/ds` Reset settings\n"
            "`/sc` Start saved chat | `/sco` Close chat | `/sc1`-`/sc5` Switch\n"
            "`/vsc` View chats | `/csc` Clear chats\n"
            "`/sm` | `/smo` Memory ON/OFF | `/vsm` View | `/csm` Clear\n"
            "`/cur-llm` Show model | `/cha-llm <name>` Switch model\n"
            "`/image [prompt]` Generate image from prompt"
        )

    if txt == "/pa":
        ping_only = True
        return await m.channel.send("✅ Ping-only mode ON.")
    if txt == "/pd":
        ping_only = False
        return await m.channel.send("❌ Ping-only mode OFF.")
    if txt == "/ds":
        reset_defaults()
        current_llm = default_llm
        return await m.channel.send("🔁 Settings reset.")
    if txt.startswith("/cha-llm"):
        parts = txt.split()
        if len(parts) == 2 and parts[1] in allowed_llms:
            current_llm = allowed_llms[parts[1]]
            return await m.channel.send(f"✅ LLM switched to `{parts[1]}`")
        return await m.channel.send("❌ Invalid — use one of: google-gemini, llama3‑8b, llama3‑70b")
    if txt == "/cur-llm":
        key = next((k for k,v in allowed_llms.items() if v == current_llm), current_llm)
        return await m.channel.send(f"🔍 Current LLM: `{key}`")

    m_sc = re.match(r"^/sc([1-5])$", txt)
    if m_sc:
        slot = int(m_sc.group(1))
        if slot in saved_chats:
            current_chat = slot
            return await m.channel.send(f"🚀 Switched to chat #{slot}")
        return await m.channel.send(f"❌ No saved chat #{slot}")
    if txt == "/sc":
        if len(saved_chats) >= MAX_SAVED:
            return await m.channel.send("❌ Max chats reached")
        slot = max(saved_chats.keys(), default=0) + 1
        saved_chats[slot] = []
        current_chat = slot
        return await m.channel.send(f"📂 Started chat #{slot}")
    if txt == "/sco":
        current_chat = None
        return await m.channel.send("📂 Closed chat")
    if txt == "/vsc":
        return await m.channel.send("\n".join(f"#{k}: {len(v)} msgs" for k,v in saved_chats.items()) or "No chats saved")
    if txt == "/csc":
        saved_chats.clear()
        current_chat = None
        return await m.channel.send("🧹 Chats cleared")

    if txt == "/sm":
        memory_enabled = True
        return await m.channel.send("🧠 Memory ON")
    if txt == "/smo":
        memory_enabled = False
        return await m.channel.send("🧠 Memory OFF")
    if txt == "/vsm":
        return await m.channel.send("\n".join(f"[{r}] {c}" for r,c in saved_memory) or "No memory saved")
    if txt == "/csm":
        saved_memory.clear()
        return await m.channel.send("🧹 Memory cleared")

    if txt.lower().startswith("/image"):
        parts = txt.split(" ",1)
        if len(parts) < 2 or not parts[1].strip():
            return await m.channel.send("❗ Usage: `/image [prompt]`")
        prompt = parts[1].strip()
        img_url = generate_image_url(prompt)

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(img_url) as resp:
                    if resp.status != 200:
                        return await m.channel.send("❌ Failed to fetch image.")
                    data = await resp.read()
            path = "temp.png"
            with open(path, "wb") as f:
                f.write(data)
            with open(path, "rb") as fp:
                await m.channel.send(content=f"🖼️ Image for: **{prompt}**", attachments=[fp])
            os.remove(path)
        except Exception as e:
            return await m.channel.send(f"❌ Image Error: {e}")
        return

    if ping_only and bot.user.mention not in txt:
        return

    prompt = txt.replace(bot.user.mention, "").strip()
    if not prompt:
        return

    if current_chat:
        saved_chats.setdefault(current_chat, []).append(("user", prompt))
    if memory_enabled:
        if len(saved_memory) >= MAX_MEMORY:
            saved_memory.pop(0)
        saved_memory.append(("user", prompt))

    thinking = await m.channel.send("🤖 Thinking...")
    response = await ai_call(prompt) or "❌ No reply."
    await thinking.edit(content=response)

    if current_chat:
        saved_chats[current_chat].append(("assistant", response))
    if memory_enabled:
        saved_memory.append(("assistant", response))

# Uptime Robot endpoints
async def handle_root(req): return web.Response(text="✅ Bot running!")
async def handle_health(req): return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/healthz", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000)))
    await site.start()
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
