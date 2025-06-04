import logging
import logging.handlers
import os
import traceback
import datetime
import random
import asyncio
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    JobQueue
)
from dotenv import load_dotenv

# Configure logger
logger = logging.getLogger('my_bot')
logger.setLevel(logging.DEBUG)

# Rotating file handler
file_handler = logging.handlers.RotatingFileHandler(
    'bot.log',
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add handler
logger.addHandler(file_handler)

# ===== CONFIGURATION =====
# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()  # Load variables from .env file

# --- SECURE ENV CONFIGURATION ---
TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS")

# Validate critical configuration
missing_vars = []
if not TOKEN: missing_vars.append("BOT_TOKEN")
if not SUPPORT_USERNAME: missing_vars.append("SUPPORT_USERNAME")
if not SUPPORT_CHANNEL_ID: missing_vars.append("SUPPORT_CHANNEL_ID")
if not ADMIN_CHAT_ID: missing_vars.append("ADMIN_CHAT_ID")

if missing_vars:
    # Provide detailed troubleshooting help
    print(f"CRITICAL: Missing environment variables: {', '.join(missing_vars)}")
    print("\nTROUBLESHOOTING GUIDE:")
    print("1. Create a .env file in your project directory")
    print("2. Add the required variables in this format:")
    print('   BOT_TOKEN="your_token_here"')
    print('   SUPPORT_USERNAME="your_username_here"')
    print("3. Ensure the .env file is in the same directory as your script")
    print("4. Verify variable names match exactly (case-sensitive)")
    print("\nExample .env file content:")
    print('BOT_TOKEN="7474373357:AAFe1f4SpA-ocsqiaBWV7PYA6EkD0-_5qRI"')
    print('SUPPORT_USERNAME="Firekirin77777"')
    print('SUPPORT_CHANNEL_ID="-1002416775295"')
    print('ADMIN_CHAT_ID="-1002416775295"')
    raise EnvironmentError("Missing critical environment variables")

# Convert and validate numeric IDs
try:
    SUPPORT_CHANNEL_ID = int(SUPPORT_CHANNEL_ID)
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
except ValueError:
    raise TypeError("SUPPORT_CHANNEL_ID and ADMIN_CHAT_ID must be integers")

# Process admin user IDs
ADMIN_USER_IDS = [int(x.strip()) for x in ADMIN_USER_IDS.split(",")] if ADMIN_USER_IDS else []
if not ADMIN_USER_IDS:
    print("WARNING: No ADMIN_USER_IDS specified - admin commands will be disabled")

SUPPORT_URL = f"https://t.me/{SUPPORT_USERNAME}"

# --- REST OF YOUR CONFIGURATION ---
# Conversation states
SCAMMER_INFO, INCIDENT_DETAILS, EVIDENCE, ACCOUNT_INFO = range(4)

# Global user tracking
interacted_users = set()
started_users = set()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_file = os.getenv("LOG_FILE", "firekirin_bot.log")
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
))
logger.addHandler(file_handler)

# Add console logging for development
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
))
logger.addHandler(console_handler)


# --- COMPLETE PROMOTIONAL MESSAGES ---
PROMOTIONAL_MESSAGES = [
    f"🚨 FLASH OFFER! 40% reload bonus - 12hrs ONLY! Deposit NOW! 🔥\n\n"
    f"⚡ Instant cashouts! Win → Cash in SECONDS! 💨\n\n"
    f"💬 Problems? Questions? Message @{SUPPORT_USERNAME} now!",

    f"🎉 100% SIGNUP BONUS! Double your start + instant cashouts! ⚡\n\n"
    f"⚡ Instant cashouts! Win → Cash in SECONDS! 💨\n\n"
    f"💬 Problems? Need help? Contact @{SUPPORT_USERNAME}!",

    f"🛡️ 15% WEEKLY CASHBACK! Lose? We soften the blow! 💸\n\n"
    f"⚡ Instant cashouts! Win → Cash in SECONDS! 💨\n\n"
    f"💬 Problems? Assistance? DM @{SUPPORT_USERNAME}!",

    f"👥 50% REFERRAL BONUS! Earn $$$ when friends play! 🎁\n\n"
    f"Instant cashouts! Win → Cash in SECONDS! 💨\n\n"
    f"💬 Problems? Support? Message @{SUPPORT_USERNAME}!",

    f"🎮 HOT GAMES: Orion Stars, FireKirin, Juwa, Vegas! 🔥\n\n"
    f"⚡ Instant cashouts! Win → Cash in SECONDS! 💨\n\n"
    f"💬 Problems? Issues? Contact @{SUPPORT_USERNAME}!",

    f"🏆 PLAY CONSISTENTLY! Deposit often → Win more → Cashout BIG! 💰\n\n"
    f"💬 Help? Message @{SUPPORT_USERNAME}!"
]

