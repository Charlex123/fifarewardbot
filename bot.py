import os
from dotenv import load_dotenv
from prettytable import PrettyTable

load_dotenv()
import telebot
import sqlite3
import tempfile
import re
import csv
import requests
import signal
import time

BOT_TOKEN = os.getenv('BOT_TOKEN')

address_pattern = re.compile(r'^[a-zA-Z0-9]{30,}$')
email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# State management
user_states = {}
STATE_WAITING_FOR_EMAIL = 'waiting_for_email'
STATE_WAITING_FOR_WALLET = 'waiting_for_wallet'

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


# Function to create a new SQLite connection and cursor
def get_connection():
    conn = sqlite3.connect('referrals.db')
    return conn, conn.cursor()

# Create tables if not exists
def create_tables():
    conn, c = get_connection()
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
             (chat_id INTEGER PRIMARY KEY, referral_link TEXT, count INTEGER, upline_id INTEGER)''')
    # Ensure the upline_id column exists (SQLite does not support ALTER TABLE to add a column if it exists, so we need to check manually)
    c.execute("PRAGMA table_info(referrals)")
    columns = [column[1] for column in c.fetchall()]
    if 'upline_id' not in columns:
        c.execute("ALTER TABLE referrals ADD COLUMN upline_id INTEGER")
    c.execute('''CREATE TABLE IF NOT EXISTS bot_replies
                 (message_id INTEGER PRIMARY KEY, reply_text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bep20_addresses
                 (chat_id INTEGER PRIMARY KEY, bep20_address TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_address
                 (chat_id INTEGER PRIMARY KEY, email_address TEXT)''')
    conn.commit()
    conn.close()

# Clear the database
def clear_database():
    conn, c = get_connection()
    c.execute('DELETE FROM referrals')
    c.execute('DELETE FROM bot_replies')
    c.execute('DELETE FROM bep20_addresses')
    conn.commit()
    conn.close()

# Function to generate a CSV file from bep20_addresses table
def generate_bep20_csv():
    # Create a temporary file to store the CSV data
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv')
    temp_file_path = temp_file.name

    # Retrieve data from bep20_addresses table
    conn, c = get_connection()
    c.execute("SELECT chat_id, bep20_address FROM bep20_addresses")
    data = c.fetchall()
    conn.close()

    # Write data to the CSV file
    with open(temp_file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Chat ID', 'BEP20 Address'])
        writer.writerows(data)

    return temp_file_path

# Function to generate a CSV file from email_address table
def generate_email_csv():
    # Create a temporary file to store the CSV data
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv')
    temp_file_path = temp_file.name

    # Retrieve data from email_address table
    conn, c = get_connection()
    c.execute("SELECT chat_id, email_address FROM email_address")
    data = c.fetchall()
    conn.close()

    # Write data to the CSV file
    with open(temp_file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Chat ID', 'Email Address'])
        writer.writerows(data)

    return temp_file_path

@bot.message_handler(commands=['clear_data'])
def clear_data(message):
    print(f"User ID: {message.from_user.id}")  # Debug statement to log the user ID
    if message.from_user.id == 730149343:  # Replace with the actual Telegram account ID
        clear_database()
        bot.reply_to(message, "All data has been cleared.")
    else:
        bot.reply_to(message, "You do not have permission to use this command.")
        
# Handler to request wallet address
@bot.callback_query_handler(func=lambda call: call.data == 'Wallet')
def request_wallet_address(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = STATE_WAITING_FOR_WALLET
    msg = bot.send_message(chat_id, "Please send your BEP20 wallet address:")

# Process wallet address
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == STATE_WAITING_FOR_WALLET)
def process_wallet_address(message):
    chat_id = message.chat.id
    address = message.text
    if address_pattern.match(address):
        conn, c = get_connection()
        c.execute("INSERT INTO bep20_addresses (chat_id, bep20_address) VALUES (?, ?)", (chat_id, address))
        conn.commit()
        conn.close()
        generate_bep20_csv()
        bot.send_message(chat_id, "Your BEP20 address has been saved successfully.")
    else:
        bot.send_message(chat_id, "Invalid address format. Please send a valid BEP20 wallet address.")
    user_states.pop(chat_id, None)

# Handler to request email address
@bot.callback_query_handler(func=lambda call: call.data == 'Email')
def request_email_address(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = STATE_WAITING_FOR_EMAIL
    msg = bot.send_message(chat_id, "Please send your email address:")

# Process email address
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == STATE_WAITING_FOR_EMAIL)
def process_email_address(message):
    chat_id = message.chat.id
    email = message.text
    if email_pattern.match(email):
        conn, c = get_connection()
        c.execute("INSERT INTO email_address (chat_id, email_address) VALUES (?, ?)", (chat_id, email))
        conn.commit()
        conn.close()
        generate_email_csv()
        bot.send_message(chat_id, "Your email address has been saved successfully.")
    else:
        bot.send_message(chat_id, "Invalid email format. Please send a valid email address.")
    user_states.pop(chat_id, None)

@bot.message_handler(commands=['start','hello','help'])
def start_command(message):
    firstname = str(message.from_user.first_name)
    keyboard = telebot.types.InlineKeyboardMarkup()
    message_text = message.text
    message_array = message_text.split()
    chat_id = message.chat.id
    conn, c = get_connection()
    
    if len(message_array) > 1:
        upline_id = message_array[1]
        c.execute("SELECT * FROM referrals WHERE chat_id=?", (upline_id,))
        upline_data = c.fetchone()
        if upline_data:
            referral_link = f"https://t.me/{bot.get_me().username}?start={chat_id}"
            c.execute("INSERT INTO referrals (chat_id, referral_link, count, upline_id) VALUES (?, ?, ?, ?)", (chat_id, referral_link, 0, upline_id))
            conn.commit()
            c.execute("UPDATE referrals SET count = count + 1 WHERE chat_id=?", (upline_id,))
            conn.commit()
    
    c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
    data = c.fetchone()
    
    if not data:
        referral_link = f"https://t.me/{bot.get_me().username}?start={chat_id}"
        c.execute("INSERT INTO referrals (chat_id, referral_link, count) VALUES (?, ?, ?)", (chat_id, referral_link, 0))
        conn.commit()
        
        count = 0
        
        keyboard.add(
            telebot.types.InlineKeyboardButton('About Fifareward', callback_data='details')
        )
        
        text = str("Hello! " + firstname + "\n\n" +
        "Welcome!, I'm FRD Airdrop Bot, follow the instructions below to join FRD waiting list.\n\n"+
        f"Here is your referral link: {referral_link}.\n\n"+
        f"Your have *{count}* referrals. \n\n"+
        f"Keep sharing to earn a top spot in the aidrop waiting list"
        )
        bot.send_photo(
            message.chat.id,
            'https://www.fifareward.io/fifarewardlogo.png',
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
            
    else:
        referral_link = data[1]
        count = data[2]
        keyboard.add(
            telebot.types.InlineKeyboardButton('Check My Status', callback_data='status')
        )
        
        text = str("Hello! " + firstname + "\n\n" +
        " Welcome back\n"
        )
        bot.send_photo(
            message.chat.id,
            'https://www.fifareward.io/fifarewardlogo.png',
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )


@bot.message_handler(commands=['view_referrals'])
def view_referrals(message):
    chat_id = message.chat.id
    conn, c = get_connection()
    c.execute("SELECT chat_id FROM referrals WHERE upline_id=?", (chat_id,))
    downlines = c.fetchall()
    conn.close()

    if downlines:
        text = "Your referrals:\n\n"
        for downline in downlines:
            text += f"- {downline[0]}\n"
    else:
        text = "You don't have any referrals yet."

    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['view_all_referrals'])
def view_all_referrals(message):
    conn, c = get_connection()
    c.execute("SELECT chat_id, upline_id FROM referrals")
    all_referrals = c.fetchall()
    conn.close()

    if all_referrals:
        referrals_map = {}
        for referral in all_referrals:
            chat_id, upline_id = referral
            if upline_id not in referrals_map:
                referrals_map[upline_id] = []
            referrals_map[upline_id].append(chat_id)

        text = "All referrals:\n\n"
        for upline_id, downlines in referrals_map.items():
            downlines_text = ", ".join(str(downline) for downline in downlines)
            text += f"Upline {upline_id}:\n"
            text += f"```\n"
            text += f"{downlines_text}\n"
            text += f"```\n\n"
    else:
        text = "No referrals found."

    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# @bot.message_handler(commands=['download_csv'])
# def download_csv():
#     try:
#         # Create a temporary file to store the CSV data
#         temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv')
#         temp_file_path = temp_file.name

#         # Retrieve data from bep20_addresses table
#         conn, c = get_connection()
#         c.execute("SELECT chat_id, bep20_address FROM bep20_addresses")
#         data = c.fetchall()
#         conn.close()

#         # Write data to the CSV file
#         with open(temp_file_path, 'w', newline='') as file:
#             writer = csv.writer(file)
#             writer.writerow(['Chat ID', 'BEP20 Address'])
#             writer.writerows(data)

#         return temp_file_path
#     except Exception as e:
#         print(f"An error occurred while generating the CSV file: {e}")
#         return None

@bot.message_handler(commands=['download_csv'])
def download_csv(message):
    if message.from_user.id == 730149343:  # Replace with the actual Telegram account ID
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(
            telebot.types.InlineKeyboardButton('BEP20 Addresses', callback_data='download_bep20'),
            telebot.types.InlineKeyboardButton('Email Addresses', callback_data='download_email')
        )
        bot.send_message(message.chat.id, "Select which CSV file to download:", reply_markup=keyboard)
    else:
        bot.reply_to(message, "You do not have permission to use this command.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def handle_download_callback(call):
    csv_type = call.data.split('_')[1]
    if csv_type == 'bep20':
        file_path = generate_bep20_csv()
        if file_path:
            bot.send_document(call.message.chat.id, open(file_path, 'rb'))
            bot.answer_callback_query(call.id, "BEP20 address CSV file has been sent.")
        else:
            bot.answer_callback_query(call.id, "Failed to generate the BEP20 address CSV file.")
    elif csv_type == 'email':
        file_path = generate_email_csv()
        if file_path:
            bot.send_document(call.message.chat.id, open(file_path, 'rb'))
            bot.answer_callback_query(call.id, "Email address CSV file has been sent.")
        else:
            bot.answer_callback_query(call.id, "Failed to generate the email address CSV file.")


@bot.callback_query_handler(func=lambda call: True)
def iq_callback(call):
    data = call.data
    user_id = call.from_user.id
    keyboard = telebot.types.InlineKeyboardMarkup()
    
    if data == 'details':
        keyboard.add(
            telebot.types.InlineKeyboardButton('Join Airdrop Campaign', callback_data='joinairdrop')
        )
        text = str("Fifareward is a layer 2 blockchain on BSC network, it is the first decentralized AI revolutionary betting Dapp on the blockchain. \n\n" +
        "Utilities include: \n\n" +
        "1) Betting\n" +
        "2) Staking \n" +
        "3) Farming \n" + 
        "4) AI Powered Games\n" +
        "5) NFT Minting Engine And Market Place \n\n" +
        "==>) More in our road map \n\n" 
        )
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard
        )
    
    if data == 'joinairdrop':
        keyboard.add(
            telebot.types.InlineKeyboardButton("Have Completed Tasks", callback_data='Done')
        )
        discord = f"https://discord.com/invite/DC5Ta8bb"
        telegramgroup = f"https://t.me/FifarewardLabs"
        twitter = f"https://twitter.com/@FRD_Labs"
        metamask = f"https://metamask.io"
        trustwallet = f"https://trustwallet.com"
        
        text = f"To join the Fifareward airdrop campaign, you must do the following tasks. \n\n" + \
       "Join our;\n\n" + \
       f"1) <a href=\"{twitter}\">Twitter</a> \n" + \
       f"2) <a href=\"{discord}\">Discord</a> \n" + \
       f"3) <a href=\"{telegramgroup}\">Telegram</a> \n" + \
       f"4) Connect to our dapp using <a href=\"{trustwallet}\"> trust wallet </a> or <a href=\"{metamask}\"> metmask</a>, in your trust wallet app, enter https://www.fifareward.io in the browser address bar and connect to fifareward dapp. \n\n" + \
       "5) Like and retweet our tweets \n\n"
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    if data == 'Done':
        keyboard.add(
            telebot.types.InlineKeyboardButton("Enter Email Address", callback_data='Email'),
            telebot.types.InlineKeyboardButton("Enter Wallet Address", callback_data='Wallet'),
            telebot.types.InlineKeyboardButton("Next", callback_data='Continue')
        )
        text = str("Congratulations!, we will verify that you have completed all the tasks, please submit your wallet and email address for the waiting list. \n\n" + \
                   "To submit your email, type your email and click Enter Email Address button, do same for wallet address \n"
                   "Click on Continue after you've submitted your wallet and email addresses")
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    if data == 'status':
        conn, c = get_connection()
        chat_id = call.message.chat.id
        c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
        data = c.fetchone()
        conn.close()  # Ensure the connection is closed

        if data:
            count = data[2]
            referral_link = data[1]
            text = (
                f"You have *{count}* referrals. \n\n"
                f"Here is your referral link: {referral_link}.\n\n"
                f"Keep sharing to earn a top spot in FRD waiting list"
            )
            bot.send_chat_action(call.message.chat.id, 'typing')
            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="Markdown"  # Ensure proper Markdown parsing
            )
        else:
            bot.send_message(
                call.message.chat.id,
                "No referral data found for your account.",
                parse_mode="Markdown"
            )
        
    # if data == "Wallet":
    #     print("uiopa")
    #     bot.send_message(call.message.chat.id, "Please enter your BEP20 wallet address:")
    #     user_states[user_id] = STATE_WAITING_FOR_ADDRESS
    #     address = call.message.text
    #     if address_pattern.match(address):
    #         conn, c = get_connection()
    #         c.execute("INSERT INTO bep20_addresses (chat_id, bep20_address) VALUES (?, ?)", (user_id, address))
    #         conn.commit()
    #         conn.close()
            
    #         generate_bep20_csv()
    #         text = f"Hi! {call.message.from_user.first_name}\n\nYour BEP20 address is saved successfully. Please wait for our airdrop community distribution."
    #     else:
    #         text = "Please send only your BEP20 address, don't attach any other text or number to it."
    #     bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    #     del user_states[user_id]
            
    # if data == "Email":
    #     print("poiul")
    #     bot.send_message(call.message.chat.id, "Please enter your email address:")
    #     user_states[user_id] = STATE_WAITING_FOR_EMAIL
    #     print("oplyu",user_states[user_id])
    #     email = call.message.text
    #     print("joes",email)
    #     if user_states[user_id]:
    #         if email_pattern.match(email):
    #             conn, c = get_connection()
    #             c.execute("INSERT INTO email_address (chat_id, email_address) VALUES (?, ?)", (user_id, email))
    #             conn.commit()
    #             conn.close()
                
    #             generate_email_csv()
    #             text = f"Hi! {call.message.from_user.first_name}\n\nYour email address is saved successfully. Please wait for our airdrop community distribution."
    #         else:
    #             text = "Please send a valid email address."
    #         bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    #     del user_states[user_id]
        
    if data == "Continue":
        conn, c = get_connection()
        chat_id = call.message.chat.id
        
        c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
        data_ = c.fetchone()
        count = data_[2]
        referral_link = data_[1]
        text = (
            f"You have *{count}* referrals. \n\n"
            f"Here is your referral link: {referral_link}.\n\n"
            f"Keep sharing to earn a top spot in FRD waiting list"
        )
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="Markdown"  # Ensure proper Markdown parsing
        )
        conn.close()
        

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    conn, c = get_connection()
    keyboard = telebot.types.InlineKeyboardMarkup()
    chat_id = message.chat.id
    
    c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
    data = c.fetchone()
    
    if not data :
        text = str("Hi! " + message.from_user.first_name + "\n\n" +
                "You must join using someone's referral link to participate in Fifareward airdrop.")
        
        bot.send_photo(
            message.chat.id,
            'https://www.fifareward.io/fifarewardlogo.png',
            caption=text,
            parse_mode="Markdown"
        )
    else:
        count = data[2]
        referral_link = data[1]
        text = (
            f"You have *{count}* referrals. \n\n"
            f"Here is your referral link: {referral_link}.\n\n"
            f"Keep sharing to earn a top spot in FRD waiting list"
        )
        bot.send_chat_action(message.chat.id, 'typing')
        bot.send_message(
            message.chat.id,
            text,
            parse_mode="Markdown"  # Ensure proper Markdown parsing
        )
        
    conn.close()
    
# Handler for callback queries
# @bot.callback_query_handler(func=lambda call: call.data in ['Wallet', 'Email'])
# def handle_wallet_email_callback(call):
#     print("occured")
#     user_id = call.from_user.id
#     if call.data == 'Wallet':
#         bot.send_message(call.message.chat.id, "Please enter your BEP20 wallet address:")
#         user_states[user_id] = STATE_WAITING_FOR_ADDRESS
#     elif call.data == 'Email':
#         bot.send_message(call.message.chat.id, "Please enter your email address:")
#         user_states[user_id] = STATE_WAITING_FOR_EMAIL
#     bot.answer_callback_query(call.id, "Please enter your information.")
            
# Handler for text messages to capture user input
# @bot.message_handler(func=lambda message: message.from_user.id in user_states)
# def handle_user_input(message):
#     print("occureed too")
#     user_id = message.from_user.id
#     state = user_states.get(user_id)

#     if state == STATE_WAITING_FOR_ADDRESS:
#         address = message.text
#         if address_pattern.match(address):
#             conn, c = get_connection()
#             c.execute("INSERT INTO bep20_addresses (chat_id, bep20_address) VALUES (?, ?)", (user_id, address))
#             conn.commit()
#             conn.close()
            
#             generate_bep20_csv()
#             text = f"Hi! {message.from_user.first_name}\n\nYour BEP20 address is saved successfully. Please wait for our airdrop community distribution."
#         else:
#             text = "Please send only your BEP20 address, don't attach any other text or number to it."

#     elif state == STATE_WAITING_FOR_EMAIL:
#         email = message.text
#         if email_pattern.match(email):
#             conn, c = get_connection()
#             c.execute("INSERT INTO email_address (chat_id, email_address) VALUES (?, ?)", (user_id, email))
#             conn.commit()
#             conn.close()
            
#             generate_email_csv()
#             text = f"Hi! {message.from_user.first_name}\n\nYour email address is saved successfully. Please wait for our airdrop community distribution."
#         else:
#             text = "Please send a valid email address."

#     bot.send_message(message.chat.id, text, parse_mode="Markdown")
#     del user_states[user_id]

# Create the table if not exists
create_tables()

def run_bot():
    def handle_shutdown(signum, frame):
        print(f"Signal {signum} received, shutting down...")
        bot.stop_polling()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except requests.exceptions.ReadTimeout:
        print("Read timeout occurred. Retrying in 15 seconds...")
        time.sleep(15)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        time.sleep(15)

run_bot()
