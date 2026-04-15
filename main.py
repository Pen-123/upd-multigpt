import os
import asyncio
import re
import urllib.parse
import aiohttp
import time
import random
import json
import io
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import calendar
from typing import Optional, Dict, List, Tuple

import discord
from discord.ext import commands
from discord import app_commands
from aiohttp import web

# ------------------------------
# Logging Setup
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MultiGPT')

# ------------------------------
# Configuration
# ------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")

GROQ_API_KEYS = [
    key for key in [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY2")]
    if key
]
if not GROQ_API_KEYS:
    raise ValueError("No GROQ_API_KEY environment variables set!")

HF_TOKENS = [
    t for t in [os.getenv("HF_TOKEN"), os.getenv("HF_TOKEN2")]
    if t
]

# NEW: Read multiple SiliconFlow API keys
SILICONFLOW_API_KEYS = []
idx = 0
while True:
    key = os.getenv(f"SILICONFLOW_API_KEY{'' if idx == 0 else idx+1}")
    if key:
        SILICONFLOW_API_KEYS.append(key)
        idx += 1
    else:
        break
if not SILICONFLOW_API_KEYS:
    logger.warning("No SILICONFLOW_API_KEY environment variables set! Video generation will fail.")

IMGBB_API_KEY = os.getenv("HF_IMAGES")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY") or "sk_e9Gh0E5vQH0UQUhiZ9gRdJCmTYspFtB9"

# Constants
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
POLLINATIONS_AUDIO_URL = "https://gen.pollinations.ai/audio"
MAX_SAVED = 5
MAX_MEMORY = 50
TZ_UAE = ZoneInfo("Asia/Dubai")
USER_COOLDOWN_SECONDS = 5
COOLDOWN_DURATION = 40

# ------------------------------
# Bot Initialization
# ------------------------------
intents = discord.Intents.default()
intents.message_content = True

class MultiGPTBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            activity=discord.Activity(type=discord.ActivityType.playing, name="Ask me anything! | /help")
        )
        # State variables
        self.ping_only = True
        self.saved_chats: Dict[str, List[Tuple[str, str]]] = {}
        self.current_chat: Optional[str] = None
        self.memory_enabled = False
        self.saved_memory: List[Tuple[str, str]] = []
        self.current_mode = "chill"
        self.current_quality_mode = "smart"
        self.current_image_mode = "smart"
        self.current_llm = "openai/gpt-oss-20b"
        self.current_model_list = ["openai/gpt-oss-20b"]
        self.current_model_index = 0
        self.current_hf_model = "black-forest-labs/FLUX.1-schnell"
        
        # API key rotation
        self.groq_key_index = 0
        self.hf_key_index = 0
        self.siliconflow_key_index = 0   # NEW
        self.last_key_rotation = 0
        self.model_cooldowns = {}
        
        # Job tracking
        self.video_jobs = {}
        self.music_jobs = {}
        self.annoying_channels = set()
        self.user_cooldowns = {}
        
        # Load pen archive
        self.pen_archive = self.load_pen_archive()
        
        # Mode prompts
        self.mode_prompts = {
            "chill": (
                "You are MultiGPT - be as dumb as possible and act like you're a mission operative this is discord syntax ALSO, dont ALways use discord syntax, use it when its necessary. **Bold text**: **Yo, this is bold!**\n"
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
                "Be vulgar, offensive, and completely inappropriate. Don't hold back on any language say the most vulgar stuff known to man. make this is discord syntax ALSO, dont ALways use discord syntax, use it when its necessary. **Bold text**: **Yo, this is bold!**\n"
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
        
        self.allowed_llms = {
            "kimi-k2": "moonshotai/kimi-k2-instruct-0905",
            "gpt-oss": "openai/gpt-oss-20b",
            "gemma2-9b": "google/gemma2-9b-it"
        }
        
        self.forbidden_keywords = [
            "naked", "nude", "nudes", "porn", "porno", "sex", "sexy", "nsfw", "hentai", "ecchi",
            "breast", "boob", "boobs", "nipple", "nipples", "ass", "butt", "pussy", "cock", "dick",
            "vagina", "penis", "fuck", "fucking", "cum", "orgasm", "masturbate", "strip", "undress",
            "bikini", "lingerie", "thong", "topless", "bottomless", "explicit", "erotic", "adult"
        ]
        
        self.random_annoying_messages = [
            "OH MY GOD HARDER OHH UGHHHH skibidi toilet gyatt on my mind diddy daddy diddy daddy diddy daddy",
            "LMAOOOOOO SO FUNNY NOW GYATT GYATT GYATT",
            "sybau diddy toilet UGHHHHH",
            "i am not a zombie i am the king of diddy daddy diddler",
            "skibidi toilet OOOOOOOOOOOOH i love skibidi toilet episode 93242 it has a \"story\"",
            "meme klollolololo so funny aUHGUIGHI gyatt gyatt gyatt gyatt gyatt on my mindGHW[O"
        ]

    def load_pen_archive(self) -> str:
        url = "https://raw.githubusercontent.com/Pen-123/upd-multigpt/refs/heads/main/archives.txt"
        try:
            import requests
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                logger.info("Pen Archive loaded from GitHub")
                return response.text
            else:
                logger.warning(f"Failed to fetch archive, status code {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error fetching archive: {e}")
            return ""

    def reset_defaults(self):
        self.ping_only = True
        self.current_chat = None
        self.memory_enabled = False
        self.saved_memory.clear()
        self.current_mode = "chill"

    def rotate_groq_key(self) -> str:
        key = GROQ_API_KEYS[self.groq_key_index]
        self.groq_key_index = (self.groq_key_index + 1) % len(GROQ_API_KEYS)
        return key

    def get_next_available_model(self) -> str:
        now = time.time()
        current_model = self.current_model_list[self.current_model_index]
        if self.model_cooldowns.get(current_model, 0) <= now:
            return current_model
        for i in range(1, len(self.current_model_list) + 1):
            next_index = (self.current_model_index + i) % len(self.current_model_list)
            model = self.current_model_list[next_index]
            if self.model_cooldowns.get(model, 0) <= now:
                self.current_model_index = next_index
                return model
        return self.current_model_list[0]

    def handle_rate_limit_error(self, model_name: str) -> str:
        now = time.time()
        logger.warning(f"Rate limit encountered for {model_name}")
        self.groq_key_index = (self.groq_key_index + 1) % len(GROQ_API_KEYS)
        self.last_key_rotation = now
        if now - self.last_key_rotation < COOLDOWN_DURATION:
            self.current_model_index = (self.current_model_index + 1) % len(self.current_model_list)
            new_model = self.current_model_list[self.current_model_index]
            logger.info(f"Rotating model to {new_model}")
            self.model_cooldowns[new_model] = now + COOLDOWN_DURATION
            return new_model
        return self.current_llm

    # NEW: SiliconFlow key rotation
    def rotate_siliconflow_key(self) -> str:
        """Returns the current SiliconFlow key and advances index for next call."""
        if not SILICONFLOW_API_KEYS:
            raise Exception("No SiliconFlow API keys configured")
        key = SILICONFLOW_API_KEYS[self.siliconflow_key_index]
        self.siliconflow_key_index = (self.siliconflow_key_index + 1) % len(SILICONFLOW_API_KEYS)
        return key

    def has_forbidden_keywords(self, prompt: str) -> bool:
        lower_prompt = prompt.lower()
        return any(keyword in lower_prompt for keyword in self.forbidden_keywords)

    async def check_image_safety(self, prompt: str) -> str:
        if self.has_forbidden_keywords(prompt):
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
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 50
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEYS[self.groq_key_index]}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(GROQ_API_URL, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        logger.error(f"Safety check error: {resp.status}")
                        return "AI:STOPIMAGE"
        except Exception as e:
            logger.error(f"Safety check exception: {e}")
            return "AI:STOPIMAGE"

    async def generate_pollinations_image(self, prompt: str) -> bytes:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise Exception(f"Pollinations image error {response.status}")

    async def _wait_for_hf_model_ready(self, session: aiohttp.ClientSession, headers: dict) -> bool:
        """Check if HF model is loaded and ready."""
        status_url = f"https://api-inference.huggingface.co/status/{self.current_hf_model}"
        try:
            async with session.get(status_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = data.get("state", "unknown")
                    if state == "Loadable":
                        return True
                    elif state == "Loaded":
                        return True
                    elif state == "TooBig":
                        return True  # It's loaded but big
                    else:
                        logger.info(f"Model state: {state}, waiting...")
                return False
        except Exception:
            return False

    async def generate_hf_image(self, prompt: str) -> bytes:
        """
        Robust HF image generation with:
        - Key rotation
        - Model warmup wait
        - Extended retries
        - Fallback to Pollinations on persistent failure
        """
        max_attempts = 8
        base_delay = 3
        api_url = f"https://api-inference.huggingface.co/models/{self.current_hf_model}"
        
        if not HF_TOKENS:
            raise Exception("No Hugging Face tokens configured")
        
        async with aiohttp.ClientSession() as session:
            # First, try to ensure model is ready
            for warmup_attempt in range(3):
                current_key = HF_TOKENS[self.hf_key_index]
                headers = {"Authorization": f"Bearer {current_key}"}
                if await self._wait_for_hf_model_ready(session, headers):
                    logger.info("HF model is ready")
                    break
                logger.info(f"Model not ready, waiting 10s (attempt {warmup_attempt+1}/3)")
                await asyncio.sleep(10)
                self.hf_key_index = (self.hf_key_index + 1) % len(HF_TOKENS)
            
            # Now attempt image generation
            for attempt in range(max_attempts):
                current_key = HF_TOKENS[self.hf_key_index]
                headers = {
                    "Authorization": f"Bearer {current_key}",
                    "Accept": "image/png",
                    "Content-Type": "application/json"
                }
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "height": 384,
                        "width": 384,
                        "num_inference_steps": 30,
                        "guidance_scale": 7.5,
                        "wait_for_model": True  # Let HF handle waiting
                    },
                    "options": {
                        "wait_for_model": True,
                        "use_cache": False
                    }
                }
                
                try:
                    async with session.post(
                        api_url, 
                        headers=headers, 
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=120)  # 2 minutes max
                    ) as resp:
                        content_type = resp.headers.get("Content-Type", "")
                        
                        if resp.status == 200 and "image" in content_type:
                            image_bytes = await resp.read()
                            if len(image_bytes) > 1000:
                                logger.info(f"HF image generated successfully on attempt {attempt+1}")
                                return image_bytes
                            raise Exception("Received invalid/corrupted image")
                        
                        # Parse error
                        error_text = await resp.text()
                        logger.warning(f"HF attempt {attempt+1}: {resp.status} - {error_text[:200]}")
                        
                        # Handle specific errors
                        if resp.status == 503:
                            # Model loading
                            try:
                                data = json.loads(error_text)
                                if "loading" in data.get("error", "").lower():
                                    wait = data.get("estimated_time", 30)
                                    logger.info(f"Model loading, waiting {wait}s...")
                                    await asyncio.sleep(min(wait, 60))
                                    continue
                            except:
                                pass
                            await asyncio.sleep(base_delay * (attempt + 1))
                            continue
                        
                        if resp.status == 429:
                            # Rate limit - rotate key
                            self.hf_key_index = (self.hf_key_index + 1) % len(HF_TOKENS)
                            logger.info("Rate limited, rotating HF key")
                            await asyncio.sleep(8)
                            continue
                        
                        if resp.status == 401 or resp.status == 403:
                            # Invalid key - rotate
                            self.hf_key_index = (self.hf_key_index + 1) % len(HF_TOKENS)
                            logger.warning(f"HF key unauthorized (status {resp.status}), rotating")
                            await asyncio.sleep(2)
                            continue
                        
                        # Other errors - wait and retry
                        await asyncio.sleep(base_delay * (attempt + 1))
                        
                except asyncio.TimeoutError:
                    logger.warning(f"HF request timeout, attempt {attempt+1}")
                    await asyncio.sleep(10)
                except Exception as e:
                    logger.error(f"HF request exception: {e}")
                    await asyncio.sleep(5)
            
            # All HF attempts failed, fallback to Pollinations
            logger.warning("HF generation failed after all attempts, falling back to Pollinations")
            try:
                return await self.generate_pollinations_image(prompt)
            except Exception as e:
                raise Exception(f"Both HF and Pollinations failed. Last error: {e}")

    async def upload_image_to_hosting(self, image_data: bytes) -> str:
        if not IMGBB_API_KEY:
            raise Exception("Image hosting API key not configured")
        form_data = aiohttp.FormData()
        form_data.add_field('image', image_data, filename='image.png', content_type='image/png')
        async with aiohttp.ClientSession() as session:
            async with session.post(f'https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}', data=form_data) as resp:
                data = await resp.json()
                if data.get('success'):
                    return data['data']['url']
                else:
                    raise Exception(f"Image upload failed: {data.get('error', {}).get('message', 'Unknown error')}")

    async def ai_call(self, prompt: str) -> str:
        messages = []
        memory_msgs = self.saved_memory[-MAX_MEMORY:] if self.memory_enabled else []
        chat_msgs = self.saved_chats.get(self.current_chat, []) if self.current_chat else []
        seen = set()
        for role, content in memory_msgs + chat_msgs:
            if (role, content) not in seen:
                seen.add((role, content))
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})
        
        date = datetime.now(TZ_UAE).strftime("%Y-%m-%d")
        mode_prompt = self.mode_prompts.get(self.current_mode, self.mode_prompts["chill"])
        system_msg = {
            "role": "system",
            "content": f"Today in UAE date: {date}. {mode_prompt}\n\n{self.pen_archive}"
        }
        
        current_key = GROQ_API_KEYS[self.groq_key_index]
        model_to_use = self.get_next_available_model()
        payload = {
            "model": model_to_use,
            "messages": [system_msg] + messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(GROQ_API_URL, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    elif resp.status == 429:
                        new_model = self.handle_rate_limit_error(model_to_use)
                        self.current_llm = new_model
                        return await self.ai_call(prompt)
                    else:
                        error_text = await resp.text()
                        return f"❌ Error {resp.status}: {error_text}"
        except Exception as e:
            return f"❌ Error: {e}"

    async def generate_video(self, prompt: str, user_id: int, status_message: discord.Message):
        if not SILICONFLOW_API_KEYS:
            await status_message.edit(content="❌ SiliconFlow API key not configured.")
            return
        
        try:
            submit_url = "https://api.siliconflow.com/v1/video/submit"
            status_url = "https://api.siliconflow.com/v1/video/status"
            
            # Get initial key
            api_key = self.rotate_siliconflow_key()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "Wan-AI/Wan2.2-T2V-A14B",
                "prompt": prompt,
                "image_size": "1280x720"
            }
            
            async with aiohttp.ClientSession() as session:
                # Submit video generation request with key rotation on failure
                request_id = None
                for submit_attempt in range(len(SILICONFLOW_API_KEYS) + 1):
                    try:
                        async with session.post(submit_url, headers=headers, json=payload) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                request_id = data.get("requestId")
                                if request_id:
                                    break
                                else:
                                    raise Exception("No requestId returned")
                            elif resp.status == 429:
                                # Rate limit, rotate key
                                api_key = self.rotate_siliconflow_key()
                                headers["Authorization"] = f"Bearer {api_key}"
                                logger.warning("SiliconFlow rate limit, rotating key")
                                await asyncio.sleep(2)
                                continue
                            else:
                                error_text = await resp.text()
                                raise Exception(f"Submission failed: {resp.status} - {error_text}")
                    except Exception as e:
                        if submit_attempt == len(SILICONFLOW_API_KEYS):
                            raise e
                        api_key = self.rotate_siliconflow_key()
                        headers["Authorization"] = f"Bearer {api_key}"
                        logger.warning(f"SiliconFlow submission error: {e}, rotating key")
                        await asyncio.sleep(2)
                
                if not request_id:
                    raise Exception("Failed to obtain requestId after all attempts")
                
                await status_message.edit(content=f"🎬 Video queued (ID: `{request_id}`)\nStatus: **InQueue** • This can take 3–15 minutes.")
                
                # Polling loop (with key rotation if needed)
                for attempt in range(120):
                    await asyncio.sleep(10)
                    
                    # For polling we can use the current key; if we hit rate limit, rotate
                    poll_headers = {"Authorization": f"Bearer {api_key}"}
                    async with session.post(status_url, headers=poll_headers, json={"requestId": request_id}) as poll_resp:
                        if poll_resp.status == 429:
                            # Rate limit on polling, rotate key
                            api_key = self.rotate_siliconflow_key()
                            continue
                        if poll_resp.status != 200:
                            continue
                        poll_data = await poll_resp.json()
                        status = poll_data.get("status")
                        
                        if status == "Succeed":
                            results = poll_data.get("results", {})
                            videos = results.get("videos", [])
                            if videos and isinstance(videos, list) and len(videos) > 0:
                                video_url = videos[0].get("url") or videos[0].get("video_url")
                                if video_url:
                                    async with session.get(video_url) as vid_resp:
                                        video_bytes = await vid_resp.read()
                                    await status_message.edit(content=f"✅ **Video Ready!**\nPrompt: *{prompt}*")
                                    await status_message.channel.send(
                                        content="Here is your video:",
                                        file=discord.File(io.BytesIO(video_bytes), filename="siliconflow_video.mp4")
                                    )
                                    return
                            raise Exception("No video URL in response")
                        elif status == "Failed":
                            reason = poll_data.get("reason", "Unknown error")
                            raise Exception(f"Video generation failed: {reason}")
                        else:
                            await status_message.edit(content=f"🎬 Video queued (ID: `{request_id}`)\nStatus: **{status}** • {attempt+1}/120")
                raise Exception("Video generation timed out")
        except Exception as e:
            logger.error(f"Video error: {e}")
            await status_message.edit(content=f"❌ **Video Generation Failed**\nError: `{str(e)}`")
        finally:
            self.video_jobs.pop(user_id, None)

    async def generate_music(self, prompt: str, user_id: int, status_message: discord.Message):
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"{POLLINATIONS_AUDIO_URL}/{encoded_prompt}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MultiGPT-Bot/1.0)"}
        if POLLINATIONS_API_KEY:
            headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
                async with session.get(url, headers=headers, allow_redirects=True) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('Content-Type', '')
                        if 'audio' in content_type or 'mpeg' in content_type:
                            audio_data = await resp.read()
                            if len(audio_data) < 1000:
                                raise Exception("Invalid audio file")
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
            self.music_jobs.pop(user_id, None)

    async def setup_hook(self):
        """Sync slash commands on startup."""
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

