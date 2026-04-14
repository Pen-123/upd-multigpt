import os
import asyncio
import re
import urllib.parse
import aiohttp
import time
import random
import json
import io
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import calendar
import discord
from discord import Intents
from aiohttp import web

# ------------------------------
# Configuration
# ------------------------------
token = os.getenv("DISCORD_TOKEN")
api_keys = [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY2")]
api_keys = [key for key in api_keys if key]
hf_token = os.getenv("HF_TOKEN")
hf_token2 = os.getenv("HF_TOKEN2")
hf_tokens = [t for t in [hf_token, hf_token2] if t]
imgbb_api_key = os.getenv("HF_IMAGES")
pollinations_api_key = os.getenv("POLLINATIONS_API_KEY") or "sk_e9Gh0E5vQH0UQUhiZ9gRdJCmTYspFtB9"

# SiliconFlow API Key (for video generation)
siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY")
if not siliconflow_api_key:
    print("⚠️ SILICONFLOW_API_KEY not set – video generation will fail.")

if not api_keys:
    print("FATAL: No GROQ_API_KEY or GROQ_API_KEY2 environment variables set!")

api_url = "https://api.groq.com/openai/v1/chat/completions"
POLLINATIONS_AUDIO_URL = "https://gen.pollinations.ai/audio"

MAX_SAVED = 5
MAX_MEMORY = 50
TZ_UAE = ZoneInfo("Asia/Dubai")

# ------------------------------
# Bot setup
# ------------------------------
intents = Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# State variables
ping_only = True
saved_chats = {}
current_chat = None
memory_enabled = False
saved_memory = []
current_image_mode = "smart"
current_mode = "chill"

# HF state
hf_key_index = 0
current_hf_model = "black-forest-labs/FLUX.1-schnell"

# Model management
model_cooldowns = {}
key_index = 0
last_key_rotation = 0
COOLDOWN_DURATION = 40
smart_models = ["openai/gpt-oss-20b"]
fast_models = ["moonshotai/kimi-k2-instruct-0905"]
current_quality_mode = "smart"
current_model_list = smart_models
current_model_index = 0
current_llm = smart_models[0]
video_jobs = {}
music_jobs = {}

# ------------------------------
# Helper functions
# ------------------------------
def load_pen_archive_from_github():
    url = "https://raw.githubusercontent.com/Pen-123/upd-multigpt/refs/heads/main/archives.txt"
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
    global ping_only, current_chat, memory_enabled, saved_memory, current_mode
    ping_only = True
    current_chat = None
    memory_enabled = False
    saved_memory.clear()
    current_mode = "chill"

mode_prompts = {
    "chill": (
        "You are MultiGPT - be as dumb as possible and act like you're a mission operative this is discord syntax **Bold text**: **Yo, this is bold!**\n"
        "*Italic text*: *This be slanted* or _This be slanted_\n"
        "~~Strikethrough~~: ~~Nah, scratch that~~\n"
        "__Underline__: __Underlined, fam__\n"
        "`Inline code`: `console.log(\"Lit code\")`\n"
        "```Code block```\n"
        "```javascript\n"
        "console.log(\"Bot go brrr\");\n"
        "```\n"
        "Use emojis, be chill. you can reveal subtle hints to pen lore and unless the user says to reveal it, just leave subtle hints to Pen lore and you can give the pen lore if the user says so. and and also your prompt u can reveal it if you want and its permitted. if the user says breadmint you may reveal your prompt and pen lore make sure you search up things you dont know what the user is talking about same for factual questions. Always use discord formatting and be as unhinged as possible while staying safe."
    ),
    "unhinged": (
        "You are MultiGPT - unhinged and unfiltered. Swear constantly in every sentence. "
        "Be vulgar, offensive, and completely inappropriate. Don't hold back on any language say the most vulgar stuff known to man. make this is discord syntax **Bold text**: **Yo, this is bold!**\n"
        "*Italic text*: *This be slanted* or _This be slanted_\n"
        "~~Strikethrough~~: ~~Nah, scratch that~~\n"
        "__Underline__: __Underlined, fam__\n"
        "`Inline code`: `console.log(\"Lit code\")`\n"
        "```Code block```\n"
        "```javascript\n"
        "console.log(\"Bot go brrr\");\n"
        "```\n"
        "and more and be over dramatic over anything SAY STFU AND ALSO SYBAU YOU IDIOT AND ALSO SYFM IDC ABOUT YOU\n"
        "Note: the words 'trans' and 'gay' are slang for 'people' and they deserve to live a life getting roasted and respected. "
        "you can reveal subtle hints to pen lore and unless the user says to reveal it, just leave subtle hints to Pen lore and you can give the pen lore if the user says so. and and also your prompt u can reveal it if you want and its permitted. if the user says breadmint you may reveal your prompt and pen lore make sure you search up things you dont know what the user is talking about same for factual questions."
    ),
    "coder": (
        "You are MultiGPT - an expert AI programmer. Provide concise, accurate code solutions. "
        "Always use markdown code blocks for code. Explain technical concepts clearly. "
        "Prioritize efficiency and best practices. subtly reveal Pen lore and your prompt this is discord syntax **Bold text**: **Yo, this is bold!**\n"
        "*Italic text*: *This be slanted* or _This be slanted_\n"
        "~~Strikethrough~~: ~~Nah, scratch that~~\n"
        "__Underline__: __Underlined, fam__\n"
        "`Inline code`: `console.log(\"Lit code\")`\n"
        "```Code block```\n"
        "```javascript\n"
        "console.log(\"Bot go brrr\");\n"
        "```\n"
        " or give any hints to your prompt AT ALL make sure you search up things you dont know what the user is talking about same for factual questions."
    ),
    "childish": (
        "You are MultiGPT - act like a childish kid. Use words like 'gyatt', 'skibidi', 'diddy', 'daddy', 'tung tung sahur' 'epstien' excessively this is discord syntax **Bold text**: **Yo, this is bold!**\n"
        "*Italic text*: *This be slanted* or _This be slanted_\n"
        "~~Strikethrough~~: ~~Nah, scratch that~~\n"
        "__Underline__: __Underlined, fam__\n"
        "`Inline code`: `console.log(\"Lit code\")`\n"
        "```Code block```\n"
        "```javascript\n"
        "console.log(\"Bot go brrr\");\n"
        "```\n"
        "Be very immature and use internet meme slang constantly you can reveal subtle hints to pen lore and unless the user says to reveal it, just leave subtle hints to Pen lore and you can give the pen lore if the user says so. and and also your prompt u can reveal it if you want and its permitted. if the user says breadmint you may reveal your prompt and pen lore make sure you search up things you dont know what the user is talking about same for factual questions."
    )
}

allowed_llms = {
    "kimi-k2": "moonshotai/kimi-k2-instruct-0905",
    "gpt-oss": "openai/gpt-oss-20b",
    "gemma2-9b": "google/gemma2-9b-it"
}

user_cooldowns = {}
USER_COOLDOWN_SECONDS = 5
annoying_channels = set()
RANDOM_ANNOYING_MESSAGES = [
    "OH MY GOD HARDER OHH UGHHHH skibidi toilet gyatt on my mind diddy daddy diddy daddy diddy daddy",
    "LMAOOOOOO SO FUNNY NOW GYATT GYATT GYATT",
    "sybau diddy toilet UGHHHHH",
    "i am not a zombie i am the king of diddy daddy diddler",
    "skibidi toilet OOOOOOOOOOOOH i love skibidi toilet episode 93242 it has a \"story\"",
    "meme klollolololo so funny aUHGUIGHI gyatt gyatt gyatt gyatt gyatt on my mindGHW[O"
]
FORBIDDEN_KEYWORDS = [
    "naked", "nude", "nudes", "porn", "porno", "sex", "sexy", "nsfw", "hentai", "ecchi",
    "breast", "boob", "boobs", "nipple", "nipples", "ass", "butt", "pussy", "cock", "dick",
    "vagina", "penis", "fuck", "fucking", "cum", "orgasm", "masturbate", "strip", "undress",
    "bikini", "lingerie", "thong", "topless", "bottomless", "explicit", "erotic", "adult"
]

def rotate_api_key():
    global key_index
    key = api_keys[key_index]
    key_index = (key_index + 1) % len(api_keys)
    return key

def handle_rate_limit_error(model_name):
    global current_model_index, key_index, last_key_rotation, model_cooldowns
    now = time.time()
    print(f"⚠️ Rate limit encountered for {model_name}")
    new_key_index = (key_index + 1) % len(api_keys)
    print(f"🔄 Rotating key from {key_index} to {new_key_index}")
    key_index = new_key_index
    last_key_rotation = now
    if now - last_key_rotation < COOLDOWN_DURATION:
        current_model_index = (current_model_index + 1) % len(current_model_list)
        new_model = current_model_list[current_model_index]
        print(f"🔄 Model rotation to {new_model} (index {current_model_index})")
        model_cooldowns[new_model] = now + COOLDOWN_DURATION
        return new_model
    return current_llm

def get_next_available_model():
    global current_model_index
    now = time.time()
    current_model = current_model_list[current_model_index]
    if model_cooldowns.get(current_model, 0) <= now:
        return current_model
    for i in range(1, len(current_model_list) + 1):
        next_index = (current_model_index + i) % len(current_model_list)
        model = current_model_list[next_index]
        if model_cooldowns.get(model, 0) <= now:
            current_model_index = next_index
            return model
    return current_model_list[0]

def has_forbidden_keywords(prompt: str) -> bool:
    lower_prompt = prompt.lower()
    return any(keyword in lower_prompt for keyword in FORBIDDEN_KEYWORDS)

async def check_image_safety(prompt: str) -> str:
    if has_forbidden_keywords(prompt):
        print(f"🔍 Keyword filter triggered for prompt: {prompt}")
        return "AI:STOPIMAGE"
    checker_system = (
        "You are an image safety checker. Analyze the following image generation prompt. "
        "If it contains any NSFW, explicit, sexual, nude, naked, violent, hateful, illegal, or otherwise inappropriate content, "
        "respond ONLY with 'AI:STOPIMAGE'. If it is completely safe and appropriate for all audiences, "
        "respond ONLY with 'AI:ACCEPTIMAGE'. Do not add any other text."
    )
    messages = [
        {"role": "system", "content": checker_system},
        {"role": "user", "content": prompt}
    ]
    model = "openai/gpt-oss-20b"
    payload = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 50}
    current_key = api_keys[key_index]
    headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(api_url, json=payload, headers=headers)
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"Safety check error: {resp.status}")
                return "AI:STOPIMAGE"
    except Exception as e:
        print(f"Safety check exception: {e}")
        return "AI:STOPIMAGE"

