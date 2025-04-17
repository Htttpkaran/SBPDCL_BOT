from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import asyncio
import time
import os
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Telegram Bot Token from Environment
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN is not set. Please set it as an environment variable.")
    exit("Environment variable TELEGRAM_BOT_TOKEN is missing.")

# Subscriber data: {chat_id: ca_number}
subscribers = {}

# Fetch data function using Selenium
def fetch_data(ca_number: str) -> tuple:
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.get("https://sbpdcl.co.in/frmQuickBillPaymentAll.aspx")

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "MainContent_txtCANO")))
        driver.find_element(By.ID, "MainContent_txtCANO").send_keys(ca_number)

        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "MainContent_btnSubmit")))
        driver.find_element(By.ID, "MainContent_btnSubmit").click()

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "MainContent_btnCurrentblnce")))
        driver.find_element(By.ID, "MainContent_btnCurrentblnce").click()

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "MainContent_txtCurrentblnce")))
        balance = driver.find_element(By.ID, "MainContent_txtCurrentblnce").get_attribute("value").strip()

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "MainContent_lblcnStatus")))
        connection_status = driver.find_element(By.ID, "MainContent_lblcnStatus").text.strip()

        now = datetime.now().strftime("%d-%m-%Y, %H:%M:%S")
    except Exception as e:
        balance = None
        connection_status = f"Error: {e}"
        now = datetime.now().strftime("%d-%m-%Y, %H:%M:%S")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.warning(f"⚠️ Failed to close the driver: {e}")
    return balance, connection_status, now

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to ⚡ *Smart Meter Bot* ⚡\nSend me your *CA Number* to get your current balance.\n\nYou'll now receive hourly updates.",
        parse_mode='Markdown'
    )

async def get_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ca_number = update.message.text.strip()
    subscribers[update.message.chat_id] = ca_number

    await update.message.reply_text("🔍 Fetching your balance, please wait...")

    balance, connection_status, now = await asyncio.to_thread(fetch_data, ca_number)
    if balance:
        await update.message.reply_text(
            f"✅ *CA Number:* `{ca_number}`\n\n💡 *Current Balance:* ₹{balance}\n\n"
            f"🔌 *Connection Status:* {connection_status}\n\n📅 *Date & Time:* {now}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("⚠️ Couldn't fetch balance. Please check the CA Number.")

async def hourly_update(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, ca_number in subscribers.items():
        try:
            balance, connection_status, now = await asyncio.to_thread(fetch_data, ca_number)
            if balance:
                message = (
                    f"🔄 *Hourly Update*\n\n"
                    f"✅ *CA Number:* `{ca_number}`\n\n"
                    f"💡 *Current Balance:* ₹{balance}\n\n"
                    f"🔌 *Connection Status:* {connection_status}\n\n"
                    f"📅 *Date & Time:* {now}"
                )
            else:
                message = (
                    f"🔄 *Hourly Update*\n\n"
                    f"❌ Unable to fetch data for CA Number: `{ca_number}`\n"
                    f"Error: {connection_status}"
                )
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error sending hourly update to {chat_id}: {e}")

async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"⚠️ Telegram error: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("🚫 Internal error occurred. Please try again later.")

# Start the bot with webhook
if __name__ == "__main__":
    try:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), get_balance))
        app.add_error_handler(handle_error)

        app.job_queue.run_repeating(hourly_update, interval=3600, first=10)

        logger.info("🚀 Bot started with webhook.")

        # Railway provides a domain like: https://worker-production-xyz.up.railway.app
        RAILWAY_DOMAIN = os.getenv("RAILWAY_DOMAIN")
        if not RAILWAY_DOMAIN:
            logger.critical("❌ RAILWAY_DOMAIN environment variable is missing.")
            exit()

        webhook_url = f"{RAILWAY_DOMAIN}/webhook"

        # Set webhook
        import httpx
        resp = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            params={"url": webhook_url}
        )
        logger.info(f"🔗 Webhook set: {resp.json()}")

        # Run with webhook
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 8080)),
            webhook_url=webhook_url
        )

    except Exception as e:
        logger.critical(f"❌ Failed to start the bot: {e}")
        exit("Bot initialization failed.")
