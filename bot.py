import os
import sys
import json
import time
import asyncio
import random
import logging
from datetime import datetime

# Auto install packages
os.system("pip install telethon nest_asyncio firebase-admin -q")

import nest_asyncio
nest_asyncio.apply()

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, DeleteChatUserRequest
from telethon.tl.functions.phone import JoinGroupCallRequest
from telethon.tl.functions.account import UpdateStatusRequest, UpdateProfileRequest
from telethon.tl.types import UserEmpty
from telethon.errors import (
    SessionPasswordNeededError,
    UserAlreadyParticipantError,
    PasswordHashInvalidError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    RPCError,
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeEmptyError
)

# ===== FIREBASE IMPORTS =====
import firebase_admin
from firebase_admin import credentials, db

# ===== FIREBASE INITIALIZATION =====
FIREBASE_ACTIVE = False
try:
    # Check if firebase config file exists
    if os.path.exists("firebase-config.json"):
        cred = credentials.Certificate("firebase-config.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://bossmodpro-default-rtdb.firebaseio.com/'
        })
        print("✅ Firebase Connected Successfully!")
        FIREBASE_ACTIVE = True
    else:
        print("⚠️ firebase-config.json not found. Using local storage only.")
except Exception as e:
    print(f"⚠️ Firebase Connection Error: {e}")
    print("⚠️ Using local file storage only!")

# ===== CONFIGURATION =====
API_ID = 36750842
API_HASH = '5e211599a50d0a467d57d52ea73fe49c'
BOT_TOKEN = '8669699293:AAEEHvvmcMuvgRYCM-kF2iTrGTJtyZ9BhnI'
SUDO_USERS = [6304445582, 5826061877]
DB_FILE = "sessions.json"
ADMIN_FILE = "admins.json"
OWNER_TAG = "BOSSMODSPRO1"
WELCOME_PIC = "https://missing-tan-xya9g9mrok.edgeone.app/IMG_20260310_131824_473.jpg"

# ===== GLOBAL VARIABLES =====
ONLINE_REGISTRY = {}
ACTIVE_CLIENTS = []
START_TIME = datetime.now()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TITAN")

# ===== FIREBASE DATABASE FUNCTIONS =====
def load_data(file):
    if file == DB_FILE and FIREBASE_ACTIVE:
        # Firebase से sessions load करो
        try:
            ref = db.reference('/sessions')
            data = ref.get()
            if data:
                print(f"✅ Loaded {len(data)} sessions from Firebase")
                return data
            else:
                print("📭 No sessions found in Firebase")
                return []
        except Exception as e:
            print(f"❌ Firebase load error: {e}")
            # Fallback to local file
            if os.path.exists(file):
                try:
                    with open(file, 'r') as f:
                        return json.load(f)
                except:
                    return []
            return []
    else:
        # Local file से load करो
        if os.path.exists(file):
            try:
                with open(file, 'r') as f:
                    return json.load(f)
            except:
                return []
    return []

