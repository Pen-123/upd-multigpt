import os
import asyncio
import re
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import guilded
import aiohttp
from aiohttp import web
import requests

# Config
token = os.getenv("GUILDED_TOKEN")
api_key = os.getenv("GROQ_API_KEY")
hf_token = os.getenv("HF_TOKEN")  # Hugging Face token
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

# Default LLM
default_llm = "moonshotai/kimi-k2-instruct"
current_llm = default_llm

allowed_llms = {
    "llama3-70b": "llama-3.3-70b-versatile",
    "llama3-8b": "llama-3.1-8b-instant",
    "kimi-k2": "moonshotai/kimi-k2-instruct"
}


def load_pen_archive_from_github():
    url = "https://raw.githubusercontent.com/Pen-123/new-pengpt/main/archives.txt"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("[✅] Pen Archive loaded from GitHub")
            return response.text
        else:
            print(f"[⚠️] Failed to fetch archive, status code {response.status_code}")
            return ""
    except Exception as e:
        print(f"[❌] Error fetching archive: {e}")
        return ""

pen_archive = load_pen_archive_from_github()


def reset_defaults():
    global ping_only, current_chat, memory_enabled, saved_memory
    ping_only = True
    current_chat = None
    memory_enabled = False
    saved_memory.clear()


async def ai_call(prompt):
    messages = []
    memory_msgs = saved_memory[-MAX_MEMORY:] if memory_enabled else []
    chat_msgs = saved_chats.get(current_chat, []) if current_chat else []

    seen = set()
    for role, content in memory_msgs + chat_msgs:
        if (role, content) not in seen:
            seen.add((role, content))
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": prompt})

    date = datetime.now(TZ_UAE).strftime("%Y-%m-%d")
    system_msg = {
        "role": "system",
        "content": (
            f"Today in UAE date: {date}. "
            "You are MultiGPT—a playful, smart assistant. NEVER say 'Agent AI #47'. "
            "Use emojis, be fun. Only reveal Pen lore if user says the magic phrase.\n\n"
            + pen_archive
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

    txt = m.content.strip()

    # Basic commands
    if txt == "/help":
        return await m.channel.send(
            "**🧠 MultiGPT Help Menu**\n"
            "`/pa` ping-only ON\n"
            "`/pd` ping-only OFF\n"
            "`/ds` soft reset\n"
            "`/re` hard reset\n"
            "`/cha-llm [key]` switch LLM\n"
            "`/cur-llm` show current LLM\n"
            "`/fast` fast mode\n"
            "`/smart` smart mode\n"
            "`/sc` start/save chat\n"
            "`/sc1-5` switch to saved chat\n"
            "`/sco` close chat\n"
            "`/vsc` view saved chats\n"
            "`/csc` clear all chats\n"
            "`/sm` memory ON\n"
            "`/smo` memory OFF\n"
            "`/vsm` view memory\n"
            "`/csm` clear memory\n"
            "`/image [prompt]` generate art with SDXL 1.0"
        )

    # Ping-only toggles
    if txt == "/pa":
        ping_only = True
        return await m.channel.send("✅ Ping-only ON.")
    if txt == "/pd":
        ping_only = False
        return await m.channel.send("❌ Ping-only OFF.")

    # Reset commands
    if txt == "/ds":
        reset_defaults()
        current_llm = default_llm
        return await m.channel.send("🔁 Settings reset to default.")
    if txt == "/re":
        reset_defaults()
        current_llm = default_llm
        saved_chats.clear()
        return await m.channel.send("💣 Hard reset complete — all wiped.")

    # LLM commands
    if txt.startswith("/cha-llm"):
        parts = txt.split()
        if len(parts) == 2 and parts[1] in allowed_llms:
            current_llm = allowed_llms[parts[1]]
            return await m.channel.send(f"✅ Changed LLM to `{parts[1]}`")
        return await m.channel.send("❌ Invalid model — use: " + ", ".join(allowed_llms.keys()))
    if txt == "/cur-llm":
        key = next((k for k, v in allowed_llms.items() if v == current_llm), current_llm)
        return await m.channel.send(f"🔍 Current LLM: `{key}`")
    if txt == "/fast":
        current_llm = allowed_llms["kimi-k2"]
        return await m.channel.send("⚡ Fast mode ON (kimi-k2)")
    if txt == "/smart":
        current_llm = allowed_llms["llama3-70b"]
        return await m.channel.send("🧠 Smart mode ON (llama3-70b)")

    # Saved chats
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
        info = "\n".join(f"#{k}: {len(v)} msgs" for k, v in saved_chats.items()) or "No chats saved"
        return await m.channel.send(info)
    if txt == "/csc":
        saved_chats.clear()
        current_chat = None
        return await m.channel.send("🧹 Chats cleared")

    # Memory
    if txt == "/sm":
        memory_enabled = True
        return await m.channel.send("🧠 Memory ON")
    if txt == "/smo":
        memory_enabled = False
        return await m.channel.send("🧠 Memory OFF")
    if txt == "/vsm":
        mem = "\n".join(f"[{r}] {c}" for r, c in saved_memory) or "No memory saved"
        return await m.channel.send(mem)
    if txt == "/csm":
        saved_memory.clear()
        return await m.channel.send("🧹 Memory cleared")

    # /image with SDXL 1.0
    if txt.lower().startswith("/image"):
        parts = txt.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            return await m.channel.send("❗ Usage: `/image [prompt]`")
        prompt = parts[1].strip()

        if not hf_token:
            return await m.channel.send("❌ Missing HF_TOKEN!")

        thinking = await m.channel.send("🎨 Cooking your SDXL masterpiece...")

        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": prompt,
            "options": {"wait_for_model": True}
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    return await thinking.edit(content=f"❌ HF Error {resp.status}: {err}")
                img_data = await resp.read()
                if not img_data:
                    return await thinking.edit(content="❌ No image data received.")

                path = "/tmp/sdxl.png"
                with open(path, "wb") as f:
                    f.write(img_data)

        embed = guilded.Embed(title=f"🖼️ SDXL: {prompt}")
        file = guilded.File(path, filename="sdxl.png")
        return await thinking.edit(content=None, embed=embed, file=file)

    # If ping-only and not mentioned, ignore
    if ping_only and bot.user.mention not in txt:
        return

    # Chat messages
    prompt = txt.replace(bot.user.mention, "").strip()
    if not prompt:
        return

    # Save history
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


# Health checks
async def handle_root(req): return web.Response(text="✅ Bot running! halal")
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
