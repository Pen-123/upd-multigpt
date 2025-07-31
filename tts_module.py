import os
from groq import Groq
from discord.ext import commands
import discord

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client_groq = Groq(api_key=GROQ_API_KEY)

# Set up your bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.command()
async def say(ctx, *, message):
    await ctx.trigger_typing()

    speech_file_path = "speech.wav"
    model = "playai-tts"
    voice = "Fritz-PlayAI"
    text = message
    response_format = "wav"

    try:
        response = client_groq.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format=response_format
        )
        
        response.write_to_file(speech_file_path)

        await ctx.send(file=discord.File(speech_file_path))

    except Exception as e:
        await ctx.send(f"Error generating speech: {e}")

# To use: import this file and run bot.run in your main launcher file.
