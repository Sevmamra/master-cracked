import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import urllib.parse
import yt_dlp
import cloudscraper
from datetime import datetime, timedelta
from logs import logging
from bs4 import BeautifulSoup
import core as helper
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, MONGO_URL, OWNER_ID
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pytube import YouTube
from pymongo import MongoClient
from aiohttp import web
import random
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

#========================================================================================================================================================================
cookies_file_path= "youtube_cookies.txt"
#====================================================================================================

photologo = 'https://tinypic.host/images/2025/02/07/DeWatermark.ai_1738952933236-1.png'
photoyt = 'https://tinypic.host/images/2025/03/18/YouTube-Logo.wine.png'
photocp = 'https://tinypic.host/images/2025/03/28/IMG_20250328_133126.jpg'

#================================================================================================================================
# Initialize the bot
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)
#================================================================================================================================
mongo = MongoClient(MONGO_URL)
db = mongo["mini_auth_bot"]
auth_col = db["auth_users"]

# ==== HELPERS ====
def parse_duration(duration_str):
    pattern = r"(\d+)([smhdwMy])"
    match = re.match(pattern, duration_str)
    if not match:
        return None
    num, unit = match.groups()
    num = int(num)
    if unit == "s":
        return timedelta(seconds=num)
    if unit == "m":
        return timedelta(minutes=num)
    if unit == "h":
        return timedelta(hours=num)
    if unit == "d":
        return timedelta(days=num)
    if unit == "w":
        return timedelta(weeks=num)
    if unit == "M":
        return timedelta(days=30 * num)
    if unit == "y":
        return timedelta(days=365 * num)
    return None

def is_authorized(user_id):
    user = auth_col.find_one({"_id": user_id})
    if user:
        if "expires_at" in user:
            if user["expires_at"] < datetime.utcnow():
                auth_col.delete_one({"_id": user_id})  # Auto-remove if expired
                return False
        return True
    return user_id == OWNER_ID

# ==== BACKGROUND TASK ====
async def auto_remove_expired_users():
    while True:
        now = datetime.utcnow()
        result = auth_col.delete_many({"expires_at": {"$lt": now}})
        if result.deleted_count:
            print(f"Auto-removed {result.deleted_count} expired users.")
        await asyncio.sleep(60)

# ==== COMMANDS ====

@bot.on_message(filters.command("add") & filters.user(OWNER_ID))
async def add_user(_, m):
    if len(m.command) < 3:
        return await m.reply_text("⚠️ Usage: /add <user_id> <duration> (e.g. 1m, 2h, 7d)")
    try:
        user_id = int(m.command[1])
        duration = parse_duration(m.command[2])
        if not duration:
            return await m.reply_text("❌ Invalid duration format.")

        expires_at = datetime.utcnow() + duration
        if not auth_col.find_one({"_id": user_id}):
            auth_col.insert_one({"_id": user_id, "expires_at": expires_at})
            await m.reply_text(f"✅ User added till {expires_at} UTC.")
            try:
                await client.send_message(user_id, f"✅ You have been authorized until {expires_at} UTC!")
            except Exception as e:
                print(f"Failed to notify user: {e}")
        else:
            await m.reply_text("ℹ️ User already exists.")
    except:
        await m.reply_text("❌ Invalid ID format.")

@bot.on_message(filters.command("rem") & filters.user(OWNER_ID))
async def remove_user(_, m):
    if len(m.command) < 2:
        return await m.reply_text("⚠️ Usage: /rem <user_id>")
    try:
        user_id = int(m.command[1])
        result = auth_col.delete_one({"_id": user_id})
        await m.reply_text("✅ User removed." if result.deleted_count else "❌ User not found.")
        try:
            await client.send_message(user_id, "❌ You have been removed from authorized!")
        except Exception as e:
            print(f"Failed to notify user: {e}")
    except:
        await m.reply_text("❌ Invalid ID format.")

@bot.on_message(filters.command("clear") & filters.user(OWNER_ID))
async def clear_all_users(_, m):
    result = auth_col.delete_many({})
    await m.reply_text(f"✅ All users deleted.\nTotal removed: {result.deleted_count}")