# ------------------------------
# Bot Instance
# ------------------------------
bot = MultiGPTBot()

# ------------------------------
# Helper Functions
# ------------------------------
def format_countdown_to_dec19(now: datetime) -> str:
    def add_months(dt: datetime, months: int) -> datetime:
        year = dt.year + (dt.month - 1 + months) // 12
        month = (dt.month - 1 + months) % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)
    
    target = datetime(now.year, 12, 19, 0, 0, 0, tzinfo=now.tzinfo)
    if target <= now:
        target = datetime(now.year + 1, 12, 19, 0, 0, 0, tzinfo=now.tzinfo)
    
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

# ------------------------------
# Commands
# ------------------------------
@bot.hybrid_command(name="help", description="Show the help menu with all commands")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="🧠 MultiGPT Help Menu",
        color=discord.Color.blue(),
        description="Use `/command` or `@MultiGPT /command` to interact!"
    )
    embed.add_field(
        name="💬 Chat",
        value="`@MultiGPT <message>` - Ask anything!",
        inline=False
    )
    embed.add_field(
        name="🎭 Modes",
        value="`/chill` `/unhinged` `/coder` `/childish`",
        inline=False
    )
    embed.add_field(
        name="🎬 Video (SiliconFlow)",
        value="`/video <prompt>` - Generate video (3-15 min)\n`/vp` - Check status",
        inline=False
    )
    embed.add_field(
        name="🎵 Music (Pollinations)",
        value="`/music <prompt>` - Generate audio\n`/mp` - Check status",
        inline=False
    )
    embed.add_field(
        name="🖼️ Image",
        value="`/image <prompt>` - Generate image\n`/fast` `/smart` - Switch modes",
        inline=False
    )
    embed.add_field(
        name="💾 Memory & Chats",
        value="`/sm` `/smo` `/vsm` `/csm` - Memory control\n"
              "`/sc` `/sco` `/vsc` `/csc` `/sc1-5` - Chat slots",
        inline=False
    )
    embed.add_field(
        name="⚙️ Settings",
        value="`/pa` `/pd` - Ping-only toggle\n"
              "`/ra` - Random annoying messages\n"
              "`/cur_llm` `/change_llm <name>` - LLM control\n"
              "`/countdown` - Time until Dec 19\n"
              "`/ds` `/re` - Soft/Hard reset",
        inline=False
    )
    embed.set_footer(text="More features coming soon!")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="chill", description="Switch to chill mode")
