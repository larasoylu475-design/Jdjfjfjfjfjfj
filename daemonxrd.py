import logging
logging.getLogger('telebot').disabled = True
logging.disable(logging.CRITICAL)

import telebot
from telebot import types
from requests import post, get, Session
import threading, uuid, time
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import os

# ---------------- CONFIG ---------------- #
BOT_TOKEN = "7741122025:AAEMNBqNq-yHaYlA9-mqLLTqoDznAfJFhqs"  # <-- Replace with your bot token
bot = telebot.TeleBot(BOT_TOKEN)

# Encryption key (in memory only)
key = base64.urlsafe_b64encode(os.urandom(32))
fernet = Fernet(key)

# Bot commands
bot.set_my_commands([
    types.BotCommand("/start", "Welcome message"),
    types.BotCommand("/login", "Login to your Instagram account"),
    types.BotCommand("/sessionlogin", "Login using Instagram sessionid"),
    types.BotCommand("/logout", "Logout from Instagram"),
    types.BotCommand("/report", "Start continuous reporting"),
    types.BotCommand("/singlereport", "Submit a single report"),
    types.BotCommand("/bulkreport", "Submit multiple reports"),
    types.BotCommand("/stop", "Stop ongoing reports"),
    types.BotCommand("/help", "Show usage instructions")
])

# Expiration check
expiration_date = datetime(2027, 12, 31)
if datetime.now() > expiration_date:
    print("Tool Disabled")
    exit()

uid = str(uuid.uuid4())
sessions = {}          # {chat_id: encrypted session data}
report_threads = {}    # {chat_id: threading.Event()}

# ---------------- HELP ---------------- #
@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = (
        "📖 **Bot Commands:**\n\n"
        "/start - Welcome message\n"
        "/login - Login to Instagram\n"
        "/sessionlogin - Login using sessionid\n"
        "/logout - Logout from Instagram\n"
        "/report - Continuous report\n"
        "/singlereport - Single report\n"
        "/bulkreport - Bulk report\n"
        "/stop - Stop ongoing reports\n"
        "/help - Show this help message"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

# ---------------- SESSION ---------------- #
def store_session(chat_id, username, sessionid, csrftoken):
    data = f"{username}|{sessionid}|{csrftoken}".encode()
    encrypted = fernet.encrypt(data)
    sessions[chat_id] = encrypted

def get_session(chat_id):
    encrypted = sessions.get(chat_id)
    if not encrypted:
        return None
    decrypted = fernet.decrypt(encrypted).decode()
    username, sessionid, csrftoken = decrypted.split("|")
    return {'username': username, 'sessionid': sessionid, 'csrftoken': csrftoken}

def logout_session(chat_id):
    if chat_id in sessions:
        del sessions[chat_id]

# ---------------- ANIMATION ---------------- #
def animate_message(chat_id, msg_id, stop_event):
    animation = ["▁▁▁▁","▂▁▁▁","▃▂▁▁","▄▃▂▁","▅▄▃▂","▆▅▄▃","▇▆▅▄","█▇▆▅","▇▆▅▄","▆▅▄▃","▅▄▃▂","▄▃▂▁"]
    i = 0
    while not stop_event.is_set():
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=msg_id,
                                  text=f"⏳ Reporting in progress {animation[i % len(animation)]}")
        except: pass
        i += 1
        time.sleep(0.2)