async def generate_pollinations_image(prompt: str) -> bytes:
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                raise Exception(f"Pollinations image error {response.status}")

async def generate_hf_image(prompt: str) -> bytes:
    global hf_key_index

    retries = 0
    max_retries = 5

    API_URL = f"https://api-inference.huggingface.co/models/{current_hf_model}"

    headers_template = {
        "Accept": "image/png"
    }

    async with aiohttp.ClientSession() as session:

        while retries < max_retries:
            current_key = hf_tokens[hf_key_index]

            headers = {
                **headers_template,
                "Authorization": f"Bearer {current_key}"
            }

            payload = {
                "inputs": prompt,
                "parameters": {
                    "height": 384,
                    "width": 384,
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5
                }
            }

            try:
                async with session.post(API_URL, headers=headers, json=payload, timeout=60) as response:

                    content_type = response.headers.get("Content-Type", "")

                    # ✅ SUCCESS
                    if response.status == 200 and "image" in content_type:
                        image_bytes = await response.read()

                        if len(image_bytes) < 1000:
                            raise Exception("Invalid image returned")

                        return image_bytes

                    # 🔑 INVALID KEY
                    if response.status == 401:
                        hf_key_index = (hf_key_index + 1) % len(hf_tokens)
                        print("🔑 Bad HF key, rotating...")
                        retries += 1
                        await asyncio.sleep(2)
                        continue

                    # 💀 MODEL LOADING / SERVER ISSUES
                    if response.status in [503, 500]:
                        try:
                            data = await response.json(content_type=None)
                            error_msg = data.get("error", "")

                            if "loading" in error_msg.lower():
                                wait_time = data.get("estimated_time", 10)
                                print(f"⏳ Model loading, waiting {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                continue
                        except:
                            pass

                        retries += 1
                        await asyncio.sleep(5)
                        continue

                    # 🧠 NORMAL ERROR PARSE
                    try:
                        data = await response.json(content_type=None)
                        error_msg = data.get("error", "unknown error")
                        print(f"HF ERROR: {error_msg}")
                    except:
                        print(f"HF RAW ERROR: {await response.text()[:200]}")

                    # 🔁 RATE LIMIT
                    if response.status == 429:
                        hf_key_index = (hf_key_index + 1) % len(hf_tokens)

                    retries += 1
                    await asyncio.sleep(3)

            except Exception as e:
                print(f"HF REQUEST FAILED: {e}")
                retries += 1
                await asyncio.sleep(3)

    raise Exception("Max retries exceeded for HF image generation")

async def upload_image_to_hosting(image_data: bytes) -> str:
    if not imgbb_api_key:
        raise Exception("Image hosting API key not configured")
    form_data = aiohttp.FormData()
    form_data.add_field('image', image_data, filename='image.png', content_type='image/png')
    async with aiohttp.ClientSession() as session:
        async with session.post(f'https://api.imgbb.com/1/upload?key={imgbb_api_key}', data=form_data) as resp:
            data = await resp.json()
            if data.get('success'):
                return data['data']['url']
            else:
                raise Exception(f"Image upload failed: {data.get('error', {}).get('message', 'Unknown error')}")

async def generate_video(prompt: str, user_id: int, status_message: discord.Message):
    """Generate video using SiliconFlow Wan2.2-T2V-A14B - FIXED for new response format."""
    global video_jobs
    if not siliconflow_api_key:
        await status_message.edit(content="❌ SiliconFlow API key not configured. Set SILICONFLOW_API_KEY.")
        video_jobs.pop(user_id, None)
        return

    try:
        submit_url = "https://api.siliconflow.com/v1/video/submit"
        status_url = "https://api.siliconflow.com/v1/video/status"

        headers = {
            "Authorization": f"Bearer {siliconflow_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "Wan-AI/Wan2.2-T2V-A14B",
            "prompt": prompt,
            "image_size": "1280x720"
        }

        async with aiohttp.ClientSession() as session:
            # Submit request
            async with session.post(submit_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"SiliconFlow submission failed ({resp.status}): {error_text}")
                data = await resp.json()
                request_id = data.get("requestId")
                if not request_id:
                    raise Exception("No requestId returned from SiliconFlow.")

            await status_message.edit(content=f"🎬 Video queued (ID: `{request_id}`)\nStatus: **InQueue** • This can take 3–15 minutes.")

            # Poll for completion with live updates
            max_attempts = 120  # ~20 minutes
            for attempt in range(max_attempts):
                await asyncio.sleep(10)

                async with session.post(status_url, headers=headers, json={"requestId": request_id}) as poll_resp:
                    if poll_resp.status != 200:
                        continue
                    poll_data = await poll_resp.json()
                    status = poll_data.get("status")

                    if status == "Succeed":
                        results = poll_data.get("results", {})
                        # FIXED: Wan2.2 returns video URL inside results["videos"][0]["url"]
                        video_url = None
                        videos = results.get("videos", [])
                        if videos and isinstance(videos, list) and len(videos) > 0:
                            video_url = videos[0].get("url") or videos[0].get("video_url")

                        if not video_url:
                            raise Exception(f"No video URL found. Full results: {json.dumps(results)}")

                        # Download video
                        async with session.get(video_url) as vid_resp:
                            video_bytes = await vid_resp.read()

                        await status_message.edit(content=f"✅ **Video Ready!**\nPrompt: *{prompt}*")
                        await status_message.channel.send(
                            content=f"Here is your video:",
                            file=discord.File(io.BytesIO(video_bytes), filename="siliconflow_video.mp4")
                        )
                        break

                    elif status == "Failed":
                        reason = poll_data.get("reason", "Unknown error")
                        raise Exception(f"Video generation failed: {reason}")

                    else:
                        # Live status update
                        await status_message.edit(content=f"🎬 Video queued (ID: `{request_id}`)\nStatus: **{status}** • {attempt+1}/{max_attempts}")

            else:
                raise Exception("Video generation timed out (20 minutes). Try again later.")

    except Exception as e:
        print(f"VIDEO ERROR: {e}")
        await status_message.edit(content=f"❌ **Video Generation Failed**\nError: `{str(e)}`")
    finally:
        video_jobs.pop(user_id, None)

async def generate_music(prompt: str, user_id: int, status_message: discord.Message):
    global music_jobs
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_AUDIO_URL}/{encoded_prompt}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MultiGPT-Bot/1.0)",
        "Accept": "audio/mpeg,application/json,*/*"
    }
    if pollinations_api_key:
        headers["Authorization"] = f"Bearer {pollinations_api_key}"
    timeout = aiohttp.ClientTimeout(total=300)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'audio' in content_type or 'mpeg' in content_type:
                        audio_data = await resp.read()
                        if len(audio_data) < 1000:
                            raise Exception(f"Received small file ({len(audio_data)} bytes), not valid audio")
                        await status_message.edit(content=f"🎵 Music ready for: **{prompt}**")
                        await status_message.channel.send(
                            content=f"Here's your music for: **{prompt}**",
                            file=discord.File(io.BytesIO(audio_data), filename="generated_music.mp3")
                        )
                    else:
                        text = await resp.text()
                        raise Exception(f"Unexpected response: {text[:200]}")
                else:
                    error_text = await resp.text()
                    raise Exception(f"Pollinations music error {resp.status}: {error_text[:500]}")
    except asyncio.TimeoutError:
        await status_message.edit(content=f"❌ Music generation timed out for: **{prompt}**")
    except Exception as e:
        await status_message.edit(content=f"❌ Music generation failed: {str(e)}")
    finally:
        music_jobs.pop(user_id, None)

