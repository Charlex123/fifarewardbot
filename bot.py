import os
from dotenv import load_dotenv

load_dotenv()
import telebot
import sqlite3
import threading
import tempfile
import re
import csv
import requests

BOT_TOKEN = os.getenv('BOT_TOKEN')

address_pattern = re.compile(r'^[a-zA-Z0-9]{30,}$')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# Function to create a new SQLite connection and cursor
def get_connection():
    conn = sqlite3.connect('referrals.db')
    return conn, conn.cursor()

# Create tables if not exists
def create_tables():
    conn, c = get_connection()
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (chat_id INTEGER PRIMARY KEY, referral_link TEXT, count INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_replies
                 (message_id INTEGER PRIMARY KEY, reply_text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bep20_addresses
                 (chat_id INTEGER PRIMARY KEY, bep20_address TEXT)''')
    conn.commit()
    conn.close()


# Function to generate a CSV file from bep20_addresses table
def generate_csv():
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

@bot.message_handler(commands=['start','hello','help'])
def start_command(message):
    
    firstname = str(message.from_user.first_name)
    keyboard = telebot.types.InlineKeyboardMarkup()
    # Given string
    message_text = message.text
    
    # Splitting the string into an array
    message_array = message_text.split()

    # Get the user's chat ID
    chat_id = message.chat.id
    # Create a new connection and cursor
    conn, c = get_connection()
    
    # Check if the user already has a referral link
    c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
    data = c.fetchone()
    
    if not data:
        # Generate a unique referral link using the user's Telegram ID
        referral_link = f"https://t.me/{bot.get_me().username}?start={chat_id}"
        # Store the referral link and initialize count as 0
        c.execute("INSERT INTO referrals (chat_id, referral_link, count) VALUES (?, ?, ?)", (chat_id, referral_link, 0))
        conn.commit()
        
        if len(message_array) > 1 :
            command = message_array[0]
            chat_id_ = message_array[1]
            # Increase the count for the referral link associated with the referrer
            c.execute("UPDATE referrals SET count = count + 1 WHERE chat_id=?", (chat_id_,))
            conn.commit()
        
        count = 0
        
        keyboard.add(
            telebot.types.InlineKeyboardButton('About Fifareward', callback_data='details')
        )
        
        text = str("Hello! " + firstname + "\n\n" +
        " Welcome!, I'm FRD Airdrop Bot, I can help you accumulate FRD tokens if you obey my instructions.\n\n"+
        f"Here is your referral link: {referral_link}.\n\n"+
        f"Your have *{count}* referrals. \n\n"+
        f"Keep sharing to partake in the FifaReward *10%* Airdrop distribution to the community"
        )
        bot.send_photo(
            message.chat.id,
            'https://www.fifareward.io/fifarewardlogo.png',
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
            
    else:
        # Get the existing referral link for the user
        referral_link = data[1]
    
        # Get the count for the user's referral link
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
    
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    conn, c = get_connection()
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    chat_id = message.chat.id
    
    # Check if the user already has a referral link
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
    else :
        if address_pattern.match(message.text):
            # Store the message ID and content of the reply in the table
            c.execute("INSERT INTO bep20_addresses (chat_id, bep20_address) VALUES (?, ?)", (message.message_id, message.text))
            conn.commit()
            
            # Save the user's chat ID and BEP20 address to a CSV file
            generate_csv()
            
            text = str("Hi! " + message.from_user.first_name + "\n\n" +
                    "Your bep20 address is saved successfully, patiently wait for our airdrop community distribution.")
            
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="Markdown"
            )
        else : 
            text = str("please send only your bep20 address, don't attach any other text or number to it")
        
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="Markdown"
            )
            # c.execute("SELECT reply_text FROM bot_replies ORDER BY message_id ")
            # result = c.fetchall()
            
            # print('result',result)
            # keyboard.add(
            # telebot.types.InlineKeyboardButton("Yes", callback_data='yes'),  # Fix the URL parameter
            #     telebot.types.InlineKeyboardButton("No", callback_data='no')
            # )
            # text = "Hi! " + message.from_user.first_name + " welcome back \n\n" +\
            # f"Your referral link: {data[1]}.\n\n" + \
            # f"Your have *{data[2]}* referrals. \n\n" + \
            # f"Keep sharing to earn more airdrop in the FifaReward *10%* Airdrop distribution to the community \n\n" + \
            # "Have you submitted your bep20 wallet address ?"
            
            # bot.send_photo(
            #     message.chat.id,
            #     'https://www.fifareward.io/fifarewardlogo.png',
            #     caption=text,
            #     reply_markup=keyboard,
            #     parse_mode="Markdown"
            # )
    
    # Close the connection
    conn.close()
    
@bot.callback_query_handler(func=lambda call: True)
def iq_callback(call):
    data = call.data
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
            telebot.types.InlineKeyboardButton("Have Completed Tasks", callback_data='Done')  # Fix the URL parameter
        )
        discord = f"https://discord.com/invite/DC5Ta8bb"
        telegramgroup = f"https://t.me/FifarewardLabs"
        twitter = f"https://twitter.com/@FRD_Labs"
        website = f"https://www.fifareward.io"
        mintnft = f"https://www.fifareward.io/nft/"
        
        text = f"To join the Fifareward airdrop campaign, you must do the following tasks. \n\n" + \
       "Join our;\n\n" + \
       f"1) <a href=\"{discord}\">Discord</a> \n" + \
       f"2) <a href=\"{telegramgroup}\">Telegram</a> \n" + \
       f"3) <a href=\"{twitter}\">Twitter handle</a> \n" + \
       f"4) <a href=\"{website}\">Register</a> in our website \n" + \
        f"5) <a href=\"{website}\">Mint NFT</a> in our website \n" + \
       "6) Like and retweet our tweets \n\n"
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    if data == 'Done':
        text = str("Congratulations on completing the tasks, you will be added to our FRD tokens airdrop list. \n\n" +
        "Send you bep20 wallet address to me;\n\n")
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text
        )   
        
    if data == 'continue':
        text = str("Congratulations on completing the tasks, you will be added to our FRD tokens airdrop list. \n\n" +
        "Send your bep20 wallet address to me;\n\n")
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text
        ) 
    
    if data == 'status':
        
        conn, c = get_connection()
        chat_id = call.message.chat.id
        # Check if the user already has a referral link
        c.execute("SELECT * FROM referrals WHERE chat_id=?", (chat_id,))
        data = c.fetchone()
        keyboard.add(
            telebot.types.InlineKeyboardButton("Yes", callback_data='yes'),  # Fix the URL parameter
            telebot.types.InlineKeyboardButton("No", callback_data='no')
        )
        text = f"Your referral link: {data[1]}.\n\n" + \
        f"Your have *{data[2]}* referrals. \n\n" + \
        f"Keep sharing to earn more airdrop in the FifaReward *10%* Airdrop distribution to the community \n\n" + \
        "Have you submitted your bep20 wallet address ?"
        
        bot.send_photo(
            call.message.chat.id,
            'https://www.fifareward.io/fifarewardlogo.png',
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    if data == 'yes':
        text = str("Congratulations on submitting your bep20 address and joining FRD airdrop. Patiently wait for the distribution date\n\n" +
        "Download Airdrop CSV List.\n\n")
        
        csv_file_path = generate_csv()
        
        keyboard.add(
            telebot.types.InlineKeyboardButton("Download CSV", callback_data=csv_file_path)
        )
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
        )
        
    if data == 'no':
        text = str("Send your bep20 wallet address to me.\n\n")
        bot.answer_callback_query(call.id)
        bot.send_chat_action(call.message.chat.id, 'typing')
        bot.send_message(
            call.message.chat.id,
            text
        )
    
    if call.data.endswith('.csv') :
        # Send the CSV file to the user
        bot.send_document(call.message.chat.id, open(call.data, 'rb'))
        

    
# Create the table if not exists
create_tables()

bot.infinity_polling()