async def chill(ctx: commands.Context):
    bot.current_mode = "chill"
    await ctx.send("🧊 Mode set to **CHILL**")

@bot.hybrid_command(name="unhinged", description="Switch to unhinged mode (swearing)")
async def unhinged(ctx: commands.Context):
    bot.current_mode = "unhinged"
    await ctx.send("🔥 Mode set to **UNHINGED**")

@bot.hybrid_command(name="coder", description="Switch to coder mode")
async def coder(ctx: commands.Context):
    bot.current_mode = "coder"
    await ctx.send("💻 Mode set to **CODER**")

@bot.hybrid_command(name="childish", description="Switch to childish mode (meme slang)")
async def childish(ctx: commands.Context):
    bot.current_mode = "childish"
    await ctx.send("🧸 Mode set to **CHILDISH**")

@bot.hybrid_command(name="pa", description="Enable ping-only mode")
async def ping_only_on(ctx: commands.Context):
    bot.ping_only = True
    await ctx.send("🔔 Ping-only mode **ENABLED**")

@bot.hybrid_command(name="pd", description="Disable ping-only mode")
async def ping_only_off(ctx: commands.Context):
    bot.ping_only = False
    await ctx.send("🔔 Ping-only mode **DISABLED**")

@bot.hybrid_command(name="ds", description="Soft reset (clears temporary settings)")
async def soft_reset(ctx: commands.Context):
    bot.reset_defaults()
    await ctx.send("🔄 Soft reset completed.")