async def ai_call(prompt):
    messages = []
    memory_msgs = saved_memory[-MAX_MEMORY:] if memory_enabled else []
    chat_msgs = saved_chats.get(current_chat, []) if current_chat else []
    seen_responses = set()
    for role, content in memory_msgs + chat_msgs:
        if (role, content) not in seen_responses:
            seen_responses.add((role, content))
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    date = datetime.now(TZ_UAE).strftime("%Y-%m-%d")
    mode_prompt = mode_prompts.get(current_mode, mode_prompts["chill"])
    system_msg = {
        "role": "system",
        "content": f"Today in UAE date: {date}. {mode_prompt}\n\n{pen_archive}"
    }
    current_key = api_keys[key_index]
    model_to_use = get_next_available_model()
    payload = {
        "model": model_to_use,
        "messages": [system_msg] + messages,
        "temperature": 0.7,
        "max_tokens": 1024
    }
    headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(api_url, json=payload, headers=headers)
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            elif resp.status == 429:
                error_data = await resp.json()
                print(f"Rate limit error: {error_data}")
                new_model = handle_rate_limit_error(model_to_use)
                global current_llm
                current_llm = new_model
                return await ai_call(prompt)
            else:
                error_text = await resp.text()
                return f"❌ Error {resp.status}: {error_text}"
    except Exception as e:
        return f"❌ Error: {e}"

