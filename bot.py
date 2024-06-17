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
STATE_WAITING_FOR_TWITTERUSERNAME = 'waiting_for_twitterusername'

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


# Function to create a new SQLite connection and cursor
def get_connection():
    conn = sqlite3.connect('referrals.db')
    return conn, conn.cursor()

# Create tables if not exists
def create_tables():
    conn, c = get_connection()
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
             (chat_id INTEGER PRIMARY KEY, referral_link TEXT, count INTEGER, upline_id INTEGER, username TEXT)''')
    # Ensure the upline_id column exists (SQLite does not support ALTER TABLE to add a column if it exists, so we need to check manually)
    c.execute("PRAGMA table_info(referrals)")
    columns = [column[1] for column in c.fetchall()]
    if 'upline_id' not in columns:
        c.execute("ALTER TABLE referrals ADD COLUMN upline_id INTEGER")
    if 'username' not in columns:
        c.execute("ALTER TABLE referrals ADD COLUMN username INTEGER")
    c.execute('''CREATE TABLE IF NOT EXISTS bot_replies
                 (message_id INTEGER PRIMARY KEY, reply_text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bep20_addresses
                 (chat_id INTEGER PRIMARY KEY, bep20_address TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_address
                 (chat_id INTEGER PRIMARY KEY, email_address TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS twitterusernames
              (chat_id INTEGER PRIMARY KEY, twitter_username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS telegramusernames
              (chat_id INTEGER PRIMARY KEY, telegram_username TEXT)''')
    conn.commit()
    conn.close()

# Clear the database
def clear_database():
    conn, c = get_connection()
    c.execute('DELETE FROM email_address')
    print(f"Deleted {c.rowcount} records from email_address")
    c.execute('DELETE FROM referrals')
    print(f"Deleted {c.rowcount} records from referrals")
    c.execute('DELETE FROM bep20_addresses')
    print(f"Deleted {c.rowcount} records from bep20_addresses")
    c.execute('DELETE FROM telegramusernames')
    print(f"Deleted {c.rowcount} records from telegramusernames")
    c.execute('DELETE FROM twitterusernames')
    print(f"Deleted {c.rowcount} records from twitterusernames")
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

# Function to generate a CSV file from referrals table
def generate_referrals_csv():
    # Create a temporary file to store the CSV data
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv')
    temp_file_path = temp_file.name

    # Retrieve data from referrals table
    conn, c = get_connection()
    c.execute("SELECT chat_id, referral_link, count, upline_id, username FROM referrals")
    data = c.fetchall()
    conn.close()

    # Write data to the CSV file
    with open(temp_file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Chat ID', 'Referral Link', 'Count', 'Upline ID', 'Username'])
        writer.writerows(data)

    return temp_file_path

# Function to generate a CSV file from twitterusername table
def generate_twitterusernames_csv():
    try:
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv')
        temp_file_path = temp_file.name
        temp_file.close()

        conn, c = get_connection()
        c.execute("SELECT chat_id, twitter_username FROM twitterusernames")
        data = c.fetchall()
        conn.close()

        with open(temp_file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Chat ID', 'Twitter Username'])
            writer.writerows(data)

        with open(temp_file_path, 'r') as file:
            content = file.read()
            print("Generated CSV content (Twitter Username):\n", content)

        return temp_file_path

    except Exception as e:
        print(f"An error occurred while generating the CSV file: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return None

# Function to generate a CSV file from telegramusername table
def generate_telegramusernames_csv():
    try:
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix='.csv')
        temp_file_path = temp_file.name
        temp_file.close()

        conn, c = get_connection()
        c.execute("SELECT chat_id, telegram_username FROM telegramusernames")
        data = c.fetchall()
        conn.close()

        with open(temp_file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Chat ID', 'Telegram Username'])
            writer.writerows(data)

        with open(temp_file_path, 'r') as file:
            content = file.read()
            print("Generated CSV content (Telegram Username):\n", content)

        return temp_file_path

    except Exception as e:
        print(f"An error occurred while generating the CSV file: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return None

# Retry decorator to handle database locking
def retry_on_lock(func):
    def wrapper(*args, **kwargs):
        retries = 5
        delay = 1
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    time.sleep(delay)
                else:
                    raise
        raise Exception('Maximum retry attempts reached')
    return wrapper

@retry_on_lock
def insert_bep20_address(chat_id, address):
    conn, c = get_connection()
    c.execute("INSERT INTO bep20_addresses (chat_id, bep20_address) VALUES (?, ?)", (chat_id, address))
    conn.commit()
    conn.close()

@retry_on_lock
def insert_email_address(chat_id, email):
    conn, c = get_connection()
    c.execute("INSERT INTO email_address (chat_id, email_address) VALUES (?, ?)", (chat_id, email))
    conn.commit()
    conn.close()

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
        c.execute("SELECT bep20_address FROM bep20_addresses WHERE chat_id = ?", (chat_id,))
        waddress = c.fetchone()
        conn.close()
        if waddress is not None:
            bot.send_message(chat_id, "BEP20 address already exists.")
        else:
            insert_bep20_address(chat_id, address)
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
        c.execute("SELECT email_address FROM email_address WHERE chat_id = ?", (chat_id,))
        emailaddress = c.fetchone()
        conn.close()
        if emailaddress is not None:
            bot.send_message(chat_id, "Email address already added.")
        else:
            insert_email_address(chat_id, email)
            generate_email_csv()
            bot.send_message(chat_id, "Your email address has been saved successfully.")
    else:
        bot.send_message(chat_id, "Invalid email format. Please send a valid email address.")
    user_states.pop(chat_id, None)

# Handler to request twitter username
@bot.callback_query_handler(func=lambda call: call.data == 'TwitterUsername')
def request_twitter_username(call):
    chat_id = call.message.chat.id
    user_states[chat_id] = STATE_WAITING_FOR_TWITTERUSERNAME
    msg = bot.send_message(chat_id, "Please send your verified Twitter username e.g @username:")

# Process twitter username
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == STATE_WAITING_FOR_TWITTERUSERNAME)
def process_twitter_username(message):
    chat_id = message.chat.id
    twitter_username = message.text
    conn, c = get_connection()
    c.execute("SELECT chat_id FROM twitterusernames WHERE chat_id = ?", (chat_id,))
    uinfo = c.fetchone()
    if uinfo is not None: 
        c.execute("SELECT twitter_username FROM twitterusernames WHERE chat_id = ?", (chat_id,))
        twt_uname = c.fetchone()
        if twt_uname is not None:
            bot.send_message(chat_id, "Twitter username already added.")
            user_states.pop(chat_id, None)
        else:
            c.execute("INSERT INTO twitterusernames (chat_id, twitter_username) VALUES (?, ?)", (chat_id, twitter_username))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, "Your verified Twitter username has been saved successfully.")
            user_states.pop(chat_id, None)
    else:
        c.execute("INSERT INTO twitterusernames (chat_id, twitter_username) VALUES (?, ?)", (chat_id, twitter_username))
        conn.commit()
        conn.close()
        bot.send_message(chat_id, "Your verified Twitter username has been saved successfully.")
        user_states.pop(chat_id, None)
        
# Handler to request email address
@bot.callback_query_handler(func=lambda call: call.data == 'MyReferrals')
def request_email_address(call):
    chat_id = call.message.chat.id
    conn, c = get_connection()
    c.execute("SELECT chat_id, username FROM referrals WHERE upline_id=? AND chat_id != ?", (chat_id, chat_id))
    downlines = c.fetchall()
    conn.close()

    if downlines:
        text = "Your referrals:\n\n"
        for downline in downlines:
            text += f"- Chat ID: {downline[0]}, Username: {downline[1] if downline[1] else 'N/A'}\n"
    else:
        text = "You don't have any referrals yet."

    bot.send_message(chat_id, text, parse_mode="Markdown")
        
@bot.message_handler(commands=['download_csv'])
def send_csv_options(message):
    chat_id = message.chat.id
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Download BEP20 Addresses CSV", callback_data="download_bep20_csv"))
    markup.add(telebot.types.InlineKeyboardButton("Download Email Addresses CSV", callback_data="download_email_csv"))
    markup.add(telebot.types.InlineKeyboardButton("Download Referrals CSV", callback_data="download_referrals_csv"))
    markup.add(telebot.types.InlineKeyboardButton("Download Twitter Usernames", callback_data="download_twitterusernames_csv"))
    markup.add(telebot.types.InlineKeyboardButton("Download Telegram Usernames", callback_data="download_telegramusernames_csv"))
    bot.send_message(chat_id, "Please select the CSV file you want to download:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def handle_download_csv(call):
    chat_id = call.message.chat.id
    file_type = call.data.split('_')[1]
    
    if file_type == "bep20":
        file_path = generate_bep20_csv()
        file_name = "bep20_addresses.csv"
    elif file_type == "email":
        file_path = generate_email_csv()
        file_name = "email_addresses.csv"
    elif file_type == "referrals":
        file_path = generate_referrals_csv()
        file_name = "referrals.csv"
    elif file_type == "twitterusernames":
        file_path = generate_twitterusernames_csv()
        file_name = "twitterusernames.csv"
    elif file_type == "telegramusernames":
        file_path = generate_telegramusernames_csv()
        file_name = "telegramusernames.csv"
    else:
        bot.send_message(chat_id, "Invalid file type.")
        return
    
    with open(file_path, 'rb') as file:
        bot.send_document(chat_id, file, caption=f"{file_name}")
    
    os.remove(file_path)  # Clean up the temporary file
    
@bot.message_handler(commands=['clear_data'])
def clear_data(message):
    print(f"User ID: {message.from_user.id}")  # Debug statement to log the user ID
    if message.from_user.id == 730149343:  # Replace with the actual Telegram account ID
        clear_database()
        bot.reply_to(message, "All data has been cleared.")
    else:
        bot.reply_to(message, "You do not have permission to use this command.")

@bot.message_handler(commands=['start', 'hello', 'help'])
def start_command(message):
    firstname = str(message.from_user.first_name)
    keyboard = telebot.types.InlineKeyboardMarkup()
    message_text = message.text
    username = message.from_user.username  # Get the username
    message_array = message_text.split()
    chat_id = message.chat.id
    conn, c = get_connection()
    print("mesg text",message_text)
    print("msg arr",message_array)
    print("msg arr",len(message_array))
    if len(message_array) > 1:
        upline_id = message_array[1]
        print("uplin id",upline_id)
        c.execute("SELECT * FROM referrals WHERE chat_id=?", (upline_id,))
        upline_data = c.fetchone()
        print("upl data",upline_data)
        if upline_data:
            referral_link = f"https://t.me/{bot.get_me().username}?start={chat_id}"
            # Check if the chat_id already exists
            c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
            data = c.fetchone()
            if not data:
                c.execute("SELECT chat_id FROM telegramusernames WHERE chat_id = ?", (chat_id,))
                uinfo = c.fetchone()
                if uinfo is not None: 
                    c.execute("SELECT telegram_username FROM telegramusernames WHERE chat_id = ?", (chat_id,))
                    twt_uname = c.fetchone()
                    if twt_uname is None:
                        c.execute("INSERT INTO telegramusernames (chat_id, telegram_username) VALUES (?, ?)", (chat_id, username))
                        conn.commit()
                else:
                    c.execute("INSERT INTO telegramusernames (chat_id, telegram_username) VALUES (?, ?)", (chat_id, username))
                    conn.commit()
                    
                c.execute("INSERT INTO referrals (chat_id, referral_link, count, upline_id, username) VALUES (?, ?, ?, ?, ?)",
                          (chat_id, referral_link, 0, upline_id, username))
                conn.commit()
                c.execute("UPDATE referrals SET count = count + 1 WHERE chat_id=?", (upline_id,))
                conn.commit()
                
                c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
                userdata = c.fetchone()
                if userdata is not None:
                    count = userdata[2]  # Assuming the count column is at index 2 in the tuple
                    # Use the count value as needed
                else:
                    count = 0
                    
                keyboard.add(
                    telebot.types.InlineKeyboardButton('About Fifareward', callback_data='details')
                )
                text = str("Hello! " + firstname + "\n\n" +
                        "Welcome!, I'm FRD Airdrop Bot, follow the instructions below to join FRD waiting list.\n\n" +
                        f"Here is your referral link: {referral_link}.\n\n" +
                        f"Your have *{count}* referrals. \n\n" +
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
                # If the chat_id exists, update the existing record
                c.execute("UPDATE referrals SET referral_link = ?, upline_id = ? WHERE chat_id = ?",
                          (referral_link, upline_id, chat_id))
                conn.commit()
                keyboard.add(
                    telebot.types.InlineKeyboardButton('Check My Status', callback_data='status')
                )

                text = str("Hello! " + firstname + "\n\n" +
                        "Welcome back\n"
                        )
                bot.send_photo(
                    message.chat.id,
                    'https://www.fifareward.io/fifarewardlogo.png',
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )

        else:
            referral_link = f"https://t.me/{bot.get_me().username}?start={chat_id}"
            # Check if the chat_id already exists
            c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
            data = c.fetchone()
            
            if not data:
                c.execute("INSERT INTO referrals (chat_id, referral_link, count, upline_id, username) VALUES (?, ?, ?, ?, ?)",
                          (chat_id, referral_link, 0, upline_id, username))
                conn.commit()
                c.execute("UPDATE referrals SET count = count + 1 WHERE chat_id=?", (upline_id,))
                conn.commit()
                c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
                userdata = c.fetchone()
                
                if userdata is not None:
                    count = userdata[2]  # Assuming the count column is at index 2 in the tuple
                    # Use the count value as needed
                else:
                    count = 0
                    
                keyboard.add(
                    telebot.types.InlineKeyboardButton('About Fifareward', callback_data='details')
                )
                text = str("Hello! " + firstname + "\n\n" +
                        "Welcome!, I'm FRD Airdrop Bot, follow the instructions below to join FRD waiting list.\n\n" +
                        f"Here is your referral link: {referral_link}.\n\n" +
                        f"Your have *{count}* referrals. \n\n" +
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
                # If the chat_id exists, update the existing record
                c.execute("UPDATE referrals SET referral_link = ?, upline_id = ? WHERE chat_id = ?",
                          (referral_link, upline_id, chat_id))
                conn.commit()
                keyboard.add(
                    telebot.types.InlineKeyboardButton('Check My Status', callback_data='status')
                )

                text = str("Hello! " + firstname + "\n\n" +
                        "Welcome back\n"
                        )
                bot.send_photo(
                    message.chat.id,
                    'https://www.fifareward.io/fifarewardlogo.png',
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
    else:
        text = str("Hi! " + message.from_user.first_name + "\n\n" +
                "You must join using someone's referral link to participate in Fifareward airdrop.")
        
        bot.send_photo(
            message.chat.id,
            'https://www.fifareward.io/fifarewardlogo.png',
            caption=text,
            parse_mode="Markdown"
        )
                

@bot.message_handler(commands=['view_referrals'])
def view_referrals(message):
    chat_id = message.chat.id
    conn, c = get_connection()
    c.execute("SELECT chat_id, username FROM referrals WHERE upline_id=? AND chat_id != ?", (chat_id, chat_id))
    downlines = c.fetchall()
    conn.close()

    if downlines:
        text = "Your referrals:\n\n"
        for downline in downlines:
            text += f"- Chat ID: {downline[0]}, Username: {downline[1] if downline[1] else 'N/A'}\n"
    else:
        text = "You don't have any referrals yet."

    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['view_all_referrals'])
def view_all_referrals(message):
    conn, c = get_connection()
    c.execute("SELECT chat_id, upline_id, username FROM referrals")
    all_referrals = c.fetchall()
    conn.close()

    if all_referrals:
        referrals_map = {}
        for referral in all_referrals:
            chat_id, upline_id, username = referral
            if upline_id not in referrals_map:
                referrals_map[upline_id] = []
            referrals_map[upline_id].append((chat_id, username))

        text = "All referrals:\n\n"
        for upline_id, downlines in referrals_map.items():
            downlines_text = ", ".join(f"{downline[0]} ({downline[1] if downline[1] else 'N/A'})" for downline in downlines)
            text += f"Upline {upline_id}:\n"
            text += f"```\n"
            text += f"{downlines_text}\n"
            text += f"```\n\n"
    else:
        text = "No referrals found."

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

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
        "1) Soccer Betting\n" +
        "2) Staking Protocol\n" +
        "3) Farming Protocol\n" + 
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
        
        text = f"To join the Fifareward airdrop waiting list, you must do the following tasks. \n\n" + \
       "Join our;\n\n" + \
       f"1) <a href=\"{twitter}\">Twitter</a> \n" + \
       f"2) <a href=\"{discord}\">Discord</a> \n" + \
       f"3) <a href=\"{telegramgroup}\">Telegram</a> \n" + \
       f"4) Connect to our dapp using <a href=\"https://link.trustwallet.com/open_url?&url=https://www.fifareward.io\"> trust wallet </a> or <a href=\"https://metamask.app.link/dapp/www.fifareward.io\"> metmask</a>, in your wallet, enter https://www.fifareward.io in the browser address bar and connect to fifareward dapp. \n\n" + \
       "5) Like and retweet our tweets \n\n"
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    if data == 'BackToTasks':
        keyboard.add(
            telebot.types.InlineKeyboardButton("Have Completed Tasks", callback_data='Done')
        )
        discord = f"https://discord.com/invite/DC5Ta8bb"
        telegramgroup = f"https://t.me/FifarewardLabs"
        twitter = f"https://twitter.com/@FRD_Labs"
        
        text = f"To join the Fifareward airdrop waiting list, you must do the following tasks. \n\n" + \
       "Join our;\n\n" + \
       f"1) <a href=\"{twitter}\">Twitter</a> \n" + \
       f"2) <a href=\"{discord}\">Discord</a> \n" + \
       f"3) <a href=\"{telegramgroup}\">Telegram</a> \n" + \
       f"4) Connect to our dapp using <a href=\"https://link.trustwallet.com/open_url?&url=https://www.fifareward.io\"> trust wallet </a> or <a href=\"https://metamask.app.link/dapp/www.fifareward.io\"> metmask</a>, in your wallet, enter https://www.fifareward.io in the browser address bar and connect to fifareward dapp. \n\n" + \
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
            telebot.types.InlineKeyboardButton("Submit Email Address", callback_data='Email'),
            telebot.types.InlineKeyboardButton("Submit Wallet Address", callback_data='Wallet')
        )
        keyboard.add(
            telebot.types.InlineKeyboardButton("Submit Twitter Username", callback_data='TwitterUsername')
        )
        keyboard.add(
            telebot.types.InlineKeyboardButton("Have Submitted All Details", callback_data='Continue')
        )
        text = str("Congratulations!, we will verify that you have completed all the tasks, please submit your wallet address, verified twitter username and email address for the waiting list. \n\n")
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
        print("chat id--",chat_id)
        c.execute("SELECT * FROM referrals WHERE chat_id =?", (chat_id,))
        data = c.fetchone()
        print("data o",data)
        if data is not None:
            # c.execute("SELECT * FROM referrals WHERE upline_id=?", (chat_id,))
            # data_ = c.fetchone()
            # print("pop",data_)
            # conn.close()  # Ensure the connection is closed
            count = data[2]
            referral_link = data[1]
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(telebot.types.InlineKeyboardButton("Back To Tasks", callback_data='BackToTasks'))
            text = (
                f"You have *{count}* referrals. \n\n"
                f"Here is your referral link: {referral_link}.\n\n"
                f"Keep sharing to earn a top spot in FRD waiting list"
            )
            bot.send_chat_action(call.message.chat.id, 'typing')
            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=keyboard,
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
        
        keyboard.add(
            telebot.types.InlineKeyboardButton("My Referrals", callback_data='MyReferrals'),
            telebot.types.InlineKeyboardButton("Back To Tasks", callback_data='BackToTasks')
        )
        
        
        c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
        data = c.fetchone()
        if data is not None:
            # c.execute("SELECT * FROM referrals WHERE upline_id=? AND chat_id != upline_id", (chat_id,))
            # data_ = c.fetchone()
            # if data_ is not None:
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
                reply_markup=keyboard,
                parse_mode="Markdown"  # Ensure proper Markdown parsing
            )
            
        conn.close()
        

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    conn, c = get_connection()
    chat_id = message.chat.id
    
    c.execute("SELECT * FROM referrals WHERE chat_d=?", (chat_id,))
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