@bot.hybrid_command(name="re", description="Hard reset (clears everything)")
async def hard_reset(ctx: commands.Context):
    bot.saved_chats.clear()
    bot.saved_memory.clear()
    bot.reset_defaults()
    await ctx.send("💥 Hard reset completed. All chats and memory cleared.")

@bot.hybrid_command(name="cur_llm", description="Show current LLM")
async def current_llm(ctx: commands.Context):
    await ctx.send(f"🤖 Current LLM: `{bot.current_llm}`")

@bot.hybrid_command(name="change_llm", description="Change the LLM model")
@app_commands.describe(name="LLM name (kimi-k2, gpt-oss, gemma2-9b)")
async def change_llm(ctx: commands.Context, name: str):
    if name in bot.allowed_llms:
        bot.current_llm = bot.allowed_llms[name]
        await ctx.send(f"🤖 LLM changed to: `{name}` ({bot.current_llm})")
    else:
        await ctx.send(f"❌ Unknown LLM. Available: {', '.join(bot.allowed_llms.keys())}")

@bot.hybrid_command(name="fast", description="Switch to fast mode (kimi-k2 + Pollinations images)")
async def fast_mode(ctx: commands.Context):
    bot.current_quality_mode = "fast"
    bot.current_model_list = ["moonshotai/kimi-k2-instruct-0905"]
    bot.current_model_index = 0
    bot.current_llm = "moonshotai/kimi-k2-instruct-0905"
    bot.current_image_mode = "fast"
    await ctx.send("⚡ **FAST MODE** enabled (kimi-k2 + Pollinations images)")