# ===== BROADCAST SYSTEM =====
class BroadcastSystem:
    def __init__(self):
        self.message_index = 0
        self.is_active = True
        self.min_delay = 3600  # 1 hour
        self.max_delay = 14400  # 4 hours
        self.last_sent = None

    async def broadcast_messages(self, context: ContextTypes.DEFAULT_TYPE):
        """Send promotional messages to all interacted users"""
        if not self.is_active or not interacted_users:
            return

        # Format message with support username
        message = PROMOTIONAL_MESSAGES[self.message_index].format(
            support_username=SUPPORT_USERNAME
        )

        # Send to all users
        failed_users = set()
        for user_id in list(interacted_users):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 SPECIAL OFFER 🎉\n\n{message}\n\n{SUPPORT_URL}"
                )
                logger.info(f"Broadcast sent to {user_id}")
                # Add delay to prevent flooding
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Failed broadcast to {user_id}: {str(e)}")
                failed_users.add(user_id)

        # Remove failed users
        interacted_users.difference_update(failed_users)

        # Update index and timestamp
        self.message_index = (self.message_index + 1) % len(PROMOTIONAL_MESSAGES)
        self.last_sent = datetime.datetime.now()
        logger.info(f"Completed broadcast cycle. Next message: {self.message_index}")

        # Schedule next broadcast with random delay
        delay = random.randint(self.min_delay, self.max_delay)
        context.job_queue.run_once(
            lambda ctx: self.broadcast_messages(ctx),
            delay
        )
        logger.info(f"Next broadcast scheduled in {delay // 3600} hours")


# Initialize broadcast system
broadcast_system = BroadcastSystem()

# ===== USER TRACKING =====
def track_user(user_id: int):
    """Track user interactions and store in global sets"""
    interacted_users.add(user_id)
    logger.debug(f"Tracked user interaction: {user_id}")


def track_new_user(user_id: int):
    """Track users who started the bot"""
    started_users.add(user_id)
    logger.info(f"New user started: {user_id}")


# ===== CHANNEL COMMUNICATION =====
async def send_to_channel(context, report_type: str, data: dict):
    """Send collected data to private support channel with rich formatting"""
    try:
        # Create header based on report type
        if report_type == "ACCOUNT":
            header = "🔥 NEW ACCOUNT REQUEST"
            icon = "📝"
        else:
            header = "🚨 URGENT SCAM REPORT"
            icon = "⚠️"

        # Format message with Markdown
        message = (
            f"{icon} *{header}*\n"
            f"🕒 *Timestamp*: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👤 *User*: {data['user_name']} "
            f"(ID: `{data['user_id']}`)\n"
            f"🔗 Profile: [@{data['user_username']}](tg://user?id={data['user_id']})\n"
        )

        # Add type-specific details
        if report_type == "ACCOUNT":
            message += (
                f"\n🎮 *Game Platform*: {data['game']}\n"
                f"👤 *Full Name*: {data['contact_name']}\n"
                f"📧 *Email*: `{data['email']}`\n"
                f"📱 *Phone*: `{data['phone']}`\n"
            )
        else:  # SCAM REPORT
            message += (
                f"\n🕵️ *Scammer Info*: `{data['scammer']}`\n"
                f"💸 *Incident Details*:\n{data['incident']}\n"
                f"🔍 *Evidence*:\n{data['evidence']}\n"
            )

        # Add quick action buttons
        keyboard = [
            [InlineKeyboardButton("📩 Contact User",
                                  callback_data=f"contact_user_{data['user_id']}")],
            [InlineKeyboardButton("✅ Mark Resolved",
                                  callback_data=f"resolve_{report_type}_{data['user_id']}")]
        ]

        # Send to channel with failover
        try:
            await context.bot.send_message(
                chat_id=SUPPORT_CHANNEL_ID,
                text=message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Sent {report_type} report to channel {SUPPORT_CHANNEL_ID}")
            return True
        except Exception as e:
            logger.error(f"Channel send failed: {str(e)}")
            # Attempt fallback to admin group
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"❌ CHANNEL SEND FAILED\n\n{message}\n\nError: {str(e)}",
                    parse_mode='Markdown'
                )
                logger.info("Sent fallback message to admin group")
                return False
            except Exception as admin_error:
                logger.critical(f"Admin fallback failed: {str(admin_error)}")
                return False

    except Exception as e:
        logger.critical(f"Channel formatting error: {str(e)}")
        # Send raw data as fallback
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ FORMAT ERROR\n\nRaw data: {str(data)}\n\nError: {str(e)}"
            )
            return False
        except Exception as fallback_error:
            logger.critical(f"Fallback message failed: {str(fallback_error)}")
            return False