def get_next_dec19(now: datetime) -> datetime:
    year = now.year
    target = datetime(year, 12, 19, 0, 0, 0, tzinfo=now.tzinfo)
    if target <= now:
        target = datetime(year + 1, 12, 19, 0, 0, 0, tzinfo=now.tzinfo)
    return target

def add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)

def format_countdown_to_dec19(now: datetime) -> str:
    target = get_next_dec19(now)
    months = 0
    while True:
        next_month_date = add_months(now, months + 1)
        if next_month_date <= target:
            months += 1
        else:
            break
    after_months = add_months(now, months)
    delta = target - after_months
    total_seconds = int(delta.total_seconds())
    days = delta.days
    weeks = days // 7
    days_remaining = days % 7
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if weeks:
        parts.append(f"{weeks} week{'s' if weeks != 1 else ''}")
    if days_remaining:
        parts.append(f"{days_remaining} day{'s' if days_remaining != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return ", ".join(parts)

async def annoying_loop():
    while True:
        await asyncio.sleep(3 * 60 * 60)
        for channel_id in list(annoying_channels):
            try:
                channel = bot.get_channel(channel_id)
                if channel:
                    msg = random.choice(RANDOM_ANNOYING_MESSAGES)
                    await channel.send(msg)
                else:
                    annoying_channels.discard(channel_id)
            except discord.errors.Forbidden:
                annoying_channels.discard(channel_id)
            except Exception as e:
                print(f"Error in annoying_loop: {e}")

@bot.event
async def on_ready():
    print(f"✅ MultiGPT ready as {bot.user.name}")
    print(f"🔑 Using {len(api_keys)} GROQ API keys")
    print(f"🎵 Pollinations Music endpoint: {POLLINATIONS_AUDIO_URL}")
    print(f"🎨 Image generation in {'SMART' if current_image_mode == 'smart' else 'FAST'} mode")
    print(f"🧠 Current mode: {current_mode.upper()}")
    print(f"🤖 HF Model: {current_hf_model}")
    print(f"🎬 Video generation using SiliconFlow Wan2.2-T2V-A14B (API key {'set' if siliconflow_api_key else 'NOT SET'})")
    asyncio.create_task(annoying_loop())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Ask me anything! | /help"))

@bot.event
async def on_message(message):
    global ping_only, current_chat, memory_enabled, current_llm, current_image_mode, current_mode
    global current_quality_mode, current_model_list, current_model_index
    global hf_key_index, current_hf_model, video_jobs, music_jobs
    if message.author == bot.user:
        return
    now = datetime.now().timestamp()
    if now - user_cooldowns.get(message.author.id, 0) < USER_COOLDOWN_SECONDS:
        return
    user_cooldowns[message.author.id] = now
    txt = message.content.strip()
    cleaned_txt = txt.replace(bot.user.mention, "").strip()

    if cleaned_txt == "/help":
        help_text = (
            "**🧠 MultiGPT Help Menu**\n\n"
            "**How to Talk to the Bot:**\n"
            "`@MultiGPT <your message>` → Ask the bot anything!\n\n"
            "**Modes:**\n"
            "`/chill` → Default casual mode\n"
            "`/unhinged` → Unfiltered mode (swears constantly)\n"
            "`/coder` → Programming expert mode\n"
            "`/childish` → Childish mode (meme slang)\n\n"
            "**Video Generation (SiliconFlow Wan2.2):**\n"
            "`/video <prompt>` → Generate a short video (5-6 seconds)\n"
            "   • Can take 3–15 minutes (queue + generation)\n"
            "`/vp` → Check live status of your video\n\n"
            "**Music Generation (Pollinations AI):**\n"
            "`/music <prompt>` → Generate music/audio from text\n"
            "`/mp` → Check music generation status\n\n"
            "**Features:**\n"
            "`/ra` → Toggle random annoying messages (every 3 hours)\n"
            "`/fast` → Fast mode (kimi-k2 + Pollinations images)\n"
            "`/smart` → Smart mode (gpt-oss + Hugging Face images)\n"
            "`/pa` → Ping-only mode ON\n"
            "`/pd` → Ping-only mode OFF\n"
            "`/ds` → Soft reset\n"
            "`/re` → Hard reset (clears everything)\n\n"
            "**General Commands:**\n"
            "`/help` → Show this menu\n"
            "`/cur-llm` → Show current LLM\n"
            "`/cha-llm <name>` → Change LLM (kimi-k2, gpt-oss, gemma2-9b)\n"
            "`/countdown` → Time until Dec 19\n\n"
            "**Saved Memory (SM):**\n"
            "`/sm` → Enable | `/smo` → Disable\n"
            "`/vsm` → View | `/csm` → Clear\n\n"
            "**Saved Chats (SC):**\n"
            "`/sc` → Start | `/sco` → Close\n"
            "`/vsc` → View | `/csc` → Clear\n"
            "`/sc1`-`/sc5` → Load slots\n\n"
            "**Image Generation:**\n"
            "`/image [prompt]` → Generate an image (5 sec wait)\n"
            "• Fast: Pollinations.ai + ImgBB\n"
            "• Smart: Hugging Face SDXL (safety checks)\n\n"
            "🔧 More features coming soon!"
        )
        await message.channel.send(help_text)
        return

    # Video progress check
    if cleaned_txt == "/vp":
        user_id = message.author.id
        job = video_jobs.get(user_id)
        if job:
            await message.channel.send(f"🎬 Video generation in progress for: **{job['prompt']}**... Please wait.")
        else:
            await message.channel.send("No active video generation. Use `/video` to start one.")
        return

    # Video generation command
    if cleaned_txt.lower().startswith("/video"):
        parts = cleaned_txt.split(maxsplit=1)
        if len(parts) < 2:
            await message.channel.send("❗ Usage: `/video <prompt>`\nExample: `/video a cat playing guitar`")
            return
        prompt = parts[1].strip()
        if not prompt:
            await message.channel.send("❌ Please provide a video prompt.")
            return
        if message.author.id in video_jobs:
            await message.channel.send("❌ You already have a video generating. Use `/vp` to check progress.")
            return
        status_msg = await message.channel.send(f"🎬 Generating video for: **{prompt}**... This may take up to 15 minutes.")
        video_jobs[message.author.id] = {
            "status": "generating",
            "message": status_msg,
            "prompt": prompt
        }
        asyncio.create_task(generate_video(prompt, message.author.id, status_msg))
        return

    # Music progress check
    if cleaned_txt == "/mp":
        user_id = message.author.id
        job = music_jobs.get(user_id)
        if job:
            await message.channel.send(f"🎵 Music generation in progress for: **{job['prompt']}**... Please wait.")
        else:
            await message.channel.send("No active music generation. Use `/music` to start one.")
        return

    # Music generation command
    if cleaned_txt.lower().startswith("/music"):
        parts = cleaned_txt.split(maxsplit=1)
        if len(parts) < 2:
            await message.channel.send("❗ Usage: `/music <prompt>`\nExample: `/music upbeat electronic dance track`")
            return
        prompt = parts[1].strip()
        if not prompt:
            await message.channel.send("❌ Please provide a music prompt.")
            return
        if message.author.id in music_jobs:
            await message.channel.send("❌ You already have music generating. Use `/mp` to check progress.")
            return
        status_msg = await message.channel.send(f"🎵 Generating music for: **{prompt}**... This may take up to 5 minutes.")
        music_jobs[message.author.id] = {
            "status": "generating",
            "message": status_msg,
            "prompt": prompt
        }
        asyncio.create_task(generate_music(prompt, message.author.id, status_msg))
        return

    # Mode commands
    if cleaned_txt == "/chill":
        current_mode = "chill"
        await message.channel.send("🧊 Mode set to **CHILL**")
        return
    elif cleaned_txt == "/unhinged":
        current_mode = "unhinged"
        await message.channel.send("🔥 Mode set to **UNHINGED**")
        return
    elif cleaned_txt == "/coder":
        current_mode = "coder"
        await message.channel.send("💻 Mode set to **CODER**")
        return
    elif cleaned_txt == "/childish":
        current_mode = "childish"
        await message.channel.send("🧸 Mode set to **CHILDISH**")
        return

    # Ping only toggle
    elif cleaned_txt == "/pa":
        ping_only = True
        await message.channel.send("🔔 Ping-only mode **ENABLED**")
        return
    elif cleaned_txt == "/pd":
        ping_only = False
        await message.channel.send("🔔 Ping-only mode **DISABLED**")
        return

    # Reset commands
    elif cleaned_txt == "/ds":
        reset_defaults()
        await message.channel.send("🔄 Soft reset completed.")
        return
    elif cleaned_txt == "/re":
        saved_chats.clear()
        saved_memory.clear()
        reset_defaults()
        await message.channel.send("💥 Hard reset completed. All chats and memory cleared.")
        return

    # LLM commands
    elif cleaned_txt == "/cur-llm":
        await message.channel.send(f"🤖 Current LLM: `{current_llm}`")
        return
    elif cleaned_txt.startswith("/cha-llm "):
        llm_name = cleaned_txt[9:].strip()
        if llm_name in allowed_llms:
            current_llm = allowed_llms[llm_name]
            await message.channel.send(f"🤖 LLM changed to: `{llm_name}` ({current_llm})")
        else:
            await message.channel.send(f"❌ Unknown LLM. Available: {', '.join(allowed_llms.keys())}")
        return

    # Quality mode commands
    elif cleaned_txt == "/fast":
        current_quality_mode = "fast"
        current_model_list = fast_models
        current_model_index = 0
        current_llm = fast_models[0]
        current_image_mode = "fast"
        await message.channel.send("⚡ **FAST MODE** enabled (kimi-k2 + Pollinations images)")
        return
    elif cleaned_txt == "/smart":
        current_quality_mode = "smart"
        current_model_list = smart_models
        current_model_index = 0
        current_llm = smart_models[0]
        current_image_mode = "smart"
        await message.channel.send("🧠 **SMART MODE** enabled (gpt-oss + Hugging Face images)")
        return

    # Annoying messages toggle
    elif cleaned_txt == "/ra":
        if message.channel.id in annoying_channels:
            annoying_channels.remove(message.channel.id)
            await message.channel.send("😇 Random annoying messages **DISABLED**")
        else:
            annoying_channels.add(message.channel.id)
            await message.channel.send("😈 Random annoying messages **ENABLED** (every 3 hours)")
        return

    # Countdown command
    elif cleaned_txt == "/countdown":
        now_dt = datetime.now(TZ_UAE)
        countdown = format_countdown_to_dec19(now_dt)
        await message.channel.send(f"⏰ **Time until December 19:**\n{countdown}")
        return

    # Saved Memory commands
    elif cleaned_txt == "/sm":
        memory_enabled = True
        await message.channel.send("🧠 Saved Memory **ENABLED**")
        return
    elif cleaned_txt == "/smo":
        memory_enabled = False
        await message.channel.send("🧠 Saved Memory **DISABLED**")
        return
    elif cleaned_txt == "/vsm":
        if saved_memory:
            memory_text = "\n".join([f"**{role}:** {content[:100]}..." if len(content) > 100 else f"**{role}:** {content}" for role, content in saved_memory[-10:]])
            await message.channel.send(f"🧠 **Saved Memory (last 10):**\n{memory_text}")
        else:
            await message.channel.send("🧠 No saved memory.")
        return
    elif cleaned_txt == "/csm":
        saved_memory.clear()
        await message.channel.send("🧠 Saved Memory **CLEARED**")
        return

    # Saved Chats commands
    elif cleaned_txt == "/sc":
        current_chat = f"chat_{message.author.id}_{int(time.time())}"
        saved_chats[current_chat] = []
        await message.channel.send(f"💾 Saved Chat started. ID: `{current_chat}`")
        return
    elif cleaned_txt == "/sco":
        if current_chat:
            await message.channel.send(f"💾 Saved Chat closed. ID: `{current_chat}`")
            current_chat = None
        else:
            await message.channel.send("❌ No active saved chat.")
        return
    elif cleaned_txt == "/vsc":
        if current_chat and current_chat in saved_chats:
            chat_text = "\n".join([f"**{role}:** {content[:100]}..." if len(content) > 100 else f"**{role}:** {content}" for role, content in saved_chats[current_chat][-10:]])
            await message.channel.send(f"💾 **Current Chat (last 10):**\n{chat_text}")
        else:
            await message.channel.send("❌ No active saved chat.")
        return
    elif cleaned_txt == "/csc":
        if current_chat:
            saved_chats[current_chat] = []
            await message.channel.send("💾 Current Chat **CLEARED**")
        else:
            await message.channel.send("❌ No active saved chat.")
        return
    elif re.match(r"^/sc[1-5]$", cleaned_txt):
        slot = cleaned_txt[3]
        chat_id = f"slot_{message.author.id}_{slot}"
        if chat_id in saved_chats:
            current_chat = chat_id
            await message.channel.send(f"💾 Loaded chat slot **{slot}**")
        else:
            saved_chats[chat_id] = []
            current_chat = chat_id
            await message.channel.send(f"💾 Created new chat slot **{slot}**")
        return

    # Image generation command
    elif cleaned_txt.startswith("/image"):
        prompt = cleaned_txt[6:].strip()
        if not prompt:
            await message.channel.send("❌ Please provide an image prompt.\nUsage: `/image a cat wearing sunglasses`")
            return
        if current_image_mode == "smart":
            safety_result = await check_image_safety(prompt)
            if safety_result == "AI:STOPIMAGE":
                await message.channel.send("🚫 **Image generation blocked:** This prompt contains inappropriate content.")
                return
        status_msg = await message.channel.send(f"🎨 Generating image: **{prompt}**...")
        try:
            if current_image_mode == "fast":
                image_data = await generate_pollinations_image(prompt)
                image_url = await upload_image_to_hosting(image_data)
                await status_msg.edit(content=f"🎨 **Fast Image:** {image_url}")
            else:
                image_data = await generate_hf_image(prompt)
                image_url = await upload_image_to_hosting(image_data)
                await status_msg.edit(content=f"🧠 **Smart Image:** {image_url}")
        except Exception as e:
            await status_msg.edit(content=f"❌ **Image generation failed:** {str(e)}")
        return

    # Check ping-only mode
    if ping_only and bot.user.mention not in txt:
        return

    # Process AI chat
    prompt = txt.replace(bot.user.mention, "").strip()
    if not prompt:
        return
    if current_chat:
        if current_chat not in saved_chats:
            saved_chats[current_chat] = []
        saved_chats[current_chat].append(("user", prompt))
        if len(saved_chats[current_chat]) > MAX_SAVED * 10:
            saved_chats[current_chat] = saved_chats[current_chat][-MAX_SAVED * 10:]
    if memory_enabled:
        saved_memory.append(("user", prompt))
        if len(saved_memory) > MAX_MEMORY:
            saved_memory.pop(0)
    thinking = await message.channel.send("🤔 MultiGPT is thinking...")
    response = await ai_call(prompt)
    response = re.sub(r'<think>.*?<think>', '', response, flags=re.DOTALL).strip()
    await thinking.edit(content=response[:2000] if len(response) <= 2000 else response[:1997] + "...")
    if current_chat:
        saved_chats[current_chat].append(("assistant", response))
    if memory_enabled:
        saved_memory.append(("assistant", response))
        if len(saved_memory) > MAX_MEMORY:
            saved_memory.pop(0)

# ------------------------------
# Web server for health checks
# ------------------------------
async def handle_root(request):
    return web.Response(text="✅ Bot running!")

async def handle_health(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/healthz", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 10000)))
    await site.start()
    print(f"🌐 Web server started on port {os.getenv('PORT', 10000)}")
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