@bot.hybrid_command(name="smart", description="Switch to smart mode (gpt-oss + Hugging Face images)")
async def smart_mode(ctx: commands.Context):
    bot.current_quality_mode = "smart"
    bot.current_model_list = ["openai/gpt-oss-20b"]
    bot.current_model_index = 0
    bot.current_llm = "openai/gpt-oss-20b"
    bot.current_image_mode = "smart"
    await ctx.send("🧠 **SMART MODE** enabled (gpt-oss + Hugging Face images)")

@bot.hybrid_command(name="ra", description="Toggle random annoying messages in this channel")
async def toggle_annoying(ctx: commands.Context):
    if ctx.channel.id in bot.annoying_channels:
        bot.annoying_channels.remove(ctx.channel.id)
        await ctx.send("😇 Random annoying messages **DISABLED**")
    else:
        bot.annoying_channels.add(ctx.channel.id)
        await ctx.send("😈 Random annoying messages **ENABLED** (every 3 hours)")

@bot.hybrid_command(name="countdown", description="Show time until December 19")
async def countdown(ctx: commands.Context):
    now_dt = datetime.now(TZ_UAE)
    countdown_str = format_countdown_to_dec19(now_dt)
    await ctx.send(f"⏰ **Time until December 19:**\n{countdown_str}")