async def send_new_user_notification(context: ContextTypes.DEFAULT_TYPE, user: telegram.User):
    """Send notification about new users to channel"""
    try:
        user_count = len(started_users)
        message = (
            "👤 NEW USER STARTED THE BOT\n\n"
            f"• Total Users: {user_count}\n"
            f"• User ID: `{user.id}`\n\n"
            f"🔗 Profile: [@{user.username}](tg://user?id={user.id})\n"
            "🌐 Bot is growing! 🌐"
        )

        await context.bot.send_message(
            chat_id=SUPPORT_CHANNEL_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Sent new user notification for {user.id}")
    except Exception as e:
        logger.error(f"Failed to send new user notification: {str(e)}")


async def send_stats_to_channel(context: ContextTypes.DEFAULT_TYPE):
    """Send interaction statistics to channel"""
    try:
        message = (
            "📊 BOT INTERACTION STATISTICS\n\n"
            f"• Total Users Started: {len(started_users)}\n"
            f"• Active Users Interacted: {len(interacted_users)}\n\n"
            f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await context.bot.send_message(
            chat_id=SUPPORT_CHANNEL_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info("Sent statistics to channel")
    except Exception as e:
        logger.error(f"Failed to send stats to channel: {str(e)}")


# ===== PROMOTIONAL MESSAGES =====
async def send_promotional_message(context: ContextTypes.DEFAULT_TYPE):
    """Send promotional message to a random user"""
    if not interacted_users:
        return

    user_id = random.choice(list(interacted_users))
    message = random.choice(PROMOTIONAL_MESSAGES)

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 SPECIAL OFFER 🎉\n\n{message}\n\n{SUPPORT_URL}"
        )
        logger.info(f"Sent promotional message to user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to send promotion to {user_id}: {str(e)}")
        # Remove inactive user
        interacted_users.discard(user_id)


async def schedule_promotions(context: ContextTypes.DEFAULT_TYPE):
    """Schedule random promotional messages"""
    while True:
        # Random interval between 30 minutes and 2 hours
        interval = random.randint(1800, 7200)
        await asyncio.sleep(interval)

        if interacted_users:
            await send_promotional_message(context)


# ===== BOT COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with command menu"""
    user = update.message.from_user
    logger.info(f"Start command by {user.full_name} (@{user.username}) ID:{user.id}")

    # Track user
    track_user(user.id)
    if user.id not in started_users:
        track_new_user(user.id)
        await send_new_user_notification(context, user)  # Fixed: pass user object instead of user.id

    keyboard = [
        [InlineKeyboardButton("🌟 Description", callback_data="description")],
        [InlineKeyboardButton("⚠️ Report Scam", callback_data="report_scam")],
        [InlineKeyboardButton("📝 Create Account", callback_data="create_account")],
        [InlineKeyboardButton("🛎 Contact Support", callback_data="contact_support")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]

    await update.message.reply_text(
        "🔥 WELCOME TO FIREKIRIN! 🔥\n\n"
        "Instant cashouts • 24/7 Support • Premium Gaming\n\n"
        "Select an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks from main menu"""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    logger.debug(f"Button: {query.data} by {user.full_name} (@{user.username})")

    # Track user interaction
    track_user(user.id)

    if query.data == "description":
        await description(update, context)
    elif query.data == "report_scam":
        await start_report_scam(update, context)
    elif query.data == "create_account":
        await create_account(update, context)
    elif query.data == "contact_support":
        await contact_support(update, context)
    elif query.data == "help":
        await help(update, context)


# ===== ACCOUNT CREATION FLOW =====
async def create_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show game platform selection"""
    user = update.callback_query.from_user if update.callback_query else update.message.from_user
    logger.info(f"Account creation started by {user.full_name}")

    # Track user interaction
    track_user(user.id)

    keyboard = [
        [InlineKeyboardButton("Orion Stars", callback_data="account:OrionStars")],
        [InlineKeyboardButton("FireKirin", callback_data="account:Firekirin")],
        [InlineKeyboardButton("Vegas", callback_data="account:Vegas")],
        [InlineKeyboardButton("Juwa", callback_data="account:Juwa")],
        [InlineKeyboardButton("PandaMaster", callback_data="account:PandaMaster")],
        [InlineKeyboardButton("Ultra Panda", callback_data="account:UltraPanda")],
        [InlineKeyboardButton("GameVault", callback_data="account:GameVault")],
        [InlineKeyboardButton("VBlink", callback_data="account:VBlink")],
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🔐 CREATE FIREKIRIN ACCOUNT\nSelect your gaming platform:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "🔐 CREATE FIREKIRIN ACCOUNT\nSelect your gaming platform:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def account_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle game selection and request contact info"""
    query = update.callback_query
    await query.answer()
    _, game = query.data.split(":")
    user = query.from_user
    logger.info(f"Account platform selected: {game} by {user.full_name}")

    # Track user interaction
    track_user(user.id)

    context.user_data['account_data'] = {
        'game': game,
        'user_id': user.id,
        'user_name': user.full_name,
        'user_username': user.username
    }

    await query.edit_message_text(
        f"✅ {game.upper()} ACCOUNT REQUEST\n\n"
        "📝 Please provide your contact information in this format:\n\n"
        "<b>Full Name, Email, Phone Number</b>\n\n"
        "Example: <code>John Doe, john@example.com, +1234567890</code>\n\n"
        "🔍 Make sure to include commas between each piece of information",
        parse_mode='HTML'
    )
    return ACCOUNT_INFO


async def collect_account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process contact info and notify user"""
    user = update.message.from_user
    logger.info(f"Account info received from {user.full_name}")

    # Track user interaction
    track_user(user.id)

    try:
        # Extract and validate user info
        parts = [x.strip() for x in update.message.text.split(',', 2)]
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ <b>INVALID FORMAT</b>\n\n"
                "Please provide all three pieces of information separated by commas:\n"
                "• Full Name\n• Email\n• Phone Number\n\n"
                "<b>Example:</b> <code>John Doe, john@example.com, +1234567890</code>\n\n"
                "Please try again:",
                parse_mode='HTML'
            )
            return ACCOUNT_INFO

        contact_name, email, phone = parts

        # Validate email format
        if '@' not in email or '.' not in email.split('@')[-1]:
            await update.message.reply_text(
                "❌ <b>INVALID EMAIL FORMAT</b>\n\n"
                "Please provide a valid email address.\n\n"
                "<b>Example:</b> <code>john@example.com</code>\n\n"
                "Please try again:",
                parse_mode='HTML'
            )
            return ACCOUNT_INFO

        account_data = context.user_data['account_data']
        account_data.update({
            'contact_name': contact_name,
            'email': email,
            'phone': phone
        })

        # Send to support channel
        success = await send_to_channel(context, "ACCOUNT", account_data)

        # Confirm to user
        if success:
            await update.message.reply_text(
                "✅ <b>ACCOUNT REQUEST COMPLETE!</b>\n\n"
                "Our support team will contact you shortly.\n\n"
                "Need immediate help? Contact:\n"
                f"👉 {SUPPORT_URL}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "⚠️ <b>SUBMISSION FAILED</b>\n\n"
                "Please contact support directly:\n"
                f"👉 {SUPPORT_URL}",
                parse_mode='HTML'
            )

        # Clear user data after successful processing
        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Account info error: {str(e)}")
        await update.message.reply_text(
            "❌ <b>INVALID FORMAT</b>\n\n"
            "Please provide:\n"
            "<b>Full Name, Valid Email, Phone</b>\n\n"
            "<b>Example:</b> <code>John Doe, john@example.com, +1234567890</code>\n\n"
            "Please try again:",
            parse_mode='HTML'
        )
        return ACCOUNT_INFO


# ===== SCAM REPORTING FLOW =====
async def start_report_scam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate scam reporting process"""
    user = update.callback_query.from_user if update.callback_query else update.message.from_user
    logger.info(f"Scam report started by {user.full_name}")

    # Track user interaction
    track_user(user.id)

    # Initialize report data
    context.user_data['report_data'] = {
        'user_id': user.id,
        'user_name': user.full_name,
        'user_username': user.username,
        'scammer': None,
        'incident': None,
        'evidence': None
    }

    # Create enhanced prompt with visual cues
    prompt = (
        "⚠️ <b>SCAM REPORT INITIATED</b> ⚠️\n\n"
        "We'll ask 3 quick questions:\n\n"
        "1️⃣ <b>FIRST QUESTION:</b>\n"
        "What's the scammer's username/phone number?\n\n"
        "🔍 <i>Example: @scammer_username or +1234567890</i>\n\n"
        "⬇️ Please type your answer below ⬇️\n\n"
        "⏱ You have 10 minutes to complete the report\n"
        "(Type /cancel anytime to stop)"
    )

    # Send as new message
    if update.callback_query:
        await update.callback_query.message.reply_text(prompt, parse_mode='HTML')
    else:
        await update.message.reply_text(prompt, parse_mode='HTML')

    return SCAMMER_INFO


async def scammer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect scammer information"""
    user = update.message.from_user
    scammer_info = update.message.text
    logger.info(f"Scammer info received from {user.full_name}")

    # Track user interaction
    track_user(user.id)

    # Store scammer info with timestamp
    context.user_data['report_data']['scammer'] = scammer_info
    context.user_data['report_data']['scammer_timestamp'] = datetime.datetime.now().isoformat()

    # Ask for incident details
    await update.message.reply_text(
        "✅ <b>Got it! Now for the next question:</b>\n\n"
        "2️⃣ <b>SECOND QUESTION:</b>\n"
        "Describe what happened:\n"
        "- What occurred?\n"
        "- When did it happen?\n"
        "- Amount involved?\n\n"
        "🔍 <i>Example: Sent $100 on 2023-10-15 but never received promised service</i>\n\n"
        "⬇️ Type your answer below ⬇️",
        parse_mode='HTML'
    )

    return INCIDENT_DETAILS


async def incident_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect incident details"""
    user = update.message.from_user
    incident = update.message.text
    logger.info(f"Incident details received from {user.full_name}")

    # Track user interaction
    track_user(user.id)

    # Store incident details with timestamp
    context.user_data['report_data']['incident'] = incident
    context.user_data['report_data']['incident_timestamp'] = datetime.datetime.now().isoformat()

    # Ask for evidence
    await update.message.reply_text(
        "✅ <b>Thank you! Final step:</b>\n\n"
        "3️⃣ <b>LAST QUESTION:</b>\n"
        "Share any evidence you have:\n"
        "- Transaction IDs\n"
        "- Screenshots\n"
        "- Other relevant info\n\n"
        "🔍 <i>Example: Transaction ID: TX123456, Screenshot attached</i>\n\n"
        "⬇️ Type your evidence below ⬇️\n"
        "(Type /skip if none)",
        parse_mode='HTML'
    )

    return EVIDENCE


async def evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect evidence"""
    user = update.message.from_user
    evidence_text = update.message.text
    logger.info(f"Evidence received from {user.full_name}")

    # Track user interaction
    track_user(user.id)

    # Store evidence with timestamp
    context.user_data['report_data']['evidence'] = evidence_text
    context.user_data['report_data']['evidence_timestamp'] = datetime.datetime.now().isoformat()

    # Complete the report
    await finish_report(update, context)
    return ConversationHandler.END


async def skip_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip evidence collection"""
    user = update.message.from_user
    logger.info(f"Evidence skipped by {user.full_name}")

    # Track user interaction
    track_user(user.id)

    # Mark evidence as skipped
    context.user_data['report_data']['evidence'] = "No evidence provided"
    context.user_data['report_data']['evidence_timestamp'] = datetime.datetime.now().isoformat()

    # Complete the report
    await finish_report(update, context)
    return ConversationHandler.END


async def finish_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compile and send final report"""
    user = update.message.from_user
    report_data = context.user_data['report_data']

    # Send to support channel
    success = await send_to_channel(context, "SCAM", report_data)

    # Confirm to user
    if success:
        await update.message.reply_text(
            "✅ <b>REPORT SUBMITTED SUCCESSFULLY!</b>\n\n"
            "Our security team will investigate within 24 hours.\n"
            f"Contact support: {SUPPORT_URL}",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "⚠️ <b>SUBMISSION FAILED</b>\n\n"
            "Please contact support directly:\n"
            f"👉 {SUPPORT_URL}",
            parse_mode='HTML'
        )

    # Clear user data after submission
    context.user_data.clear()
    logger.info(f"Scam report completed for {user.full_name}")


# ===== STATISTICS COMMAND =====
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show interaction statistics to admin"""
    user = update.message.from_user
    if user.id != ADMIN_CHAT_ID:
        return

    stats = (
        "📊 BOT INTERACTION STATISTICS\n\n"
        f"• Total Users Started: {len(started_users)}\n"
        f"• Active Users Interacted: {len(interacted_users)}\n\n"
        f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await update.message.reply_text(stats)
    logger.info(f"Admin {user.full_name} requested stats")


# ===== SUPPORT COMMANDS =====
async def description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show FireKirin features"""
    text = (
        "🎰 FIREKIRIN PREMIUM FEATURES 🎰\n\n"
        "✅ 100% SIGN-UP BONUS • 15% LOSS PROTECTION\n"
        "✅ 30% RELOAD BONUS • $50 PER FRIEND\n"
        "⚡ INSTANT WITHDRAWALS IN <60 SECONDS!\n\n"
        f"👉 Support: {SUPPORT_URL}"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show contact information"""
    text = (
        "🛎 24/7 FIREKIRIN SUPPORT\n\n"
        "Get immediate assistance:\n\n"
        f"👉 Telegram: {SUPPORT_URL}\n"
        "📱 WhatsApp: +1 (954) 832-8649\n\n"
        "Average response time: <5 minutes"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    text = (
        "❓ FIREKIRIN HELP CENTER ❓\n\n"
        "Get instant assistance:\n\n"
        f"👉 Official Support: {SUPPORT_URL}\n\n"
        "Common Issues:\n• Account setup\n• Deposits/Withdrawals\n• Game rules\n• Bonus claims"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing operation"""
    user = update.message.from_user
    logger.info(f"Operation cancelled by {user.full_name}")
    await update.message.reply_text("❌ Operation cancelled")

    # Clear conversation data
    context.user_data.clear()
    return ConversationHandler.END


# ===== ERROR HANDLER =====
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and send notification"""
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    logger.error(f"Exception: {tb_string}")

    # Build error message
    error_msg = (
        f"⚠️ *BOT ERROR* ⚠️\n\n"
        f"• Error: `{context.error}`\n"
        f"• Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"```{tb_string[-1000:]}```"
    )

    try:
        # Notify admin group
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=error_msg,
            parse_mode='Markdown'
        )
        logger.info("Sent error notification to admin group")

        # Notify user if possible
        if update and hasattr(update, 'message'):
            await update.message.reply_text(
                "⚠️ An error occurred. Our team has been notified.\n"
                f"Contact support directly: {SUPPORT_URL}"
            )
    except Exception as e:
        logger.error(f"Error notification failed: {str(e)}")


# ===== CHANNEL TEST COMMAND =====
async def test_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test channel connectivity"""
    try:
        # Send test message to channel
        await context.bot.send_message(
            chat_id=SUPPORT_CHANNEL_ID,
            text="🔔 BOT CHANNEL CONNECTION TEST 🔔\n\n"
                 "This is a test message from the FireKirin bot.\n"
                 "If you're seeing this, the channel connection is working properly!",
            parse_mode='Markdown'
        )

        await update.message.reply_text(
            "✅ Channel test successful!\n"
            f"Message sent to channel ID: {SUPPORT_CHANNEL_ID}"
        )
        logger.info(f"Channel test successful for {SUPPORT_CHANNEL_ID}")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Channel test failed!\nError: {str(e)}\n\n"
            "Please check:\n"
            "1. Channel ID is correct\n"
            "2. Bot is admin in channel\n"
            "3. Channel privacy settings"
        )
        logger.error(f"Channel test failed: {str(e)}")


# ===== BUTTON HANDLERS =====
async def handle_contact_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact user button from reports"""
    query = update.callback_query
    await query.answer()

    try:
        # Extract user ID from callback data
        user_id = int(query.data.split('_')[-1])

        # Edit message to show action taken
        await query.edit_message_text(
            text=query.message.text + f"\n\n✅ Admin @{query.from_user.username} is contacting user",
            parse_mode='Markdown'
        )

        # Send contact information to admin
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"🔗 Contact user directly:\n"
                 f"User ID: `{user_id}`\n"
                 f"Direct link: [Message User](tg://user?id={user_id})",
            parse_mode='Markdown'
        )

        logger.info(f"Admin {query.from_user.id} requested contact with user {user_id}")

    except Exception as e:
        logger.error(f"Contact user error: {str(e)}")
        await query.answer("❌ Failed to process request. Please try manual contact.", show_alert=True)


async def handle_resolve_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle resolve report button from reports"""
    query = update.callback_query
    await query.answer()

    try:
        # Extract report type and user ID
        _, report_type, user_id = query.data.split('_', 2)
        user_id = int(user_id)

        # Edit message to mark as resolved
        await query.edit_message_text(
            text=query.message.text + f"\n\n✅ RESOLVED by @{query.from_user.username}",
            parse_mode='Markdown'
        )

        # Notify user if possible
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"ℹ️ Your {report_type.lower()} report has been resolved!\n"
                     "Thank you for helping us improve our service."
            )
        except Exception as notify_error:
            logger.warning(f"Couldn't notify user {user_id}: {str(notify_error)}")

        logger.info(f"Report resolved by admin {query.from_user.id} for user {user_id}")

    except Exception as e:
        logger.error(f"Resolve report error: {str(e)}")
        await query.answer("❌ Failed to mark resolved. Please try again.", show_alert=True)


async def scam_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation timeout for scam reports"""
    user = update.message.from_user
    logger.warning(f"Scam report timed out for {user.full_name}")

    await update.message.reply_text(
        "⏱️ Scam report session timed out due to inactivity\n\n"
        "Please start a new report if needed\n"
        f"Get help: {SUPPORT_URL}"
    )
    context.user_data.clear()
    return ConversationHandler.END


# ===== MAIN SETUP =====
def main():
    # Initialize application
    app = Application.builder().token(TOKEN).build()
    logger.info("🚀 FireKirin bot starting...")

    # Get the job queue
    job_queue = app.job_queue

    # Add test command for channel debugging
    app.add_handler(CommandHandler("testchannel", test_channel))
    app.add_handler(CommandHandler("stats", show_stats))

    # Account creation conversation
    account_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(account_selected, pattern="^account:")],
        states={
            ACCOUNT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_account_info)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    # Scam report conversation - FIXED FLOW
    scam_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_report_scam, pattern="^report_scam$"),
            CommandHandler("report", start_report_scam)
        ],
        states={
            SCAMMER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, scammer_info)],
            INCIDENT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, incident_details)],
            EVIDENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, evidence),
                CommandHandler("skip", skip_evidence)
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, scam_timeout)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="scam_report_handler",
        per_message=False,
        conversation_timeout=600  # 10-minute timeout
    )

    # Main handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        CallbackQueryHandler(button_handler, pattern="^(description|report_scam|create_account|contact_support|help)$"))
    app.add_handler(account_handler)
    app.add_handler(scam_handler)

    # Command shortcuts
    app.add_handler(CommandHandler("description", description))
    app.add_handler(CommandHandler("create", create_account))
    app.add_handler(CommandHandler("support", contact_support))
    app.add_handler(CommandHandler("help", help))

    # Error handler
    app.add_error_handler(error_handler)

    # Add new button handlers - FIXED BUTTON FUNCTIONALITY
    app.add_handler(CallbackQueryHandler(handle_contact_user, pattern=r"^contact_user_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_resolve_report, pattern=r"^resolve_(SCAM|ACCOUNT)_\d+$"))

    # Schedule promotional messages if job queue exists
    if job_queue:

        # Schedule promotional messages with random intervals
        job_queue.run_repeating(
            send_promotional_message,
            job_queue.run_repeating(
                send_promotional_message,
                interval=8 * 60 * 60,  # 8 hours
                first=30
            )

        )

        # Schedule daily stats report
        job_queue.run_daily(
            send_stats_to_channel,
            time=datetime.time(9, 0, 0),  # 9AM daily
            days=(0, 1, 2, 3, 4, 5, 6)
        )
    else:
        logger.warning("Job queue not available - promotional scheduling disabled")

    # Start bot
    logger.info("✅ Bot setup complete. Starting polling...")
    app.run_polling()


if __name__ == "__main__":
    main()