@bot.on_message(filters.command("users") & filters.user(OWNER_ID))
async def show_users(_, m):
    users = list(auth_col.find())
    if not users:
        return await m.reply_text("🚫 No authorized users.")
    user_list = "\n".join(f"{u['_id']} - Exp: {u.get('expires_at', 'N/A')}" for u in users)
    await m.reply_text(f"👥 Authorized Users:\n\n{user_list}")

@bot.on_message(filters.command("myplan"))
async def my_plan(_, m):
    user = auth_col.find_one({"_id": m.from_user.id})
    if user:
        exp = user.get("expires_at")
        await m.reply_text(f"✅ You are authorized.\nExpires at: {exp} UTC")
    else:
        await m.reply_text("❌ You are not authorized.")
#================================================================================================================================
@bot.on_message(filters.command("cookies") & filters.private)
async def cookies_handler(client: Client, m: Message):
    await m.reply_text(
        "Please upload the cookies file (.txt format).",
        quote=True
    )

    try:
        # Wait for the user to send the cookies file
        input_message: Message = await client.listen(m.chat.id)

        # Validate the uploaded file
        if not input_message.document or not input_message.document.file_name.endswith(".txt"):
            await m.reply_text("Invalid file type. Please upload a .txt file.")
            return

        # Download the cookies file
        downloaded_path = await input_message.download()

        # Read the content of the uploaded file
        with open(downloaded_path, "r") as uploaded_file:
            cookies_content = uploaded_file.read()

        # Replace the content of the target cookies file
        with open(cookies_file_path, "w") as target_file:
            target_file.write(cookies_content)

        await input_message.reply_text(
            "✅ Cookies updated successfully.\n📂 Saved in `youtube_cookies.txt`."
        )

    except Exception as e:
        await m.reply_text(f"⚠️ An error occurred: {str(e)}")

#================================================================================================================================
BUTTONSUSCRIBE = InlineKeyboardMarkup([[InlineKeyboardButton(text="🚨Buy Membership🚨", url="https://t.me/saini_contact_bot")]])

@bot.on_message(filters.command("start"))
async def start(bot, m: Message):
    user = await bot.get_me()
    mention = user.mention
    start_message = await bot.send_message(
        m.chat.id,
        "🌟 Welcome Boss☠️! 🌟\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        "🌟 Welcome Boss☠️! 🌟\n\n" +
        "Initializing Uploader bot... 🤖\n\n"
        "Progress: [⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️] 0%\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        "🌟 Welcome Boss☠️! 🌟\n\n" +
        "Loading features... ⏳\n\n"
        "Progress: [🟥🟥🟥⬜️⬜️⬜️⬜️⬜️⬜️⬜️] 25%\n\n"
    )
    
    await asyncio.sleep(1)
    await start_message.edit_text(
        "🌟 Welcome Boss☠️! 🌟\n\n" +
        "This may take a moment, sit back and relax! 😊\n\n"
        "Progress: [🟧🟧🟧🟧🟧⬜️⬜️⬜️⬜️⬜️] 50%\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        "🌟 Welcome Boss☠️! 🌟\n\n" +
        "Checking subscription status... 🔍\n\n"
        "Progress: [🟨🟨🟨🟨🟨🟨🟨🟨⬜️⬜️] 75%\n\n"
    )

    await asyncio.sleep(1)
    user_id = m.from_user.id
    if is_authorized(user_id):
        await start_message.edit_text(
            "🌟 Welcome Boss☠️! 🌟\n\n" +
            "Great! You are a premium member!\n"
            "Use Command : /drm to get started 🌟\n\n"
            f"<blockquote>If you face any problem contact - [𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎](https://t.me/saini_contact_bot)</blockquote>"
        )
    else:
        await asyncio.sleep(2)
        await start_message.edit_text(
           f" 🎉 Welcome to Non-DRM Bot! 🎉\n\n"
           f"You can have access to download all Non-DRM+AES Encrypted URLs 🔐 including\n\n"
           f"<blockquote>• 📚 Appx Zip+Encrypted Url\n"
           f"• 🎓 Classplus DRM+ NDRM\n"
           f"• 🧑‍🏫 PhysicsWallah DRM\n"
           f"• 📚 CareerWill + PDF\n"
           f"• 🎓 Khan GS\n"
           f"• 🎓 Study Iq DRM\n"
           f"• 🚀 APPX + APPX Enc PDF\n"
           f"• 🎓 Vimeo Protection\n"
           f"• 🎓 Brightcove Protection\n"
           f"• 🎓 Visionias Protection\n"
           f"• 🎓 Zoom Video\n"
           f"• 🎓 Utkarsh Protection(Video + PDF)\n"
           f"• 🎓 All Non DRM+AES Encrypted URLs\n"
           f"• 🎓 MPD URLs if the key is known (e.g., Mpd_url?key=key XX:XX)</blockquote>\n\n"
           f"🚀 You are not subscribed to any plan yet!\n\n"
           f"<blockquote>💵 Monthly Plan: free</blockquote>\n\n"
           f"If you want to buy membership of the bot, feel free to contact the Bot Admin.\n", disable_web_page_preview=True, reply_markup=BUTTONSUSCRIBE
        )