def save_data(file, data):
    if file == DB_FILE and FIREBASE_ACTIVE:
        # Firebase में save करो
        try:
            ref = db.reference('/sessions')
            ref.set(data)
            print(f"✅ Saved {len(data)} sessions to Firebase")
            return True
        except Exception as e:
            print(f"❌ Firebase save error: {e}")
            # Fallback to local file
            try:
                with open(file, 'w') as f:
                    json.dump(data, f, indent=4)
                return True
            except:
                return False
    else:
        # Local file में save करो
        try:
            with open(file, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except:
            return False

def get_admins():
    admins = load_data(ADMIN_FILE)
    return list(set(SUDO_USERS + admins))

def is_admin(user_id):
    return user_id in get_admins()

bot = TelegramClient('titan', API_ID, API_HASH)

# ===== BACK BUTTON FUNCTION =====
def back_button():
    return [Button.inline("🔙 Back to Menu", b"back")]

# ===== GHOST ONLINE LOGIC =====
async def start_ghost_online(client, phone):
    if phone in ONLINE_REGISTRY:
        return
    
    ONLINE_REGISTRY[phone] = True
    logger.info(f"🟢 Online started for {phone}")

    try:
        while phone in ONLINE_REGISTRY:
            await client(UpdateStatusRequest(offline=False))
            wait_time = random.randint(20, 40)
            await asyncio.sleep(wait_time)
    except Exception as e:
        logger.error(f"❌ Online Error for {phone}: {e}")
    finally:
        if phone in ONLINE_REGISTRY:
            del ONLINE_REGISTRY[phone]
        logger.info(f"⚫ Online stopped for {phone}")

async def join_group(client, link):
    link = link.replace("https://t.me/", "").replace("t.me/", "").replace("@", "")
    try:
        if "+" in link or "joinchat" in link:
            hash_part = link.split('/')[-1].replace('+', '')
            await client(ImportChatInviteRequest(hash_part))
        else:
            await client(JoinChannelRequest(link))
        return True
    except UserAlreadyParticipantError:
        return True
    except:
        return False

# ===== FIXED LEAVE GROUP FUNCTION =====
async def leave_group(client, link):
    """Group/channel se leave karne ke liye - FIXED VERSION"""
    link = link.strip()
    
    # Clean the link properly
    original_link = link
    link = link.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").replace("+", "")
    
    try:
        # Try to get the entity
        try:
            # First try with the cleaned link
            entity = await client.get_entity(link)
        except:
            # If that fails, try with the original username format
            if "/" in original_link:
                parts = original_link.split('/')
                username = parts[-1].split('?')[0]
                try:
                    entity = await client.get_entity(f"@{username}")
                except:
                    entity = await client.get_entity(username)
            else:
                raise
        
        # Leave the channel/group
        await client(LeaveChannelRequest(entity))
        return True
        
    except FloodWaitError as e:
        # Handle flood wait
        logger.warning(f"Flood wait: {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
        try:
            await client(LeaveChannelRequest(entity))
            return True
        except:
            return False
    except UserAlreadyParticipantError:
        # Already left? This is actually good
        return True
    except Exception as e:
        logger.error(f"Leave error: {e}")
        return False

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    if event.sender_id not in get_admins():
        await event.reply("❌ Access Denied!")
        return
    db = load_data(DB_FILE)
    online_count = len(ONLINE_REGISTRY)
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    
    # Firebase status
    fb_status = "✅ ACTIVE" if FIREBASE_ACTIVE else "❌ NOT CONNECTED"
    
    menu = [
        [Button.inline("👤 Add ID", b"add"), Button.inline("📑 List IDs", b"list")],
        [Button.inline("🚀 Joiner", b"join"), Button.inline("🔫 VC Force", b"vc")],
        [Button.inline("🧹 Cleanup", b"clean"), Button.inline("🚪 Leave All", b"leave_all")],
        [Button.inline("➕ Add Admin", b"adm_add"), Button.inline("➖ Rem Admin", b"adm_rem")],
        [Button.inline("👥 Admin List", b"adm_list"), Button.inline("🗑️ Remove Account", b"remove_acc")],
        [Button.inline("📊 Stats", b"stats"), Button.url("👑 Owner", f"https://t.me/{OWNER_TAG}")]
    ]
    await bot.send_file(
        event.chat_id,
        WELCOME_PIC,
        caption=(
            f"⚡ **TITAN V50** ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 **Owner:** @{OWNER_TAG}\n"
            f"📲 **IDs:** `{len(db)}`\n"
            f"🟢 **Online:** `{online_count}`\n"
            f"👥 **Admins:** `{len(get_admins())}`\n"
            f"🔥 **Firebase:** {fb_status}\n"
            f"⏱️ **Uptime:** `{uptime}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        ),
        buttons=menu
    )

@bot.on(events.CallbackQuery)
async def callback(event):
    if event.sender_id not in get_admins():
        return await event.answer("Access Denied!", alert=True)
    data = event.data.decode()
    db = load_data(DB_FILE)

    # ===== BACK TO MAIN MENU =====
    if data == "back":
        await start(event)
        return

    # ===== ADD ID - 2FA FIXED =====
    if data == "add":
        async with bot.conversation(event.chat_id, timeout=300) as conv:
            await conv.send_message("📱 **Phone Number (with +91):**")
            phone = (await conv.get_response()).text.strip()
            
            if not phone.startswith('+'):
                phone = '+' + phone
            
            status = await conv.send_message("⏳ **Connecting to Telegram...**")
            
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            two_fa_enabled = False  # Flag for 2FA status
            
            try:
                await status.edit("📤 **Sending OTP...**")
                sent = await client.send_code_request(phone)
                
                await conv.send_message("🔑 **Enter OTP:**")
                otp = (await conv.get_response()).text.strip()
                
                try:
                    await status.edit("🔓 **Logging in with OTP...**")
                    await client.sign_in(phone, otp, phone_code_hash=sent.phone_code_hash)
                    
                except SessionPasswordNeededError:
                    two_fa_enabled = True  # 2FA is enabled
                    await conv.send_message("🔐 **2FA Password Required!**")
                    
                    # Try password (max 3 attempts)
                    password_attempts = 0
                    max_attempts = 3
                    password_success = False
                    
                    while password_attempts < max_attempts and not password_success:
                        await conv.send_message(f"🔐 **Enter 2FA Password (Attempt {password_attempts + 1}/{max_attempts}):**")
                        password = (await conv.get_response()).text
                        
                        try:
                            await status.edit("🔓 **Verifying 2FA...**")
                            await client.sign_in(password=password)
                            password_success = True
                            
                        except PasswordHashInvalidError:
                            password_attempts += 1
                            if password_attempts < max_attempts:
                                await conv.send_message(f"❌ **Wrong Password!** {max_attempts - password_attempts} attempts left.")
                            else:
                                await conv.send_message("❌ **Too many wrong attempts! Login failed.**")
                                await client.disconnect()
                                await status.delete()
                                await start(event)
                                return
                        except FloodWaitError as e:
                            await conv.send_message(f"❌ **Flood Wait! Try after {e.seconds} seconds**")
                            await client.disconnect()
                            await status.delete()
                            await start(event)
                            return
                    
                    if not password_success:
                        await conv.send_message("❌ **Failed to login with 2FA!**")
                        await client.disconnect()
                        await status.delete()
                        await start(event)
                        return
                
                me = await client.get_me()
                session_str = client.session.save()
                
                # Start ghost online
                if await client.is_user_authorized():
                    asyncio.create_task(start_ghost_online(client, phone))
                    ACTIVE_CLIENTS.append(client)
                
                exists = False
                for i, acc in enumerate(db):
                    if acc['phone'] == phone:
                        db[i]['string'] = session_str
                        exists = True
                        break
                
                if not exists:
                    db.append({"phone": phone, "string": session_str})
                
                save_data(DB_FILE, db)
                
                # Show 2FA status in success message
                twofa_status = "✅ Enabled" if two_fa_enabled else "❌ Not Enabled"
                
                await conv.send_message(
                    f"✅ **Login Successful!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Name:** {me.first_name}\n"
                    f"🆔 **Username:** @{me.username if me.username else 'None'}\n"
                    f"🔐 **2FA:** {twofa_status}\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                
            except PhoneCodeInvalidError:
                await conv.send_message("❌ **Invalid OTP!**")
            except PhoneCodeExpiredError:
                await conv.send_message("❌ **OTP Expired! Please try again.**")
            except PhoneNumberInvalidError:
                await conv.send_message("❌ **Invalid Phone Number!**")
            except FloodWaitError as e:
                await conv.send_message(f"❌ **Flood Wait! Try after {e.seconds} seconds**")
            except Exception as e:
                await conv.send_message(f"❌ **Error:** {str(e)}")
            finally:
                await client.disconnect()
                await status.delete()
        await start(event)

    # ===== FIXED LEAVE ALL =====
    elif data == "leave_all":
        if not db:
            await event.answer("❌ No IDs!", alert=True)
            return
        
        async with bot.conversation(event.chat_id, timeout=300) as conv:
            await conv.send_message(
                "🔗 **Enter Group/Channel Link to leave from:**\n"
                "Example: @username or https://t.me/username",
                buttons=back_button()
            )
            link = (await conv.get_response()).text
            if link.lower() == "back":
                await start(event)
                return
            
            # First check if we can access the group
            try:
                test_client = TelegramClient(StringSession(db[0]['string']), API_ID, API_HASH)
                await test_client.connect()
                
                # Try to join first (to make sure we have access)
                join_success = await join_group(test_client, link)
                if not join_success:
                    await test_client.disconnect()
                    await conv.send_message("❌ **Cannot access this group/channel!**")
                    await start(event)
                    return
                
                await test_client.disconnect()
            except Exception as e:
                await conv.send_message(f"❌ **Error accessing group:** {str(e)}")
                await start(event)
                return
            
            await conv.send_message(f"🔢 **How many accounts to leave? (Max {len(db)}):**")
            try:
                qty_text = (await conv.get_response()).text
                if qty_text.lower() == "back":
                    await start(event)
                    return
                qty = int(qty_text)
                qty = min(qty, len(db))
            except ValueError:
                await conv.send_message("❌ **Invalid number!**")
                await start(event)
                return
            
            await conv.send_message("⏱️ **Delay between leaves (seconds):**")
            try:
                delay_text = (await conv.get_response()).text
                if delay_text.lower() == "back":
                    await start(event)
                    return
                delay = int(delay_text)
            except ValueError:
                await conv.send_message("❌ **Invalid delay!**")
                await start(event)
                return
            
            # Confirmation
            await conv.send_message(
                f"⚠️ **Confirm Leave Operation**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📍 Link: {link}\n"
                f"📊 Accounts: {qty}\n"
                f"⏱️ Delay: {delay}s\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Type **yes** to confirm:"
            )
            
            confirm = (await conv.get_response()).text
            if confirm.lower() != "yes":
                await conv.send_message("❌ **Cancelled!**")
                await start(event)
                return
            
            msg = await conv.send_message(f"🚪 **Leaving 0/{qty}...**")
            done = 0
            failed = 0
            
            for i, acc in enumerate(db[:qty], 1):
                client = None
                try:
                    client = TelegramClient(StringSession(acc['string']), API_ID, API_HASH)
                    await client.connect()
                    
                    # Check if authorized
                    if not await client.is_user_authorized():
                        failed += 1
                        await msg.edit(f"Progress: {i}/{qty} | ✅ Left: {done} | ❌ Failed: {failed} (Unauthorized)")
                        continue
                    
                    # Start ghost online for this account
                    asyncio.create_task(start_ghost_online(client, acc['phone']))
                    
                    # Leave the group
                    if await leave_group(client, link):
                        done += 1
                    else:
                        failed += 1
                    
                    await msg.edit(f"Progress: {i}/{qty} | ✅ Left: {done} | ❌ Failed: {failed}")
                    
                    # Wait before next leave
                    if i < qty:
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Leave error for {acc['phone']}: {e}")
                    failed += 1
                finally:
                    if client:
                        await client.disconnect()
                
                # Small break every 10 accounts to avoid flood
                if i % 10 == 0 and i < qty:
                    await asyncio.sleep(5)
            
            # Final message
            await msg.edit(
                f"✅ **Leave Operation Complete!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📍 Link: {link}\n"
                f"📊 Total: {qty}\n"
                f"✅ Success: {done}\n"
                f"❌ Failed: {failed}\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                buttons=back_button()
            )
        await start(event)

    # ===== REMOVE ACCOUNT =====
    elif data == "remove_acc":
        if not db:
            await event.answer("❌ No accounts to remove!", alert=True)
            await start(event)
            return
        
        normal_accounts = []
        for acc in db:
            normal_accounts.append(acc)
        
        if not normal_accounts:
            await event.edit("❌ **No removable accounts found!**", buttons=back_button())
            return
        
        text = "🗑️ **Select account to remove:**\n\n"
        buttons = []
        
        for i, acc in enumerate(normal_accounts[:10], 1):
            text += f"{i}. {acc['phone']}\n"
            buttons.append([Button.inline(f"❌ {i}. {acc['phone'][-4:]}", f"del_{i-1}")])
        
        if len(normal_accounts) > 10:
            text += f"\n... {len(normal_accounts)-10} more accounts (show first 10)"
        
        text += "\n\n⚠️ **Select an account to remove permanently**"
        buttons.append([Button.inline("🔙 Back", b"back")])
        
        await event.edit(text, buttons=buttons)

    # ===== DELETE SELECTED ACCOUNT =====
    elif data.startswith("del_"):
        idx = int(data.split("_")[1])
        
        if 0 <= idx < len(db):
            removed_phone = db[idx]['phone']
            
            # Remove from database
            new_db = [acc for i, acc in enumerate(db) if i != idx]
            save_data(DB_FILE, new_db)
            
            # Stop online engine
            if removed_phone in ONLINE_REGISTRY:
                del ONLINE_REGISTRY[removed_phone]
            
            await event.edit(f"✅ **Account Removed:** `{removed_phone}`", buttons=back_button())
        else:
            await event.edit("❌ **Invalid selection!**", buttons=back_button())

    # ===== JOINER =====
    elif data == "join":
        if not db:
            await event.answer("No IDs!", alert=True)
            return
        async with bot.conversation(event.chat_id, timeout=300) as conv:
            await conv.send_message("🔗 Link:", buttons=back_button())
            link = (await conv.get_response()).text
            if link == "back":
                await start(event)
                return
            
            await conv.send_message(f"🔢 Quantity (Max {len(db)}):")
            qty = int((await conv.get_response()).text)
            qty = min(qty, len(db))
            
            await conv.send_message("⏱️ Delay (sec):")
            delay = int((await conv.get_response()).text)
            
            msg = await conv.send_message(f"Joining 0/{qty}")
            done = 0
            failed = 0
            
            for i, acc in enumerate(db[:qty], 1):
                client = TelegramClient(StringSession(acc['string']), API_ID, API_HASH)
                try:
                    await client.connect()
                    
                    if await client.is_user_authorized():
                        asyncio.create_task(start_ghost_online(client, acc['phone']))
                        ACTIVE_CLIENTS.append(client)
                    
                    if await join_group(client, link):
                        done += 1
                    else:
                        failed += 1
                    
                    await msg.edit(f"Progress: {i}/{qty} | ✅ {done} | ❌ {failed}")
                    if i < qty:
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Join error: {e}")
                    failed += 1
            
            await msg.edit(f"✅ Complete! Joined: {done}/{qty} | Failed: {failed}", buttons=back_button())
        await start(event)

    # ===== VC FORCE =====
    elif data == "vc":
        if not db:
            await event.answer("No IDs!", alert=True)
            return
        async with bot.conversation(event.chat_id, timeout=300) as conv:
            await conv.send_message("🎙️ Link (VC active):", buttons=back_button())
            link = (await conv.get_response()).text
            if link == "back":
                await start(event)
                return
            
            # Check VC first
            temp = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp.connect()
            test = TelegramClient(StringSession(db[0]['string']), API_ID, API_HASH)
            await test.connect()
            
            try:
                if not await join_group(test, link):
                    await conv.send_message("❌ Can't join group")
                    return
                full = await test(GetFullChannelRequest(link))
                if not full.full_chat.call:
                    await conv.send_message("❌ No active VC")
                    return
                call = full.full_chat.call
            except Exception as e:
                await conv.send_message(f"❌ Error: {str(e)}")
                return
            finally:
                await test.disconnect()
                await temp.disconnect()
            
            await conv.send_message(f"🔢 Quantity (Max {len(db)}):")
            qty = int((await conv.get_response()).text)
            qty = min(qty, len(db))
            
            await conv.send_message("⏱️ Delay:")
            delay = int((await conv.get_response()).text)
            
            msg = await conv.send_message("Joining VC...")
            done = 0
            
            for i, acc in enumerate(db[:qty], 1):
                client = TelegramClient(StringSession(acc['string']), API_ID, API_HASH)
                try:
                    await client.connect()
                    
                    if await client.is_user_authorized():
                        asyncio.create_task(start_ghost_online(client, acc['phone']))
                        ACTIVE_CLIENTS.append(client)
                    
                    await join_group(client, link)
                    await asyncio.sleep(2)
                    me = await client.get_me()
                    await client(JoinGroupCallRequest(call=call, join_as=me, muted=True))
                    done += 1
                    
                    await msg.edit(f"VC: {i}/{qty} | ✅ {done}")
                    if i < qty:
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"VC error: {e}")
            
            await msg.edit(f"✅ VC Complete! Joined: {done}/{qty}", buttons=back_button())
        await start(event)

    # ===== CLEANUP =====
    elif data == "clean":
        if not db:
            await event.answer("No IDs!", alert=True)
            return
        async with bot.conversation(event.chat_id, timeout=300) as conv:
            await conv.send_message("🔗 Group Link:", buttons=back_button())
            link = (await conv.get_response()).text
            if link == "back":
                await start(event)
                return
            
            # Get chat ID
            temp = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp.connect()
            test = TelegramClient(StringSession(db[0]['string']), API_ID, API_HASH)
            await test.connect()
            
            try:
                await join_group(test, link)
                full = await test(GetFullChannelRequest(link))
                chat_id = full.chats[0].id
            except Exception as e:
                await conv.send_message(f"❌ Error: {str(e)}")
                return
            finally:
                await test.disconnect()
                await temp.disconnect()
            
            await conv.send_message(f"🔢 IDs (Max {len(db)}):")
            qty = int((await conv.get_response()).text)
            qty = min(qty, len(db))
            
            msg = await conv.send_message("Cleaning...")
            total = 0
            
            for i, acc in enumerate(db[:qty], 1):
                client = TelegramClient(StringSession(acc['string']), API_ID, API_HASH)
                try:
                    await client.connect()
                    
                    if await client.is_user_authorized():
                        asyncio.create_task(start_ghost_online(client, acc['phone']))
                        ACTIVE_CLIENTS.append(client)
                    
                    await join_group(client, link)
                    await asyncio.sleep(2)
                    
                    users = await client.get_participants(chat_id, limit=200)
                    removed = 0
                    
                    for u in users:
                        if isinstance(u, UserEmpty) or getattr(u, 'deleted', False):
                            try:
                                await client.kick_participant(chat_id, u.id)
                                removed += 1
                                await asyncio.sleep(1)
                            except:
                                pass
                    
                    total += removed
                    await msg.edit(f"ID {i}: Removed {removed}")
                    
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
            
            await msg.edit(f"✅ Cleanup Complete! Removed: {total}", buttons=back_button())
        await start(event)

    # ===== ADMIN LIST =====
    elif data == "adm_list":
        admins = get_admins()
        sudo_list = SUDO_USERS
        other_admins = [a for a in admins if a not in sudo_list]
        
        text = "👥 **Admin List**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "👑 **Sudo Users:**\n"
        for i, uid in enumerate(sudo_list, 1):
            text += f"{i}. `{uid}`\n"
        
        if other_admins:
            text += "\n👤 **Other Admins:**\n"
            for i, uid in enumerate(other_admins, 1):
                text += f"{i}. `{uid}`\n"
        else:
            text += "\n👤 **Other Admins:** None\n"
        
        text += f"\n**Total:** {len(admins)} Admins"
        await event.edit(text, buttons=back_button())

    # ===== STATS =====
    elif data == "stats":
        total = len(db)
        online = len(ONLINE_REGISTRY)
        admins = len(get_admins())
        uptime = str(datetime.now() - START_TIME).split('.')[0]
        fb_status = "✅ Connected" if FIREBASE_ACTIVE else "❌ Not Connected"
        
        await event.edit(
            f"📊 **TITAN STATS**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📲 IDs: {total}\n"
            f"🟢 Online: {online}\n"
            f"👑 Admins: {admins}\n"
            f"🔥 Firebase: {fb_status}\n"
            f"⏱️ Uptime: {uptime}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            buttons=back_button()
        )

    # ===== LIST =====
    elif data == "list":
        if not db:
            return await event.answer("Empty!", alert=True)
        text = "📋 **Titan IDs:**\n\n"
        online_count = 0
        for i, acc in enumerate(db[:20], 1):
            status = "🟢" if acc['phone'] in ONLINE_REGISTRY else "⚪"
            if acc['phone'] in ONLINE_REGISTRY:
                online_count += 1
            text += f"{i}. {status} {acc['phone']}\n"
        if len(db) > 20:
            text += f"\n... {len(db)-20} more"
        text += f"\n\n**Total:** {len(db)} | 🟢 **Online:** {online_count}"
        await event.edit(text, buttons=back_button())

    # ===== ADD ADMIN =====
    elif data == "adm_add":
        if event.sender_id not in SUDO_USERS:
            return await event.answer("Sudo Only!", alert=True)
        async with bot.conversation(event.chat_id) as conv:
            await conv.send_message("🆔 User ID:", buttons=back_button())
            uid = (await conv.get_response()).text
            if uid == "back":
                await start(event)
                return
            try:
                uid = int(uid)
                admins = load_data(ADMIN_FILE)
                if uid not in admins:
                    admins.append(uid)
                    save_data(ADMIN_FILE, admins)
                    await conv.send_message(f"✅ Added: {uid}", buttons=back_button())
                else:
                    await conv.send_message("❌ Already admin", buttons=back_button())
            except:
                await conv.send_message("❌ Invalid", buttons=back_button())
        await start(event)

    # ===== REMOVE ADMIN =====
    elif data == "adm_rem":
        if event.sender_id not in SUDO_USERS:
            return await event.answer("Sudo Only!", alert=True)
        async with bot.conversation(event.chat_id) as conv:
            await conv.send_message("🆔 User ID:", buttons=back_button())
            uid = (await conv.get_response()).text
            if uid == "back":
                await start(event)
                return
            try:
                uid = int(uid)
                admins = load_data(ADMIN_FILE)
                if uid in admins and uid not in SUDO_USERS:
                    admins.remove(uid)
                    save_data(ADMIN_FILE, admins)
                    await conv.send_message(f"✅ Removed: {uid}", buttons=back_button())
                elif uid in SUDO_USERS:
                    await conv.send_message("❌ Cannot remove Sudo User!", buttons=back_button())
                else:
                    await conv.send_message("❌ Not admin", buttons=back_button())
            except:
                await conv.send_message("❌ Invalid", buttons=back_button())
        await start(event)

@bot.on(events.NewMessage(pattern='/ping'))
async def ping(event):
    if event.sender_id not in get_admins():
        return
    start = time.time()
    m = await event.reply("🏓")
    await m.edit(f"🏓 {round((time.time()-start)*1000)}ms")

async def main():
    print("\n" + "="*60)
    print("⚡ TITAN V50 - FIREBASE INTEGRATED")
    print("="*60)
    print(f"👑 Owner: @{OWNER_TAG}")
    print(f"👥 Total Admins: {len(get_admins())}")
    print(f"🔥 Firebase: {'✅ ACTIVE' if FIREBASE_ACTIVE else '❌ NOT CONNECTED'}")
    print("✅ IDs will NEVER be lost!")
    print("="*60)
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Bot started!")
    print("="*60)
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopped")
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
        os.execl(sys.executable, sys.executable, *sys.argv)