# ---------------- REPORT ---------------- #
def report_instagram(chat_id, target_id, sessionid, csrftoken, reportType, delay, stop_event):
    msg = bot.send_message(chat_id, "⏳ Reporting started...")
    threading.Thread(target=animate_message, args=(chat_id, msg.message_id, stop_event)).start()

    while not stop_event.is_set():
        try:
            bot.send_chat_action(chat_id, 'typing')
            r3 = post(
                f"https://i.instagram.com/users/{target_id}/flag/",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Host": "i.instagram.com",
                    "cookie": f"sessionid={sessionid}",
                    "X-CSRFToken": csrftoken,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                },
                data=f'source_name=&reason_id={reportType}&frx_context=',
                allow_redirects=False
            )
            if r3.status_code == 429:
                stop_event.set()
                bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                                      text="⚠️ Account flagged! Too many requests.")
                break
            elif r3.status_code >= 500:
                stop_event.set()
                bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                                      text="❌ Target not found or server error.")
                break
            else:
                bot.send_message(chat_id, "✅ Report sent successfully")
            for _ in range(delay):
                if stop_event.is_set(): break
                time.sleep(1)
        except Exception as e:
            stop_event.set()
            bot.send_message(chat_id, f"❌ Report failed: {str(e)}")
            break
    bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text="🛑 Reporting stopped.")

# ---------------- LOGIN ---------------- #
def login_user(chat_id, username, password):
    try:
        r1 = post(
            'https://i.instagram.com/api/v1/accounts/login/',
            headers={'User-Agent': 'Instagram 114.0.0.38.120 Android', "Accept": "*/*"},
            data={'_uuid': uid, 'password': password, 'username': username, 'device_id': uid,
                  'from_reg': 'false', '_csrftoken': 'missing', 'login_attempt_count': '0'},
            allow_redirects=True
        )
        if 'logged_in_user' in r1.text:
            sessionid = r1.cookies['sessionid']
            csrftoken = r1.cookies['csrftoken']
            store_session(chat_id, username, sessionid, csrftoken)
            bot.send_message(chat_id, f"✅ Logged in as @{username}.\nUse /report, /singlereport or /bulkreport now.")
        else:
            bot.send_message(chat_id, f"❌ Login failed: {r1.text[:100]}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Login error: {str(e)}")

def login_with_session(chat_id, sessionid):
    try:
        s = Session()
        s.cookies.set("sessionid", sessionid)
        r = s.get("https://i.instagram.com/api/v1/accounts/current_user/", headers={
            "User-Agent": "Instagram 114.0.0.38.120 Android"
        })
        csrftoken = r.cookies.get("csrftoken", "")
        if r.status_code == 200 and csrftoken:
            username = r.json()['user']['username']
            store_session(chat_id, username, sessionid, csrftoken)
            bot.send_message(chat_id, f"✅ Logged in as @{username} using sessionid.\nNow use /report or /bulkreport.")
        else:
            bot.send_message(chat_id, "❌ Invalid sessionid or unable to fetch csrftoken.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Session login failed: {str(e)}")

# ---------------- BOT HANDLERS ---------------- #
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id, "welcome_message = (
    "🚀 *Welcome to Report Sending Tool*\n\n"
    "Hello! This is your advanced assistant for managing "
    "mass reporting tasks efficiently and securely.\n\n"
    "⚡ *Developed by:* `daemonxrd use /help - /ping`
")

@bot.message_handler(commands=['login'])
def login_handler(message):
    msg = bot.send_message(message.chat.id, "Enter your Instagram username:")
    bot.register_next_step_handler(msg, ask_password)

def ask_password(message):
    username = message.text
    msg = bot.send_message(message.chat.id, "Enter your Instagram password:")
    bot.register_next_step_handler(msg, lambda m: login_user(message.chat.id, username, m.text))

@bot.message_handler(commands=['sessionlogin'])
def session_login_handler(message):
    msg = bot.send_message(message.chat.id, "Enter your Instagram sessionid:")
    bot.register_next_step_handler(msg, lambda m: login_with_session(message.chat.id, m.text))

@bot.message_handler(commands=['logout'])
def logout_handler(message):
    logout_session(message.chat.id)
    bot.send_message(message.chat.id, "✅ Logged out successfully.")

