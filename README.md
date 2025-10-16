🤖 How to Add This AI Bot to Your Guilded Server
✅ Option 1: Use the Ready-Made Bot (Easy)

Just want the bot without doing any coding?
Use the official version here:
🔗 https://www.guilded.gg/b/79e91509-8031-4053-9d78-177c3246c786
(Perfect if you don’t want to mess with setup stuff)
🛠️ Option 2: Customize the Bot (Advanced Setup)

This is for people who want full control.
💻 You’ll need a PC or laptop (this won’t work on mobile).
🧩 Step-by-Step Setup Guide
1. Fork this Repo

Click the "Fork" button on the top right of this GitHub page. This creates your own copy of the bot’s code.
2. Create a Render Account

Go to https://render.com and sign up.
3. Deploy the Bot to Render

    On Render, click “New Web Service”.

    Choose “Deploy from GitHub”.

    Use the link to your forked repo.

4. Create a Guilded Bot + Get Your API Key

    Go to https://www.guilded.gg/developers

    Create a bot → Go to the API tab

    Scroll down and make an API key

    Copy the key (it starts with gapi_...) and save it in Notepad or somewhere safe.

5. Get a Groq API Key

    Go to https://groq.com and make an account.

    Create an API key and save it too.

6. Add Your Keys to Render

On your Render web service page:

    Find the “Environment” section

    Click “Add Environment Variable”

You’ll need to add two:
Name	Value (Paste Your Key Here)
GUILDED_TOKEN	Your Guilded key (starts with gapi_...)
GROQ_API_KEY	Your Groq API key

(These keys let your bot talk to Guilded and generate AI responses.)
7. Edit the Bot's Instructions (Optional)

    On GitHub, open the file main.py

    Scroll until you see system_prompt

    You can change how the bot talks here!

    Just don’t delete the quotation marks or break the code.

8. Deploy the Bot

    On Render, click “Deploy latest commit”

    Wait a minute for it to boot up

9. (Optional) Keep Your Bot Awake

    Go to https://betterstack.com

    Sign up → Create a “monitor”

    Use this as the website URL:
    your-bot-name.onrender.com
    (Replace "your-bot-name" with the actual Render name)
    This keeps your bot fast and online more often.

✅ Finished!

If you followed everything correctly:

    Invite your bot to your Guilded server

    Type /help to see if it's alive and working