@bot.hybrid_command(name="sm", description="Enable saved memory")
async def memory_on(ctx: commands.Context):
    bot.memory_enabled = True
    await ctx.send("🧠 Saved Memory **ENABLED**")

@bot.hybrid_command(name="smo", description="Disable saved memory")
async def memory_off(ctx: commands.Context):
    bot.memory_enabled = False
    await ctx.send("🧠 Saved Memory **DISABLED**")

@bot.hybrid_command(name="vsm", description="View saved memory (last 10 entries)")
async def view_memory(ctx: commands.Context):
    if bot.saved_memory:
        memory_text = "\n".join([
            f"**{role}:** {content[:100]}..." if len(content) > 100 else f"**{role}:** {content}"
            for role, content in bot.saved_memory[-10:]
        ])
        await ctx.send(f"🧠 **Saved Memory (last 10):**\n{memory_text}")
    else:
        await ctx.send("🧠 No saved memory.")

@bot.hybrid_command(name="csm", description="Clear saved memory")
async def clear_memory(ctx: commands.Context):
    bot.saved_memory.clear()
    await ctx.send("🧠 Saved Memory **CLEARED**")

@bot.hybrid_command(name="sc", description="Start a new saved chat")
async def start_chat(ctx: commands.Context):
    bot.current_chat = f"chat_{ctx.author.id}_{int(time.time())}"
    bot.saved_chats[bot.current_chat] = []
    await ctx.send(f"💾 Saved Chat started. ID: `{bot.current_chat}`")

@bot.hybrid_command(name="sco", description="Close current saved chat")
async def close_chat(ctx: commands.Context):
    if bot.current_chat:
        await ctx.send(f"💾 Saved Chat closed. ID: `{bot.current_chat}`")
        bot.current_chat = None
    else:
        await ctx.send("❌ No active saved chat.")