# ---------------- REPORT REASON MAPPING ---------------- #
REPORT_OPTIONS = {
    1: "Spam",
    2: "Self-harm",
    3: "Drugs",
    4: "Nudity",
    5: "Violence",
    6: "Hate Speech",
    7: "Bully or Harassment",
    8: "Impersonation",
    9: "Fraud or Scam",
    10: "False Information",
    11: "Underage",
    12: "Firearms",     # was Invisible
    13: "Invisible"     # was Unlawful content
}

# ---------------- CONTINUOUS REPORT ---------------- #
@bot.message_handler(commands=['report'])
def report_handler(message):
    chat_id = message.chat.id
    session = get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ You must login first!")
        return
    msg = bot.send_message(chat_id, "Enter target Instagram username for continuous report:")
    bot.register_next_step_handler(msg, ask_report_type)

def ask_report_type(message):
    chat_id = message.chat.id
    target = message.text
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for k, v in REPORT_OPTIONS.items():
        markup.add(types.KeyboardButton(f"{k} - {v}"))
    msg = bot.send_message(chat_id, "Choose report type:", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: ask_report_delay(chat_id, target, m.text, REPORT_OPTIONS))

def ask_report_delay(chat_id, target, choice_text, options):
    try:
        reportType = int(choice_text.split(" - ")[0])
        if reportType not in options:
            raise ValueError("Invalid report type")
    except:
        bot.send_message(chat_id, "❌ Invalid choice. Try /report again.")
        return
    msg = bot.send_message(chat_id, "Enter time interval between reports (seconds):")
    bot.register_next_step_handler(msg, lambda m: start_reporting(chat_id, target, reportType, m.text))

def start_reporting(chat_id, target, reportType, delay_text):
    try:
        delay = int(delay_text)
    except:
        delay = 10
    session = get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Session not found, please login again.")
        return
    sessionid = session['sessionid']
    csrftoken = session['csrftoken']
    try:
        r2 = get(f"https://i.instagram.com/api/v1/users/{target}/usernameinfo/",
                 headers={"User-Agent": "Instagram 114.0.0.38.120 Android",
                          "Cookie": f"sessionid={sessionid}; csrftoken={csrftoken}"})
        target_id = r2.json()['user']['pk']
    except Exception as e:
        bot.send_message(chat_id, f"❌ Failed to find target user: {str(e)}")
        return
    stop_event = threading.Event()
    report_threads[chat_id] = stop_event
    threading.Thread(target=report_instagram, args=(chat_id, target_id, sessionid, csrftoken, reportType, delay, stop_event)).start()
    bot.send_message(chat_id, "🚀 Continuous reporting started! Use /stop to stop.")

# ---------------- STOP ---------------- #
@bot.message_handler(commands=['stop'])
def stop_handler(message):
    chat_id = message.chat.id
    if chat_id in report_threads:
        report_threads[chat_id].set()
        bot.send_message(chat_id, "🛑 Stopping reports...")
    else:
        bot.send_message(chat_id, "No reports are currently running.")

# ---------------- SINGLE REPORT ---------------- #
@bot.message_handler(commands=['singlereport'])
def single_report_handler(message):
    chat_id = message.chat.id
    session = get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Login first!")
        return
    msg = bot.send_message(chat_id, "Enter target username for single report:")
    bot.register_next_step_handler(msg, ask_single_report_type)

def ask_single_report_type(message):
    chat_id = message.chat.id
    target = message.text
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for k, v in REPORT_OPTIONS.items():
        markup.add(types.KeyboardButton(f"{k} - {v}"))
    msg = bot.send_message(chat_id, "Choose report type:", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: submit_single_report(chat_id, target, m.text, REPORT_OPTIONS))