#================================================================================================================================
@bot.on_message(filters.command(["id"]))
async def id_command(client, message: Message):
    chat_id = message.chat.id
    await message.reply_text(f"<blockquote>The ID of this chat id is:</blockquote>\n`{chat_id}`")

#================================================================================================================================
@bot.on_message(filters.command(["logs"]) )
async def send_logs(bot: Client, m: Message):
    try:
        with open("logs.txt", "rb") as file:
            sent= await m.reply_text("**📤 Sending you ....**")
            await m.reply_document(document=file)
            await sent.delete(True)
    except Exception as e:
        await m.reply_text(f"Error sending logs: {e}")

#================================================================================================================================
@bot.on_message(filters.command(["stop"]) )
async def restart_handler(_, m):
    
    user_id = m.from_user.id
    if not is_authorized(user_id):
        await m.message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎](https://t.me/saini_contact_bot) !")
        return
    
    await m.reply_text("🚦**STOPPED**🚦", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

#================================================================================================================================
@bot.on_message(filters.command(["drm"]) )
async def txt_handler(bot: Client, m: Message):
    
    user_id = m.from_user.id
    if not is_authorized(user_id):
        await m.message.reply("❌ 𝚈𝚘𝚞 𝚊𝚛𝚎 𝚗𝚘𝚝 𝚊𝚞𝚝𝚑𝚘𝚛𝚒𝚣𝚎𝚍.\n💎 𝙱𝚞𝚢 𝙿𝚛𝚎𝚖𝚒𝚞𝚖  [𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎](https://t.me/saini_contact_bot) !")
        return
    
    editable = await m.reply_text(f"__Hii, I am non-drm Downloader Bot__\n<blockquote><i>Send Me Your text file which enclude Name with url...\nE.g: Name: Link</i></blockquote>")
    input: Message = await bot.listen(editable.chat.id)
    x = await input.download()
    await input.delete(True)
    file_name, ext = os.path.splitext(os.path.basename(x))
    credit = f"𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎"
    pdf_count = 0
    img_count = 0
    zip_count = 0
    other_count = 0
    
    try:    
        with open(x, "r") as f:
            content = f.read()
        content = content.split("\n")
        
        links = []
        for i in content:
            if "://" in i:
                url = i.split("://", 1)[1]
                links.append(i.split("://", 1))
                if ".pdf" in url:
                    pdf_count += 1
                elif url.endswith((".png", ".jpeg", ".jpg")):
                    img_count += 1
                else:
                    other_count += 1
        os.remove(x)
    except:
        await m.reply_text("<pre><code>🔹Invalid file input.</code></pre>")
        os.remove(x)
        return
   
    await editable.edit(f"Total 🔗 links found are {len(links)}\n\nSend starting download number")
    input0: Message = await bot.listen(editable.chat.id)
    raw_text = input0.text
    await input0.delete(True)
           
    await editable.edit("__Enter Batch Name or send /d for filename.__")
    input1: Message = await bot.listen(editable.chat.id)
    raw_text0 = input1.text
    await input1.delete(True)
    if raw_text0 == '/d':
        b_name = file_name
    else:
        b_name = raw_text0

    await editable.edit("__Enter resolution or Video Quality (`144`, `240`, `360`, `480`, `720`, `1080`)__")
    input2: Message = await bot.listen(editable.chat.id)
    raw_text2 = input2.text
    quality = f"{raw_text2}p"
    await input2.delete(True)
    try:
        if raw_text2 == "144":
            res = "256x144"
        elif raw_text2 == "240":
            res = "426x240"
        elif raw_text2 == "360":
            res = "640x360"
        elif raw_text2 == "480":
            res = "854x480"
        elif raw_text2 == "720":
            res = "1280x720"
        elif raw_text2 == "1080":
            res = "1920x1080" 
        else: 
            res = "UN"
    except Exception:
            res = "UN"

    await editable.edit("__Enter the credit name for the caption or you want default then send /d__\n\n")
    input3: Message = await bot.listen(editable.chat.id)
    raw_text3 = input3.text
    await input3.delete(True)
    if raw_text3 == '/d':
        CR = '𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎 🕊️'
    else:
        CR = raw_text3

    await editable.edit("__**Enter Your PW Token For 𝐌𝐏𝐃 𝐔𝐑𝐋**__")
    input4: Message = await bot.listen(editable.chat.id)
    raw_text4 = input4.text
    await input4.delete(True)

    await editable.edit(f"__If you want to add topic feature : Send `yes`__\n__**Otherwise send `no`**__\n\n<blockquote><i>Title fetched from (title) this bracket</i></blockquote>")
    input5: Message = await bot.listen(editable.chat.id)
    raw_text5 = input5.text
    await input5.delete(True)

    await editable.edit(f"Send the Thumb URL or Send `no` \n\n<blockquote><i>You can direct upload thumb\nFor document format send : No</i></blockquote>")
    input6 = message = await bot.listen(editable.chat.id)
    raw_text6 = input6.text
    await input6.delete(True)

    if input6.photo:
        thumb = await input6.download()  # Use the photo sent by the user
    elif raw_text6.startswith("http://") or raw_text6.startswith("https://"):
        # If a URL is provided, download thumbnail from the URL
        getstatusoutput(f"wget '{raw_text6}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = raw_text6
        
    await editable.edit("__⚠️Provide the Channel ID or send /d__\n\n<blockquote><i>🔹 Make me an admin to upload.\n🔸Send /id in your channel to get the Channel ID.\n\nExample: Channel ID = -100XXXXXXXXXXX or /d for Personally</i></blockquote>")
    input7: Message = await bot.listen(editable.chat.id)
    raw_text7 = input7.text
    if "/d" in input7.text:
        channel_id = m.chat.id
    else:
        channel_id = input7.text
    await input7.delete()     
    await editable.delete()
    try:
        batch_message = await bot.send_message(chat_id=channel_id, text=f"<blockquote><b>🎯Target Batch : {b_name}</b></blockquote>")
    except Exception as e:
        await m.reply_text(f"**Fail Reason »**\n<blockquote><i>{e}</i></blockquote>\n\n✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ `🌟『𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎』🌟`")
        return   
            
    failed_count = 0
    arg = int(raw_text)   
    count = int(raw_text)   
    try:
        for i in range(arg-1, len(links)):
            Vxy = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
            url = "https://" + Vxy
            link0 = "https://" + Vxy
            urlcpvod = "https://dragoapi.vercel.app/video/https://" + Vxy
            
            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            if "acecwply" in url:
                cmd = f'yt-dlp -o "{name}.%(ext)s" -f "bestvideo[height<={raw_text2}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'
                
            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            elif 'videos.classplusapp' in url or "tencdn.classplusapp" in url or "webvideos.classplusapp.com" in url or "media-cdn-alisg.classplusapp.com" in url or "videos.classplusapp" in url or "videos.classplusapp.com" in url or "media-cdn-a.classplusapp" in url or "media-cdn.classplusapp" in url or "alisg-cdn-a.classplusapp" in url:
             url = requests.get(f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}', headers={'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9r'}).json()['url']
                                        
            elif "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
             url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={PW}"

            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            if "," in raw_text3:
                 name = f'{PRENAME} {name1[:60]}'
            else:
                 name = f'{name1[:60]}'
                        
            #if 'cpvod.testbook.com' in url:
               #url = requests.get(f'http://api.masterapi.tech/akamai-player-v3?url={url}', headers={'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9r'}).json()['url']
               #url0 = f"https://dragoapi.vercel.app/video/{url}"
                
            if "/master.mpd" in url:
                cmd= f" yt-dlp -k --allow-unplayable-formats -f bestvideo.{quality} --fixup never {url} "
                print("counted")

            if "edge.api.brightcove.com" in url:
                bcov = 'bcov_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MjQyMzg3OTEsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiJVMFZ6TkdGU2NuQlZjR3h5TkZwV09FYzBURGxOZHowOSIsImlkIjoiZEUxbmNuZFBNblJqVEROVmFWTlFWbXhRTkhoS2R6MDkiLCJmaXJzdF9uYW1lIjoiYVcxV05ITjVSemR6Vm10ak1WUlBSRkF5ZVNzM1VUMDkiLCJlbWFpbCI6Ik5Ga3hNVWhxUXpRNFJ6VlhiR0ppWTJoUk0wMVdNR0pVTlU5clJXSkRWbXRMTTBSU2FHRnhURTFTUlQwPSIsInBob25lIjoiVUhVMFZrOWFTbmQ1ZVcwd1pqUTViRzVSYVc5aGR6MDkiLCJhdmF0YXIiOiJLM1ZzY1M4elMwcDBRbmxrYms4M1JEbHZla05pVVQwOSIsInJlZmVycmFsX2NvZGUiOiJOalZFYzBkM1IyNTBSM3B3VUZWbVRtbHFRVXAwVVQwOSIsImRldmljZV90eXBlIjoiYW5kcm9pZCIsImRldmljZV92ZXJzaW9uIjoiUShBbmRyb2lkIDEwLjApIiwiZGV2aWNlX21vZGVsIjoiU2Ftc3VuZyBTTS1TOTE4QiIsInJlbW90ZV9hZGRyIjoiNTQuMjI2LjI1NS4xNjMsIDU0LjIyNi4yNTUuMTYzIn19.snDdd-PbaoC42OUhn5SJaEGxq0VzfdzO49WTmYgTx8ra_Lz66GySZykpd2SxIZCnrKR6-R10F5sUSrKATv1CDk9ruj_ltCjEkcRq8mAqAytDcEBp72-W0Z7DtGi8LdnY7Vd9Kpaf499P-y3-godolS_7ixClcYOnWxe2nSVD5C9c5HkyisrHTvf6NFAuQC_FD3TzByldbPVKK0ag1UnHRavX8MtttjshnRhv5gJs5DQWj4Ir_dkMcJ4JaVZO3z8j0OxVLjnmuaRBujT-1pavsr1CCzjTbAcBvdjUfvzEhObWfA1-Vl5Y4bUgRHhl1U-0hne4-5fF0aouyu71Y6W0eg'
                url = url.split("bcov_auth")[0]+bcov
                
            if "youtu" in url:
                ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"
            
            if "jw-prod" in url:
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'

            elif "youtube.com" in url or "youtu.be" in url:
                cmd = f'yt-dlp --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}".mp4'

            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

            try:                                 
                if raw_text5 == "yes":
                    # Check the format of the link to extract video name and topic name accordingly
                    if links[i][0].startswith("("):
                        # Extract the topic name for format: (TOPIC) Video Name:URL
                        t_name = re.search(r"\((.*?)\)", links[i][0]).group(1).strip().upper()
                        v_name = re.search(r"\)\s*(.*?):", links[i][0]).group(1).strip()
                    else:
                        # Extract the topic name for format: Video Name (TOPIC):URL
                        t_name = re.search(r"\((.*?)\)", links[i][0]).group(1).strip().upper()
                        v_name = links[i][0].split("(", 1)[0].strip()
                    
                    cc = f'⋅ ─  ✨`{t_name}`✨  ─ ⋅\n\n[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{v_name} [{res}p] .mkv`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    cc1 = f'⋅ ─  ✨`{t_name}`✨  ─ ⋅\n\n[📕]Pdf Id : {str(count).zfill(3)}\n**File Title :** `{v_name} .pdf`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    cczip = f'⋅ ─  ✨`{t_name}`✨  ─ ⋅\n\n[📁]Zip Id : {str(count).zfill(3)}\n**Zip Title :** `{v_name} .zip`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n' 
                    ccimg = f'⋅ ─  ✨`{t_name}`✨  ─ ⋅\n\n[🖼️]Img Id : {str(count).zfill(3)}\n**Img Title :** `{v_name} .jpg`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    cccpvod = f'⋅ ─  ✨`{t_name}`✨  ─ ⋅\n\n[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{v_name} .mp4`\n<a href="{urlcpvod}">__**Click Here to Watch Stream**__</a>\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    ccyt = f'⋅ ─  ✨`{t_name}`✨  ─ ⋅\n\n[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{v_name} .mp4`\n<a href="{url}">__**Click Here to Watch Stream**__</a>\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                
                else:
                    cc = f'[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{name1} [{res}p] .mkv`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    cc1 = f'[📕]Pdf Id : {str(count).zfill(3)}\n**File Title :** `{name1} .pdf`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    cczip = f'[📁]Zip Id : {str(count).zfill(3)}\n**Zip Title :** `{name1} .zip`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n' 
                    ccimg = f'[🖼️]Img Id : {str(count).zfill(3)}\n**Img Title :** `{name1} .jpg`\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    cccpvod = f'[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{name1} .mp4`\n<a href="{urlcpvod}">__**Click Here to Watch Stream**__</a>\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                    ccyt = f'[🎥]Vid Id : {str(count).zfill(3)}\n**Video Title :** `{name1} .mp4`\n<a href="{url}">__**Click Here to Watch Stream**__</a>\n<blockquote>**Batch Name :** {b_name}</blockquote>\n\n**Extracted by➤**{CR}\n'
                
                  
                if "drive" in url:
                    try:
                        ka = await helper.download(url, name)
                        copy = await bot.send_document(chat_id=channel_id,document=ka, caption=cc1)
                        count+=1
                        os.remove(ka)
                        time.sleep(1)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        count+=1
                        continue

                elif ".pdf*" in url:
                    try:
                        url_part, key_part = url.split("*")
                        url = f"https://dragoapi.vercel.app/pdf/{url_part}*{key_part}"
                        cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await bot.send_document(chat_id=channel_id, document=f'{name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{name}.pdf')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        count += 1
                        continue   

                elif ".pdf" in url:
                    try:
                        await asyncio.sleep(4)
                        url = url.replace(" ", "%20")
                        scraper = cloudscraper.create_scraper()
                        response = scraper.get(url)
                        if response.status_code == 200:
                            with open(f'{name}.pdf', 'wb') as file:
                                file.write(response.content)
                            await asyncio.sleep(4)
                            copy = await bot.send_document(chat_id=channel_id, document=f'{name}.pdf', caption=cc1)
                            count += 1
                            os.remove(f'{name}.pdf')
                        else:
                            await bot.send_message(f"Failed to download PDF: {response.status_code} {response.reason}")
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        count += 1
                        continue

                elif ".pdf" in url:
                    try:
                        cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await bot.send_document(chat_id=channel_id, document=f'{name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{name}.pdf')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        count += 1
                        continue

                elif ".zip" in url:
                    try:
                        cmd = f'yt-dlp -o "{name}.zip" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await bot.send_document(chat_id=channel_id, document=f'{name}.zip', caption=cczip)
                        count += 1
                        os.remove(f'{name}.zip')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        count += 1
                        continue

                elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
                    try:
                        ext = url.split('.')[-1]
                        cmd = f'yt-dlp -o "{name}.{ext}" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await bot.send_photo(chat_id=m.chat.id, photo=f'{name}.{ext}', caption=cc1)
                        count += 1
                        os.remove(f'{name}.{ext}')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        count += 1
                        continue

              #  elif "cpvod.testbook.com" in url:
               #     try:
                #        await bot.send_photo(chat_id=channel_id, photo=photologo, caption=cccpvod)
               #         count +=1
              #      except Exception as e:
               #         await m.reply_text(str(e))    
                #        time.sleep(1)    
                 #       continue          

               # elif "youtu" in url:
                 #   try:
                       # await bot.send_photo(chat_id=channel_id, photo=photoyt, caption=ccyt)
                      #  count +=1
                   # except Exception as e:
                      #  await m.reply_text(str(e))    
                       # time.sleep(1)    
                      #  continue
     
                else:
                    remaining_links = len(links) - count
                    progress = (count / len(links)) * 100
                    #emoji_message = await show_random_emojis(message)
                    Show = f"**__Video Downloading__**\n<blockquote>{str(count).zfill(3)}) {name1}</blockquote>"
                  #  Show = f"🚀𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 » {progress:.2f}%\n┃\n" \
                   #        f"┣🔗𝐈𝐧𝐝𝐞𝐱 » {str(count)}/{len(links)}\n┃\n" \
                        #   f"╰━🖇️𝐑𝐞𝐦𝐚𝐢𝐧𝐢𝐧𝐠 𝐋𝐢𝐧𝐤𝐬 » {remaining_links}\n\n" \
                      #     f"**⚡Dᴏᴡɴʟᴏᴀᴅ Sᴛᴀʀᴛᴇᴅ...⏳**\n\n" \
                       #    f"📚𝐓𝐢𝐭𝐥𝐞 » `{name}`\n┃\n" \
                       #    f"┣🍁𝐐𝐮𝐚𝐥𝐢𝐭𝐲 » {raw_text2}p\n┃\n" \
                        #   f'┣━🔗𝐋𝐢𝐧𝐤 » <a href="{link0}">__**Click Here to Open Link**__</a>\n┃\n' \
                         #  f'╰━━🖼️𝐓𝐡𝐮𝐦𝐛𝐧𝐚𝐢𝐥 » <a href="{raw_text6}">__**Thumb View**__</a>\n\n' \
                          # f"✦𝐁𝐨𝐭 𝐌𝐚𝐝𝐞 𝐁𝐲 ✦ `𝙎𝘼𝙄𝙉𝙄 𝘽𝙊𝙏𝙎🐦`"
                    prog = await bot.send_message(channel_id, Show, disable_web_page_preview=True)
                    res_file = await helper.download_video(url, cmd, name)
                    filename = res_file
                    await prog.delete(True)
                    #await emoji_message.delete()
                    await helper.send_vid(bot, m, cc, filename, thumb, name, prog, channel_id)
                    count += 1
                    time.sleep(1)

            except Exception as e:
                await bot.send_message(channel_id, f'⚠️**Downloading Failed**⚠️\n**Name** =>> `{str(count).zfill(3)} {name1}`\n**Url** =>> {link0}', disable_web_page_preview=True)
                count += 1
                failed_count += 1
                continue

    except Exception as e:
        await m.reply_text(e)
    success_count = len(links) - failed_count
    await bot.send_message(channel_id, f"-┈━═.•°✅ Completed ✅°•.═━┈-\n<blockquote>🎯𝙱𝚊𝚝𝚌𝚑 𝙽𝚊𝚖𝚎 » {b_name}</blockquote>\n\n<blockquote>🔗 Total URLs: {len(links)} \n┃   ┠🔴 Total Failed URLs: {failed_count}\n┃   ┠🟢 Total Successful URLs: {success_count}\n┃   ┃   ┠🎥 Total Video URLs: {other_count}\n┃   ┃   ┠📄 Total PDF URLs: {pdf_count}\n┃   ┃   ┠📸 Total IMAGE URLs: {img_count}</blockquote>\n")
    
#================================================================================================================================
# ==== START ====
async def main():
    await bot.start()
    asyncio.create_task(auto_remove_expired_users())
    print("Bot is running...")
    await idle()

from pyrogram import idle

if __name__ == "__main__":
    asyncio.run(main())