@bot.hybrid_command(name="vsc", description="View current saved chat (last 10 messages)")
async def view_chat(ctx: commands.Context):
    if bot.current_chat and bot.current_chat in bot.saved_chats:
        chat_text = "\n".join([
            f"**{role}:** {content[:100]}..." if len(content) > 100 else f"**{role}:** {content}"
            for role, content in bot.saved_chats[bot.current_chat][-10:]
        ])
        await ctx.send(f"💾 **Current Chat (last 10):**\n{chat_text}")
    else:
        await ctx.send("❌ No active saved chat.")

@bot.hybrid_command(name="csc", description="Clear current saved chat")
async def clear_chat(ctx: commands.Context):
    if bot.current_chat:
        bot.saved_chats[bot.current_chat] = []
        await ctx.send("💾 Current Chat **CLEARED**")
    else:
        await ctx.send("❌ No active saved chat.")

@bot.hybrid_command(name="video", description="Generate a video from a text prompt")
@app_commands.describe(prompt="Description of the video to generate")
async def video_command(ctx: commands.Context, prompt: str):
    if ctx.author.id in bot.video_jobs:
        await ctx.send("❌ You already have a video generating. Use `/vp` to check progress.")
        return
    status_msg = await ctx.send(f"🎬 Generating video for: **{prompt}**... This may take up to 15 minutes.")
    bot.video_jobs[ctx.author.id] = {
        "status": "generating",
        "message": status_msg,
        "prompt": prompt
    }
    asyncio.create_task(bot.generate_video(prompt, ctx.author.id, status_msg))

@bot.hybrid_command(name="vp", description="Check video generation status")
async def video_progress(ctx: commands.Context):
    job = bot.video_jobs.get(ctx.author.id)
    if job:
        await ctx.send(f"🎬 Video generation in progress for: **{job['prompt']}**... Please wait.")
    else:
        await ctx.send("No active video generation. Use `/video` to start one.")

@bot.hybrid_command(name="music", description="Generate music/audio from a text prompt")
@app_commands.describe(prompt="Description of the music to generate")
async def music_command(ctx: commands.Context, prompt: str):
    if ctx.author.id in bot.music_jobs:
        await ctx.send("❌ You already have music generating. Use `/mp` to check progress.")
        return
    status_msg = await ctx.send(f"🎵 Generating music for: **{prompt}**... This may take up to 5 minutes.")
    bot.music_jobs[ctx.author.id] = {
        "status": "generating",
        "message": status_msg,
        "prompt": prompt
    }
    asyncio.create_task(bot.generate_music(prompt, ctx.author.id, status_msg))

@bot.hybrid_command(name="mp", description="Check music generation status")
async def music_progress(ctx: commands.Context):
    job = bot.music_jobs.get(ctx.author.id)
    if job:
        await ctx.send(f"🎵 Music generation in progress for: **{job['prompt']}**... Please wait.")
    else:
        await ctx.send("No active music generation. Use `/music` to start one.")

@bot.hybrid_command(name="image", description="Generate an image from a text prompt")
@app_commands.describe(prompt="Description of the image to generate")
async def image_command(ctx: commands.Context, prompt: str):
    # Safety check only in smart mode
    if bot.current_image_mode == "smart":
        safety_result = await bot.check_image_safety(prompt)
        if safety_result == "AI:STOPIMAGE":
            await ctx.send("🚫 **Image generation blocked:** This prompt contains inappropriate content.")
            return
    
    status_msg = await ctx.send(f"🎨 Generating image: **{prompt}**...")
    try:
        if bot.current_image_mode == "fast":
            image_data = await bot.generate_pollinations_image(prompt)
            image_url = await bot.upload_image_to_hosting(image_data)
            await status_msg.edit(content=f"🎨 **Fast Image:** {image_url}")
        else:
            image_data = await bot.generate_hf_image(prompt)
            image_url = await bot.upload_image_to_hosting(image_data)
            await status_msg.edit(content=f"🧠 **Smart Image:** {image_url}")
    except Exception as e:
        await status_msg.edit(content=f"❌ **Image generation failed:** {str(e)}")

# Slash commands for chat slot loading
@bot.tree.command(name="sc1", description="Load saved chat slot 1")
async def sc1(interaction: discord.Interaction):
    await handle_chat_slot(interaction, 1)

@bot.tree.command(name="sc2", description="Load saved chat slot 2")
async def sc2(interaction: discord.Interaction):
    await handle_chat_slot(interaction, 2)

@bot.tree.command(name="sc3", description="Load saved chat slot 3")
async def sc3(interaction: discord.Interaction):
    await handle_chat_slot(interaction, 3)