def submit_single_report(chat_id, target, choice_text, options):
    try:
        reportType = int(choice_text.split(" - ")[0])
        if reportType not in options:
            raise ValueError("Invalid report type")
    except:
        bot.send_message(chat_id, "❌ Invalid choice.")
        return
    session = get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Session missing.")
        return
    sessionid = session['sessionid']
    csrftoken = session['csrftoken']
    try:
        r2 = get(f"https://i.instagram.com/api/v1/users/{target}/usernameinfo/",
                 headers={"User-Agent": "Instagram 114.0.0.38.120 Android",
                          "Cookie": f"sessionid={sessionid}; csrftoken={csrftoken}"})
        target_id = r2.json()['user']['pk']
        post(f"https://i.instagram.com/users/{target_id}/flag/",
             headers={
                 "User-Agent": "Mozilla/5.0",
                 "Host": "i.instagram.com",
                 "cookie": f"sessionid={sessionid}",
                 "X-CSRFToken": csrftoken,
                 "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
             },
             data=f'source_name=&reason_id={reportType}&frx_context=',
             allow_redirects=False)
        bot.send_message(chat_id, "✅ Single report submitted.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Failed: {str(e)}")

# ---------------- BULK REPORT ---------------- #
@bot.message_handler(commands=['bulkreport'])
def bulk_report_handler(message):
    chat_id = message.chat.id
    session = get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Login first!")
        return
    msg = bot.send_message(chat_id, "Send usernames line by line for bulk report:")
    bot.register_next_step_handler(msg, ask_bulk_report_type)

def ask_bulk_report_type(message):
    chat_id = message.chat.id
    text = message.text.strip()
    usernames = list(filter(None, text.splitlines()))
    if not usernames:
        bot.send_message(chat_id, "❌ No usernames provided.")
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for k, v in REPORT_OPTIONS.items():
        markup.add(types.KeyboardButton(f"{k} - {v}"))
    msg = bot.send_message(chat_id, "Choose report type for bulk report:", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: submit_bulk_report(chat_id, usernames, m.text, REPORT_OPTIONS))

def submit_bulk_report(chat_id, usernames, choice_text, options):
    try:
        reportType = int(choice_text.split(" - ")[0])
        if reportType not in options:
            raise ValueError("Invalid report type")
    except:
        bot.send_message(chat_id, "❌ Invalid choice.")
        return
    session = get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Session missing.")
        return
    sessionid = session['sessionid']
    csrftoken = session['csrftoken']
    bot.send_message(chat_id, f"🚀 Bulk reporting started for {len(usernames)} users.")
    for target in usernames:
        try:
            r2 = get(f"https://i.instagram.com/api/v1/users/{target}/usernameinfo/",
                     headers={"User-Agent": "Instagram 114.0.0.38.120 Android",
                              "Cookie": f"sessionid={sessionid}; csrftoken={csrftoken}"})
            target_id = r2.json()['user']['pk']
            post(f"https://i.instagram.com/users/{target_id}/flag/",
                 headers={
                     "User-Agent": "Mozilla/5.0",
                     "Host": "i.instagram.com",
                     "cookie": f"sessionid={sessionid}",
                     "X-CSRFToken": csrftoken,
                     "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                 },
                 data=f'source_name=&reason_id={reportType}&frx_context=',
                 allow_redirects=False)
            bot.send_message(chat_id, f"✅ Report sent for @{target}")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Failed @{target}: {str(e)}")
    bot.send_message(chat_id, "✅ Bulk report completed.")

def ping(update, context):
    # Calculate latency
    start_time = time.time()
    message = update.message.reply_text("⚡ Checking latency...")
    end_time = time.time()
    
    # Calculate milliseconds
    ms = round((end_time - start_time) * 1000, 2)
    
    ping_text = (
        "📶 *Bot Status*\n\n"
        "🚀 **Speed:** `{ms}ms`\n"
        "🛰️ **Server:** Global High-Speed\n\n"
        "⚡ *Developed by:* `daemonxrd`"
    ).format(ms=ms)
    
    message.edit_text(ping_text, parse_mode='Markdown')
    
# ---------------- START BOT ---------------- #
if __name__ == "__main__":
    bot.infinity_polling()
    