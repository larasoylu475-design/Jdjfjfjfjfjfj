import asyncio
from telethon import TelegramClient, events

# --- CONFIGURATION AREA ---
# These are your unique credentials from my.telegram.org
# നിങ്ങളുടെ ടെലിഗ്രാം ആപ്പ് ഐഡിയും ഹാഷും ഇവിടെ നൽകുന്നു
API_ID = 29847762
API_HASH = '48b2038a55e0156c769cec3e97c2cd1b'

# Only messages from this ID will be accepted by the bots
# ഈ ഐഡിയിൽ നിന്നുള്ള കമാൻഡുകൾ മാത്രമേ ബോട്ടുകൾ സ്വീകരിക്കൂ
ADMIN_ID = 8367985723 

# List of 8 bot tokens provided by you
# നിങ്ങൾ നൽകിയ 8 ബോട്ട് ടോക്കണുകളുടെ ലിസ്റ്റ്
BOT_TOKENS = [
    '8508015982:AAHeIplriFINptflZEg5SCwh5NnCQdwHWuw',
    '7982676092:AAF_a8LX7njgDBEDE2wBBruIPz9XsYG0BQI',
    '8480245440:AAHe-8C52OZKw_DMZbK5Xvw7NRyDS_4_0uk',
    '8597934611:AAGKFmRz2O1FxGqy_yiadSTOTWgUSevOtpk',
    '8584855639:AAHrfSDNLAL-HBkT57Fs781W2chVanKAgMQ',
    '8016443048:AAHeuJsTlXcdTE7dCQ6L8FWiGQZqX1VIvyk',
    '8002755632:AAGutCfFKusHZ2cSrvJEzhu0_h66opmhAbw',
    '8571998153:AAGe1OaaPwzP8kb3cubKErLUCUociWiJ_es'
]

clients = []  # List to store all active bot connections / ബോട്ടുകളെ സേവ് ചെയ്യാനുള്ള ലിസ്റ്റ്
is_attacking = False # State to check if attack is running / അറ്റാക്ക് നടക്കുന്നുണ്ടോ എന്ന് നോക്കാനുള്ള വേരിയബിൾ

# Function to start all bots simultaneously
# എല്ലാ ബോട്ടുകളെയും ഒരേസമയം പ്രവർത്തിപ്പിക്കാനുള്ള ഫംഗ്ഷൻ
async def start_all_bots():
    print("🚀 Starting bots, please wait...")
    for i, token in enumerate(BOT_TOKENS):
        try:
            # Create a separate session file for each bot
            # ഓരോ ബോട്ടിനും പ്രത്യേക സെഷൻ ഫയലുകൾ ഉണ്ടാക്കുന്നു
            client = TelegramClient(f'bot_session_{i}', API_ID, API_HASH)
            await client.start(bot_token=token)
            clients.append(client)
            print(f"✅ Bot {i+1} is online!")
        except Exception as e:
            print(f"❌ Error starting bot {i+1}: {e}")

# The continuous loop that sends the messages
# നിർത്താതെ മെസ്സേജുകൾ അയച്ചുകൊണ്ടിരിക്കുന്ന ലൂപ്പ്
async def run_attack(event, target, message):
    global is_attacking
    while is_attacking:
        tasks = []
        for client in clients:
            # Sending message from each bot to the same chat
            # ഓരോ ബോട്ടും ആ ചാറ്റിലേക്ക് മെസ്സേജ് അയക്കുന്നു
            tasks.append(client.send_message(event.chat_id, f"{target} {message}"))
        
        # Execute all send tasks at the same time
        await asyncio.gather(*tasks)
        # 0.4 second delay to avoid getting banned by Telegram
        # ടെലിഗ്രാം ബാൻ ചെയ്യാതിരിക്കാൻ 0.4 സെക്കൻഡ് ഗ്യാപ്പ് നൽകുന്നു
        await asyncio.sleep(0.4) 

# Trigger for the /attack command
# /attack കമാൻഡ് വരുമ്പോൾ പ്രവർത്തിക്കുന്ന ഭാഗം
@events.register(events.NewMessage(pattern=r'/attack (\S+) (.+)'))
async def attack_handler(event):
    global is_attacking
    # Verify if the sender is the authorized Admin
    # അയക്കുന്ന ആൾ നിങ്ങൾ തന്നെയാണോ എന്ന് ഉറപ്പുവരുത്തുന്നു
    if event.sender_id != ADMIN_ID:
        return 

    # Extract target username and custom message from the command
    # കമാൻഡിൽ നിന്നും യൂസർ നെയിമും മെസ്സേജും വേർതിരിച്ചെടുക്കുന്നു
    target = event.pattern_match.group(1)
    message = event.pattern_match.group(2)

    if not is_attacking:
        is_attacking = True
        await event.reply(f"🔥 **Attack initiated on {target}!**")
        # Starts the attack loop in the background
        # അറ്റാക്ക് ലൂപ്പ് ബാക്ഗ്രൗണ്ടിൽ സ്റ്റാർട്ട് ചെയ്യുന്നു
        asyncio.create_task(run_attack(event, target, message))

# Trigger for the /stop command
# അറ്റാക്ക് നിർത്താനുള്ള കമാൻഡ്
@events.register(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    global is_attacking
    if event.sender_id == ADMIN_ID:
        is_attacking = False # Sets the loop state to False to stop it
        await event.reply("🛑 **Attack stopped successfully!**")

# Main function to run the script
async def main():
    await start_all_bots()
    # Adding command listeners to every bot
    for client in clients:
        client.add_event_handler(attack_handler)
        client.add_event_handler(stop_handler)
    
    print("\n⚡ All bots are running. Use /attack to start!")
    # Keep the script running forever
    await asyncio.gather(*[client.run_until_disconnected() for client in clients])

if __name__ == '__main__':
    # Start the event loop
    asyncio.run(main())
    