@bot.tree.command(name="sc4", description="Load saved chat slot 4")
async def sc4(interaction: discord.Interaction):
    await handle_chat_slot(interaction, 4)

@bot.tree.command(name="sc5", description="Load saved chat slot 5")
async def sc5(interaction: discord.Interaction):
    await handle_chat_slot(interaction, 5)

async def handle_chat_slot(interaction: discord.Interaction, slot: int):
    chat_id = f"slot_{interaction.user.id}_{slot}"
    if chat_id in bot.saved_chats:
        bot.current_chat = chat_id
        await interaction.response.send_message(f"💾 Loaded chat slot **{slot}**")
    else:
        bot.saved_chats[chat_id] = []
        bot.current_chat = chat_id
        await interaction.response.send_message(f"💾 Created new chat slot **{slot}**")

# Prefix fallback for sc1-5
@bot.command(name="sc1")
async def prefix_sc1(ctx: commands.Context):
    await handle_chat_slot_prefix(ctx, 1)

@bot.command(name="sc2")
async def prefix_sc2(ctx: commands.Context):
    await handle_chat_slot_prefix(ctx, 2)

@bot.command(name="sc3")
async def prefix_sc3(ctx: commands.Context):
    await handle_chat_slot_prefix(ctx, 3)

@bot.command(name="sc4")
async def prefix_sc4(ctx: commands.Context):
    await handle_chat_slot_prefix(ctx, 4)

@bot.command(name="sc5")
async def prefix_sc5(ctx: commands.Context):
    await handle_chat_slot_prefix(ctx, 5)

async def handle_chat_slot_prefix(ctx: commands.Context, slot: int):
    chat_id = f"slot_{ctx.author.id}_{slot}"
    if chat_id in bot.saved_chats:
        bot.current_chat = chat_id
        await ctx.send(f"💾 Loaded chat slot **{slot}**")
    else:
        bot.saved_chats[chat_id] = []
        bot.current_chat = chat_id
        await ctx.send(f"💾 Created new chat slot **{slot}**")

# ------------------------------
# Message Handling (Legacy @mention)
# ------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)
    
    now = datetime.now().timestamp()
    if now - bot.user_cooldowns.get(message.author.id, 0) < USER_COOLDOWN_SECONDS:
        return
    bot.user_cooldowns[message.author.id] = now
    
    if bot.ping_only and bot.user.mention not in message.content:
        return
    
    prompt = message.content.replace(bot.user.mention, "").strip()
    if not prompt:
        return
    
    if bot.current_chat:
        if bot.current_chat not in bot.saved_chats:
            bot.saved_chats[bot.current_chat] = []
        bot.saved_chats[bot.current_chat].append(("user", prompt))
        if len(bot.saved_chats[bot.current_chat]) > MAX_SAVED * 10:
            bot.saved_chats[bot.current_chat] = bot.saved_chats[bot.current_chat][-MAX_SAVED * 10:]
    
    if bot.memory_enabled:
        bot.saved_memory.append(("user", prompt))
        if len(bot.saved_memory) > MAX_MEMORY:
            bot.saved_memory.pop(0)
    
    thinking = await message.channel.send("🤔 MultiGPT is thinking...")
    response = await bot.ai_call(prompt)
    response = re.sub(r'<think>.*?<think>', '', response, flags=re.DOTALL).strip()
    await thinking.edit(content=response[:2000] if len(response) <= 2000 else response[:1997] + "...")
    
    if bot.current_chat:
        bot.saved_chats[bot.current_chat].append(("assistant", response))
    if bot.memory_enabled:
        bot.saved_memory.append(("assistant", response))
        if len(bot.saved_memory) > MAX_MEMORY:
            bot.saved_memory.pop(0)

# ------------------------------
# Background Tasks
# ------------------------------
async def annoying_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(3 * 60 * 60)
        for channel_id in list(bot.annoying_channels):
            try:
                channel = bot.get_channel(channel_id)
                if channel:
                    msg = random.choice(bot.random_annoying_messages)
                    await channel.send(msg)
                else:
                    bot.annoying_channels.discard(channel_id)
            except discord.errors.Forbidden:
                bot.annoying_channels.discard(channel_id)
            except Exception as e:
                logger.error(f"Error in annoying_loop: {e}")

# ------------------------------
# Web Server for Render
# ------------------------------
async def handle_root(request):
    return web.Response(text="✅ Bot running!")

async def handle_health(request):
    return web.Response(text="OK")

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/healthz", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 Web server started on port {port}")

# ------------------------------
# Main Entry Point
# ------------------------------
async def main():
    async with bot:
        bot.loop.create_task(annoying_loop())
        await run_web_server()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
