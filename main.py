import os
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# ---------------- Load .env ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ---------------- Database ----------------
DB_FILE = "database.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {},
            "stock": {
                "MLBBbal": {},  # {"1000": ["code1", "code2"], "2000": ["code3"]}
                "MLBBph": {},
                "PUPG": {}
            },
            "receipts": {},
            "topup_requests": {},
            "prices": {
                "MLBBbal": {},  # {"1000": 2000, "2000": 4000}
                "MLBBph": {},
                "PUPG": {}
            },
            "payment": {
                "Wave": {
                    "phone": "09673585480",
                    "name": "Nine Nine"
                },
                "Kpay": {
                    "phone": "09678786528",
                    "name": "Ma May Phoo Wai"
                }
            },
            "sales_total": 0,
            "pending_registrations": {}
        }
    with open(DB_FILE, "r") as f:
        data = json.load(f)

    # Update old structure if needed
    if "stock" in data and isinstance(data["stock"], dict) and "mlbb" in data["stock"]:
        new_stock = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}
        new_prices = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}

        # Migrate MLBB codes assuming they are for MLBBbal
        mlbb_codes = data["stock"].get("mlbb", [])
        if mlbb_codes:
            new_stock["MLBBbal"]["1000"] = mlbb_codes
            if "price" in data and data["price"] > 0:
                new_prices["MLBBbal"]["1000"] = data["price"]
            else:
                new_prices["MLBBbal"]["1000"] = 1000

        # Migrate PUBG codes to PUPG
        pubg_codes = data["stock"].get("pubg", [])
        if pubg_codes:
            new_stock["PUPG"]["60"] = pubg_codes
            if "price" in data and data["price"] > 0:
                new_prices["PUPG"]["60"] = data["price"]
            else:
                new_prices["PUPG"]["60"] = 1000

        data["stock"] = new_stock
        data["prices"] = new_prices
        save_db(data)

    # Migrate PUBG to PUPG in existing structure
    if "stock" in data and "PUBG" in data["stock"]:
        data["stock"]["PUPG"] = data["stock"].pop("PUBG")
    if "prices" in data and "PUBG" in data["prices"]:
        data["prices"]["PUPG"] = data["prices"].pop("PUBG")

    # Ensure all expected keys exist
    if "stock" not in data:
        data["stock"] = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}
    if "prices" not in data:
        data["prices"] = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}
    if "topup_requests" not in data: 
        data["topup_requests"] = {}
    if "users" not in data: 
        data["users"] = {}
    if "payment" not in data:
        data["payment"] = {
            "Wave": {
                "phone": "09673585480",
                "name": "Nine Nine"
            },
            "Kpay": {
                "phone": "09678786528",
                "name": "Ma May Phoo Wai"
            }
        }
    if "sales_total" not in data: 
        data["sales_total"] = 0
    if "pending_registrations" not in data: 
        data["pending_registrations"] = {}

    # Clear old codes from MLBBph and PUPG (one-time cleanup)
    if "cleanup_done" not in data:
        if "MLBBph" in data["stock"]:
            data["stock"]["MLBBph"] = {}
        if "PUPG" in data["stock"]:
            data["stock"]["PUPG"] = {}
        data["cleanup_done"] = True

    return data


def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


db = load_db()


# ---------------- Helpers ----------------
def get_user(uid):
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0, "history": [], "approved": False}
        save_db(db)
    return db["users"][uid]


def is_user_approved(uid):
    return uid in db["users"] and db["users"][uid].get("approved", False)


def generate_receipt_id():
    while True:
        rid = str(random.randint(10000, 999999))
        if rid not in db["receipts"] and rid not in db["topup_requests"]:
            return rid


def validate_receipt_id(rid):
    return rid.isdigit() and 5 <= len(rid) <= 6


def get_available_amounts(game_type):
    """Get available amounts for a game type that have stock"""
    amounts = []
    if game_type in db["stock"]:
        for amount, codes in db["stock"][game_type].items():
            if codes:  # Only include amounts that have codes
                amounts.append(amount)
    return sorted(amounts)


def get_game_display_name(game_type):
    names = {
        "MLBBbal": "Mobile Legends (Bal)",
        "MLBBph": "Mobile Legends (PH)",
        "PUPG": "PUPG Mobile"
    }
    return names.get(game_type, game_type)


# ---------------- User Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[
        InlineKeyboardButton("📌 အကောင့်ဝင်ရန်", callback_data="register")
    ], [InlineKeyboardButton("💰 ငွေစစ်", callback_data="balance")],
                [InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup")],
                [InlineKeyboardButton("🛒 ကုတ်ဝယ်ရန်", callback_data="buy")],
                [InlineKeyboardButton("ℹ️ အကူအညီ", callback_data="help")]]
    if update.message:
        await update.message.reply_text(
            f"👋 မင်္ဂလာပါ {user.first_name}! ကျွန်ုပ်တို့ထံမှကြိုဆိုပါတယ်။",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(
            f"👋 မင်္ဂလာပါ {user.first_name}! ကျွန်ုပ်တို့ထံမှကြိုဆိုပါတယ်။",
            reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "start":
        await start(update, context)
        return

    if data == "register":
        if uid in db["users"] and db["users"][uid].get("approved", False):
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
            ]]
            await query.edit_message_text(
                "✅ အကောင့်ဝင်ပြီးသားဖြစ်ပါသည်။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return
        elif uid in db["pending_registrations"]:
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
            ]]
            await query.edit_message_text(
                "⏳ အကောင့်ဝင်ရန်တောင်းဆိုထားပြီး စောင့်ဆိုင်းနေပါသည်။ Admin မှ လက်ခံပေးသည်အထိ စောင့်ပါ",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Create registration request
        db["pending_registrations"][uid] = {
            "user_id": uid,
            "username": query.from_user.first_name,
            "status": "pending"
        }
        save_db(db)

        # Send to admin
        keyboard = [[
            InlineKeyboardButton("✅ လက်ခံရန်", callback_data=f"approve_reg_{uid}"),
            InlineKeyboardButton("❌ ငြင်းပယ်ရန်", callback_data=f"reject_reg_{uid}")
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📬 အကောင့်ဝင်ရန်တောင်းဆိုမှုအသစ်:\n"
            f"👤 အသုံးပြုသူ ID: {uid}\n"
            f"📝 အမည်: {query.from_user.first_name}\n"
            f"👤 Username: @{query.from_user.username or 'မရှိ'}",
            reply_markup=InlineKeyboardMarkup(keyboard))

        keyboard = [[
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
        ]]
        await query.edit_message_text(
            "📝 အကောင့်ဝင်ရန်တောင်းဆိုမှုကို Admin ထံသို့ပို့ပြီးဖြစ်ပါသည်။ စောင့်ဆိုင်းပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "balance":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ အကောင့်အား Admin လက်ခံပြီးမှသာ အသုံးပြုနိုင်ပါသည်။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        user = get_user(uid)
        keyboard = []
        # Check if user has enough for any available product
        can_buy = False
        for game_type in db["prices"]:
            for amount, price in db["prices"][game_type].items():
                if amount in db["stock"].get(game_type, {}) and db["stock"][game_type][amount]:
                    if user['balance'] >= price:
                        can_buy = True
                        break

        if not can_buy:
            keyboard.append([InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup")])
        keyboard.append([InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")])
        await query.edit_message_text(
            f"💰 လက်ကျန်ငွေ: {user['balance']} MMK",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "topup":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ အကောင့်အား Admin လက်ခံပြီးမှသာ အသုံးပြုနိုင်ပါသည်။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [
            [InlineKeyboardButton("📱 Wave", callback_data="topup_wave")],
            [InlineKeyboardButton("📱 Kpay", callback_data="topup_kpay")],
            [InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")]
        ]
        await query.edit_message_text(
            "💳 ငွေဖြည့်လိုသည့်နည်းလမ်းကိုရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("topup_"):
        payment_method = data.split("_")[1].title()
        payment_info = db["payment"][payment_method]

        context.user_data['topup_method'] = payment_method
        keyboard = [[
            InlineKeyboardButton(f"📋 {payment_info['phone']}", callback_data=f"copy_{payment_info['phone']}")
        ], [InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="topup")]]

        await query.edit_message_text(
            f"💳 {payment_method} ဖြင့်ငွေဖြည့်ရန်:\n\n"
            f"📱 ဖုန်းနံပါတ်: {payment_info['phone']}\n"
            f"👤 အမည်: {payment_info['name']}\n\n"
            f"📋 ဖုန်းနံပါတ်ကိုကူးယူရန် အပေါ်ကခလုတ်ကိုနှိပ်ပါ:\n\n"
            f"💰 လွှဲပြီးပါက screenshot နှင့်တကွ အောက်ပါအချက်အလက်များကို ပို့ပေးပါ:\n"
            f"• လွှဲငွေ ID (နောက်ဆုံး ၅လုံး သို့မဟုတ် ၆လုံး)\n"
            f"• လွှဲပို့သည့်ငွေပမာဏ\n"
            f"ပို့ပေးပါ\n\n"
            f"⚠️ သတိပြုရန်: လွှဲငွေ ID မှန်မှန်ကန်ကန်ပို့မှသာ ငွေဖြည့်ပေးမည်\n\n"
            f"🕗 ငွေလွှဲပြီးလျှင် အောက်သို့ဆက်သွားပါ\n"
            f"ℹ️ KPay ဖြင့်ငွေလွှဲလျှင် အကောင့်လွဲ၍ KPay အမည်တူ ပို့ပေးပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("copy_"):
        phone_number = data.split("_", 1)[1]
        # Send the phone number as a separate message for easier copying
        await context.bot.send_message(chat_id=query.from_user.id, text=phone_number)
        await query.answer(f"📋 {phone_number} ကိုပို့ပေးပြီးပါပြီ! အပေါ်ကစာကို ကူးယူပါ။", show_alert=True)

    elif data == "help":
        keyboard = [[
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
        ]]
        await query.edit_message_text(
            "ℹ️ အသုံးပြုနည်း:\n\n"
            "1️⃣ အကောင့်ဝင်ပါ\n"
            "2️⃣ ငွေစစ်ဆေးပါ\n"
            "3️⃣ ငွေဖြည့်ပါ\n"
            "4️⃣ ကုတ်ဝယ်ယူပါ\n\n"
            "📌 မှတ်ချက်:\n"
            "• Admin မှ လက်ခံပြီးမှသာ ကုတ်ဝယ်ယူနိုင်မည်\n"
            "• ဝယ်ပြီးပစ္စည်း ပြန်လည် Umru ကြေးတောင်းခြင်း လက်မခံပါ\n"
            "• လွှဲငွေဖြင့်ဝယ်ယူလျှင် Admin လက်ခံပြီးမှသာ ကုတ်ဝယ်ယူနိုင်မည်\n"
            "• ငွေစစ်၍ဝယ်ယူလျှင် ချက်ချင်းဝယ်ယူနိုင်မည်",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "buy":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ အကောင့်အား Admin လက်ခံပြီးမှသာ အသုံးပြုနိုင်ပါသည်။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Show available game types
        keyboard = []
        available_games = []

        for game_type in ["MLBBbal", "MLBBph", "PUPG"]:
            amounts = get_available_amounts(game_type)
            if amounts:
                total_codes = sum(len(codes) for codes in db["stock"].get(game_type, {}).values())
                if total_codes > 0:
                    game_name = get_game_display_name(game_type)
                    keyboard.append([
                        InlineKeyboardButton(f"🎮 {game_name} ({total_codes})", callback_data=f"select_{game_type}")
                    ])
                    available_games.append(game_type)

        if not available_games:
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ လက်ရှိတွင် ကုတ်မရှိသေးပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard.append([InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")])
        await query.edit_message_text(
            "🎮 ဂိမ်းအမျိုးအစားရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_"):
        game_type = data.split("_")[1]
        amounts = get_available_amounts(game_type)

        if not amounts:
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="buy")
            ]]
            await query.edit_message_text(
                "⚠️ ဒီဂိမ်းအတွက် ကုတ်မရှိသေးပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = []
        game_name = get_game_display_name(game_type)

        for amount in amounts:
            codes_count = len(db["stock"][game_type][amount])
            price = db["prices"][game_type].get(amount, 0)
            unit = "Coin" if "MLBB" in game_type else "UC"
            keyboard.append([
                InlineKeyboardButton(f"💎 {amount} {unit} - {price} MMK ({codes_count})", callback_data=f"amount_{game_type}_{amount}")
            ])

        keyboard.append([InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="buy")])
        await query.edit_message_text(
            f"🎮 {game_name}\n💎 အရေအတွက်ရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("amount_"):
        parts = data.split("_")
        game_type = parts[1]
        amount = parts[2]

        if amount not in db["stock"].get(game_type, {}) or not db["stock"][game_type][amount]:
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data=f"select_{game_type}")
            ]]
            await query.edit_message_text(
                "⚠️ ဒီပမာဏအတွက် ကုတ်မရှိသေးပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        price = db["prices"][game_type].get(amount, 0)
        user = get_user(uid)
        max_quantity = len(db["stock"][game_type][amount])

        # Store selection data for text input
        context.user_data['selecting_quantity'] = {
            'game_type': game_type,
            'amount': amount,
            'price': price,
            'max_quantity': max_quantity
        }

        keyboard = [[
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data=f"select_{game_type}")
        ]]

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"🎮 {game_name}\n"
            f"💎 {amount} {unit}\n"
            f"💰 ဈေးနှုန်း: {price} MMK/ကုတ်\n"
            f"💳 လက်ကျန်ငွေ: {user['balance']} MMK\n"
            f"📦 လက်ကျန်ရှိသော ကုတ်: {max_quantity} ခု\n\n"
            f"📝 လိုချင်သော ကုတ်အရေအတွက် ပို့ပေးပါ (1 to {max_quantity}):",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("quantity_"):
        parts = data.split("_")
        game_type = parts[1]
        amount = parts[2]
        quantity = int(parts[3])

        price = db["prices"][game_type].get(amount, 0)
        total_price = price * quantity
        user = get_user(uid)

        keyboard = []
        if user["balance"] >= total_price:
            keyboard.append([
                InlineKeyboardButton(
                    f"💰 လက်ကျန်ငွေဖြင့်ဝယ်ရန် ({total_price} MMK)",
                    callback_data=f"buy_balance_{game_type}_{amount}_{quantity}"
                )
            ])
        else:
            keyboard.append([InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup")])

        # Add KPay and Wave Pay payment options
        keyboard.append([
            InlineKeyboardButton(
                "📱 KPay ဖြင့်ဝယ်ရန်",
                callback_data=f"buy_kpay_{game_type}_{amount}_{quantity}")
        ])
        keyboard.append([
            InlineKeyboardButton(
                "📱 Wave Pay ဖြင့်ဝယ်ရန်", 
                callback_data=f"buy_wave_{game_type}_{amount}_{quantity}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data=f"amount_{game_type}_{amount}")
        ])

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"🎮 {game_name}\n"
            f"💎 {amount} {unit} x {quantity}\n"
            f"💰 စုစုပေါင်းတန်ဖိုး: {total_price} MMK\n"
            f"💳 လက်ကျန်ငွေ: {user['balance']} MMK\n\n"
            f"💳 ငွေပေးချေမှုနည်းလမ်းကိုရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy_balance_"):
        parts = data.split("_")
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])

        user = get_user(uid)
        price = db["prices"][game_type].get(amount, 0)
        total_price = price * quantity

        if user["balance"] < total_price:
            keyboard = [[
                InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup")
            ], [
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန�", callback_data=f"quantity_{game_type}_{amount}_{quantity}")
            ]]
            await query.edit_message_text(
                "⚠️ လက်ကျန်ငွေမလုံလောက်ပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if len(db["stock"][game_type][amount]) < quantity:
            keyboard = [[
                InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="buy")
            ]]
            await query.edit_message_text(
                "⚠️ လုံလောက်သော ကုတ်မရှိပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Get codes
        codes = []
        for _ in range(quantity):
            if db["stock"][game_type][amount]:
                codes.append(db["stock"][game_type][amount].pop(0))

        user["balance"] -= total_price
        db["sales_total"] += total_price
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"

        user["history"].append({
            "type": "balance",
            "codes": codes,
            "game": game_name,
            "amount": amount,
            "quantity": quantity,
            "total_price": total_price
        })
        save_db(db)

        codes_text = "\n".join([f"🔑 {code}" for code in codes])
        keyboard = [[
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
        ]]
        await query.edit_message_text(
            f"✅ ဝယ်ယူမှုအောင်မြင်ပါပြီ!\n\n"
            f"🎮 {game_name}\n"
            f"💎 {amount} {unit} x {quantity}\n"
            f"💰 စုစုပေါင်းတန်ဖိုး: {total_price} MMK\n\n"
            f"🔑 ကုတ်များ:\n{codes_text}\n\n"
            f"💳 လက်ကျန်ငွေ: {user['balance']} MMK",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy_kpay_") or data.startswith("buy_wave_"):
        parts = data.split("_")
        payment_method = parts[1]  # kpay or wave
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])

        context.user_data['buying_game'] = game_type
        context.user_data['buying_amount'] = amount
        context.user_data['buying_quantity'] = quantity
        context.user_data['payment_method'] = payment_method
        context.user_data['receipt_step'] = 'photo'

        payment_display = "KPay" if payment_method == "kpay" else "Wave Pay"
        payment_info = db["payment"][payment_display]

        keyboard = [[
            InlineKeyboardButton(f"📋 {payment_info['phone']}", callback_data=f"copy_{payment_info['phone']}")
        ], [
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data=f"quantity_{game_type}_{amount}_{quantity}")
        ]]

        price = db["prices"][game_type].get(amount, 0)
        total_price = price * quantity
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"

        await query.edit_message_text(
            f"🛒 {payment_display} ဖြင့်ဝယ်ယူရန်:\n\n"
            f"🎮 {game_name}\n"
            f"💎 {amount} {unit} x {quantity}\n"
            f"💰 စုစုပေါင်းတန်ဖိုး: {total_price} MMK\n\n"
            f"💳 {payment_display} ဖြင့်ငွေလွှဲရန်:\n"
            f"📱 ဖုန်းနံပါတ်: {payment_info['phone']}\n"
            f"👤 အမည်: {payment_info['name']}\n\n"
            f"📋 ဖုန်းနံပါတ်ကိုကူးယူရန် အပေါ်ကခလုတ်ကိုနှိပ်ပါ:\n\n"
            f"💰 လွှဲပြီးပါက screenshot နှင့်တကွ အောက်ပါအချက်အလက်များကို ပို့ပေးပါ:\n"
            f"• လွှဲငွေ ID (နောက်ဆုံး ၅လုံး သို့မဟုတ် ၆လုံး)\n"
            f"• လွှဲပို့သည့်ငွေပမာဏ\n\n"
            f"⚠️ သတိပြုရန်: လွှဲငွေ ID မှန်မှန်ကန်ကန်ပို့မှသာ ကုတ်ပေးမည်",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy_receipt_"):
        parts = data.split("_")
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])

        context.user_data['buying_game'] = game_type
        context.user_data['buying_amount'] = amount
        context.user_data['buying_quantity'] = quantity
        context.user_data['receipt_step'] = 'photo'

        keyboard = [[
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data=f"quantity_{game_type}_{amount}_{quantity}")
        ]]
        await query.edit_message_text(
            "🧾 လွှဲငွေဖြင့်ဝယ်ယူရန်:\n\n"
            "1️⃣ လွှဲငွေ screenshot ပို့ပေးပါ\n"
            "2️⃣ ပြီးလျှင် လွှဲငွေ ID (နောက်ဆုံး ၅လုံး သို့မဟုတ် ၆လုံး) ပို့ပေးပါ\n\n"
            "⚠️ သတိပြုရန်: လွှဲငွေ ID မမှန်ကန်ပါက ငွေဖြည့်မည်မဟုတ်ပါ",
            reply_markup=InlineKeyboardMarkup(keyboard))

    # Admin approval handlers
    elif data.startswith("message_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text("⚠️ Admin များသာ ဤလုပ်ဆောင်ချက်ကို အသုံးပြုနိုင်ပါသည်။")
            return

        receipt_id = data.split("_")[2]
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("⚠️ ငွေဖြည့်တောင်းဆိုမှုကို မတွေ့ပါ။")
            return

        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text("💬 အသုံးပြုသူထံသို့ပို့မည့်စာကို ရိုက်ထည့်ပါ:")

    elif data.startswith("message_") and not data.startswith("message_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text("⚠️ Admin များသာ ဤလုပ်ဆောင်ချက်ကို အသုံးပြုနိုင်ပါသည်။")
            return

        receipt_id = data.split("_")[1]
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("⚠️ လွှဲငွေကို မတွေ့ပါ။")
            return

        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text("💬 အသုံးပြုသူထံသို့ပို့မည့်စာကို ရိုက်ထည့်ပါ:")

    elif data.startswith("approve_topup_") or data.startswith("reject_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text("⚠️ Admin များသာ ဤလုပ်ဆောင်ချက်ကို အသုံးပြုနိုင်ပါသည်။")
            return

        action, _, receipt_id = data.split("_")
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("⚠️ ငွေဖြည့်တောင်းဆိုမှုကို မတွေ့ပါ။")
            return

        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        amount = request["amount"]
        user = get_user(user_id)

        if action == "approve":
            user["balance"] += amount
            request["status"] = "approved"
            save_db(db)
            await context.bot.send_message(
                user_id,
                f"✅ ငွေဖြည့်မှုကို လက်ခံပြီးပါပြီ!\n💰 ငွေပမာဏ: {amount} MMK\n💳 လက်ကျန်ငွေ: {user['balance']} MMK"
            )
            await query.edit_message_text(f"✅ ငွေဖြည့်မှု {receipt_id} ကို လက်ခံပြီးပါပြီ")
        else:
            request["status"] = "rejected"
            save_db(db)
            await context.bot.send_message(user_id, "❌ ငွေဖြည့်မှုကို ငြင်းပယ်လိုက်ပါသည်။")
            await query.edit_message_text(f"❌ ငွေဖြည့်မှု {receipt_id} ကို ငြင်းပယ်ပြီးပါပြီ")

    elif data.startswith("approve_reg_") or data.startswith("reject_reg_"):
        if uid != ADMIN_ID:
            await query.edit_message_text("⚠️ Admin များသာ ဤလုပ်ဆောင်ချက်ကို အသုံးပြုနိုင်ပါသည်။")
            return

        action, _, user_id = data.split("_")
        user_id = int(user_id)

        if user_id not in db["pending_registrations"]:
            await query.edit_message_text("⚠️ အကောင့်ဝင်ရန်တောင်းဆိုမှုကို မတွေ့ပါ။")
            return

        if action == "approve":
            # Create approved user account
            db["users"][user_id] = {
                "balance": 0,
                "history": [],
                "approved": True
            }
            del db["pending_registrations"][user_id]
            save_db(db)

            await context.bot.send_message(
                user_id,
                "✅ အကောင့်ဝင်ရန်တောင်းဆိုမှုကို လက်ခံပြီးပါပြီ! ယခု bot ကို အသုံးပြုနိုင်ပါပြီ။"
            )
            await query.edit_message_text(f"✅ အသုံးပြုသူ {user_id} ၏ အကောင့်ဝင်ရန်တောင်းဆိုမှုကို လက်ခံပြီးပါပြီ")
        else:
            del db["pending_registrations"][user_id]
            save_db(db)
            await context.bot.send_message(user_id, "❌ အကောင့်ဝင်ရန်တောင်းဆိုမှုကို ငြင်းပယ်လိုက်ပါသည်။")
            await query.edit_message_text(f"❌ အသုံးပြုသူ {user_id} ၏ အကောင့်ဝင်ရန်တောင်းဆိုမှုကို ငြင်းပယ်ပြီးပါပြီ")

    elif data.startswith("approve_") or data.startswith("reject_"):
        if uid != ADMIN_ID:
            await query.edit_message_text("⚠️ Admin များသာ ဤလုပ်ဆောင်ချက်ကို အသုံးပြုနိုင်ပါသည်။")
            return

        action, receipt_id = data.split("_")
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("⚠️ လွှဲငွေကို မတွေ့ပါ။")
            return

        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        game_type = receipt["game_type"]
        amount = receipt["amount"]
        quantity = receipt["quantity"]
        payment_method = receipt.get("payment_method", "receipt")
        user = get_user(user_id)

        # Determine payment method display name
        if payment_method == "kpay":
            payment_display = "KPay"
        elif payment_method == "wave":
            payment_display = "Wave Pay"
        else:
            payment_display = "လွှဲငွေ"

        if action == "approve":
            if len(db["stock"][game_type].get(amount, [])) < quantity:
                await query.edit_message_text("⚠️ လုံလောက်သော ကုတ်မရှိပါ။")
                return

            codes = []
            for _ in range(quantity):
                if db["stock"][game_type][amount]:
                    codes.append(db["stock"][game_type][amount].pop(0))

            total_price = db["prices"][game_type].get(amount, 0) * quantity
            db["sales_total"] += total_price
            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"

            user["history"].append({
                "type": "receipt",
                "codes": codes,
                "receipt": receipt_id,
                "game": game_name,
                "amount": amount,
                "quantity": quantity,
                "payment_method": payment_method
            })
            receipt["status"] = "approved"
            save_db(db)

            codes_text = "\n".join([f"🔑 {code}" for code in codes])
            await context.bot.send_message(
                user_id, f"✅ {payment_display} ဖြင့်ဝယ်ယူမှုကို လက်ခံပြီးပါပြီ!\n\n"
                f"🎮 {game_name}\n"
                f"💎 {amount} {unit} x {quantity}\n\n"
                f"🔑 ကုတ်များ:\n{codes_text}")
            await query.edit_message_text(f"✅ {payment_display} လွှဲငွေ {receipt_id} ကို လက်ခံပြီးပါပြီ")
        else:
            receipt["status"] = "rejected"
            save_db(db)
            await context.bot.send_message(user_id, f"❌ {payment_display} ဖြင့်ဝယ်ယူမှုကို ငြင်းပယ်လိုက်ပါသည်။")
            await query.edit_message_text(f"❌ {payment_display} လွှဲငွေ {receipt_id} ကို ငြင်းပယ်ပြီးပါပြီ")

    # Admin addstock interactive handlers
    elif data.startswith("addstock_"):
        if uid != ADMIN_ID:
            await query.edit_message_text("⚠️ Admin များသာ ဤလုပ်ဆောင်ချက်ကို အသုံးပြုနိုင်ပါသည်။")
            return

        game_type = data.split("_")[1]
        context.user_data['addstock_game'] = game_type

        keyboard = [[
            InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data="start")
        ]]
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"🎮 {game_name} အတွက် ကုတ်ထည့်ရန်:\n\n"
            f"📝 ပုံစံ: <amount> <price> <code1> <code2> ...\n"
            f"ဥပမာ: 1000 2500 CODE123 CODE456\n\n"
            f"💡 {unit} ပမာဏ, ဈေးနှုန်း, ပြီးလျှင် ကုတ်များကို ပို့ပေးပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------- Receipt/Image text handler ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user = get_user(uid)

    # Handle photos
    if update.message.photo:
        # Handle topup photos
        if 'topup_method' in context.user_data:
            context.user_data['topup_photo_sent'] = True
            context.user_data['topup_photo_message_id'] = update.message.message_id

            await update.message.reply_text(
                "🧾 လွှဲငွေ screenshot လက်ခံရရှိပါသည်။ ကျေးဇူးပြု၍ အောက်ပါအချက်အလက်များကို ပို့ပေးပါ:\n\n"
                "📝 ပုံစံ: <လွှဲငွေ ID (နောက်ဆုံး ၅လုံး သို့မဟုတ် ၆လုံး)> <ငွေပမာဏ>\n"
                "ဥပမာ: 123456 50000\n\n"
                "⚠️ သတိပြုရန်: လွှဲငွေ ID မှန်မှန်ကန်ကန်ပို့မှသာ ငွေဖြည့်ပေးမည်")
            return

        # Handle receipt purchase photos
        elif 'buying_game' in context.user_data and context.user_data.get('receipt_step') == 'photo':
            context.user_data['receipt_photo_sent'] = True
            context.user_data['receipt_photo_message_id'] = update.message.message_id
            context.user_data['receipt_step'] = 'id'

            await update.message.reply_text(
                "🧾 လွှဲငွေ screenshot လက်ခံရရှိပါသည်။ ယခု လွှဲငွေ ID (နောက်ဆုံး ၅လုံး သို့မဟုတ် ၆လုံး) ကို ပို့ပေးပါ:\n\n"
                "ဥပမာ: 123456\n\n"
                "⚠️ သတိပြုရန်: လွှဲငွေ ID မမှန်ကန်ပါက ငွေဖြည့်မည်မဟုတ်ပါ")
            return

        # Handle KPay/Wave Pay purchase photos
        elif 'payment_method' in context.user_data and context.user_data.get('receipt_step') == 'photo':
            context.user_data['receipt_photo_sent'] = True
            context.user_data['receipt_photo_message_id'] = update.message.message_id
            context.user_data['receipt_step'] = 'id'

            payment_method = context.user_data['payment_method']
            payment_display = "KPay" if payment_method == "kpay" else "Wave Pay"
            
            await update.message.reply_text(
                f"🧾 {payment_display} လွှဲငွေ screenshot လက်ခံရရှိပါသည်။ ယခု လွှဲငွေ ID (နောက်ဆုံး ၅လုံး သို့မဟုတ် ၆လုံး) ကို ပို့ပေးပါ:\n\n"
                "ဥပမာ: 123456\n\n"
                "⚠️ သတိပြုရန်: လွှဲငွေ ID မမှန်ကန်ပါက ကုတ်ပေးမည်မဟုတ်ပါ")
            return

    # Handle text messages
    if update.message.text:
        text = update.message.text.strip()

        # Handle admin message sending
        if uid == ADMIN_ID and 'admin_messaging' in context.user_data:
            target_user = context.user_data['admin_messaging']['user_id']
            await context.bot.send_message(target_user, f"📬 Admin ထံမှ စာ:\n{text}")
            await update.message.reply_text(f"✅ အသုံးပြုသူ {target_user} ထံသို့ စာပို့ပြီးပါပြီ")
            del context.user_data['admin_messaging']
            return

        # Handle quantity selection
        if 'selecting_quantity' in context.user_data:
            try:
                quantity = int(text)
                selection = context.user_data['selecting_quantity']

                if quantity < 1 or quantity > selection['max_quantity']:
                    await update.message.reply_text(f"⚠️ ကုတ်အရေအတွက်သည် 1 မှ {selection['max_quantity']} အတွင်းဖြစ်ရပါမည်။")
                    return

                game_type = selection['game_type']
                amount = selection['amount']
                price = selection['price']
                total_price = price * quantity
                user = get_user(uid)

                keyboard = []
                if user["balance"] >= total_price:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"💰 လက်ကျန်ငွေဖြင့်ဝယ်ရန် ({total_price} MMK)",
                            callback_data=f"buy_balance_{game_type}_{amount}_{quantity}")
                    ])
                else:
                    keyboard.append([InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup")])

                # Add KPay and Wave Pay payment options
                keyboard.append([
                    InlineKeyboardButton(
                        "📱 KPay ဖြင့်ဝယ်ရန်",
                        callback_data=f"buy_kpay_{game_type}_{amount}_{quantity}")
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        "📱 Wave Pay ဖြင့်ဝယ်ရန်", 
                        callback_data=f"buy_wave_{game_type}_{amount}_{quantity}")
                ])
                
                keyboard.append([
                    InlineKeyboardButton("↩️ နောက်သို့ပြန်ရန်", callback_data=f"amount_{game_type}_{amount}")
                ])

                game_name = get_game_display_name(game_type)
                unit = "Coin" if "MLBB" in game_type else "UC"
                await update.message.reply_text(
                    f"🎮 {game_name}\n"
                    f"💎 {amount} {unit} x {quantity}\n"
                    f"💰 စုစုပေါင်းတန်ဖိုး: {total_price} MMK\n"
                    f"💳 လက်ကျန်ငွေ: {user['balance']} MMK\n\n"
                    f"💳 ငွေပေးချေမှုနည်းလမ်းကိုရွေးချယ်ပါ:",
                    reply_markup=InlineKeyboardMarkup(keyboard))
                del context.user_data['selecting_quantity']
                return
            except ValueError:
                await update.message.reply_text("⚠️ ကျေးဇူးပြု၍ ကိန်းဂဏန်းသာ ရိုက်ထည့်ပါ။")
                return

        # Handle admin addstock
        if uid == ADMIN_ID and 'addstock_game' in context.user_data:
            try:
                parts = text.split()
                if len(parts) < 3:
                    await update.message.reply_text("⚠️ အသုံးပြုနည်း: <amount> <price> <code1>")
                    return

                game_type = context.user_data['addstock_game']
                amount = parts[0]
                price = int(parts[1])
                codes = parts[2:]

                # Update stock
                if game_type not in db["stock"]:
                    db["stock"][game_type] = {}
                if amount not in db["stock"][game_type]:
                    db["stock"][game_type][amount] = []
                db["stock"][game_type][amount].extend(codes)

                # Update price
                if game_type not in db["prices"]:
                    db["prices"][game_type] = {}
                db["prices"][game_type][amount] = price

                save_db(db)

                game_name = get_game_display_name(game_type)
                unit = "Coin" if "MLBB" in game_type else "UC"
                await update.message.reply_text(
                    f"✅ {game_name} {amount} {unit}\n"
                    f"💰 ဈေးနှုန်း: {price} MMK\n"
                    f"📦 ကုတ်: {len(codes)} ခု ထည့်ပြီးပါပြီ")
                del context.user_data['addstock_game']
                return
            except ValueError:
                await update.message.reply_text("⚠️ ဈေးနှုန်းသည် မှားယွင်းနေပါသည်။")
                return
            except:
                await update.message.reply_text("⚠️ ပုံစံသည် မှားယွင်းနေပါသည်။")
                return

        # Handle topup with receipt ID and amount
        if context.user_data.get('topup_photo_sent'):
            try:
                parts = text.split()
                if len(parts) != 2:
                    await update.message.reply_text("⚠️ ပုံစံ: <လွှဲငွေ ID> <ငွေပမာဏ>")
                    return

                receipt_id = parts[0]
                amount = int(parts[1])

                if not validate_receipt_id(receipt_id):
                    await update.message.reply_text("⚠️ လွှဲငွေ ID သည် ၅လုံး သို့မဟုတ် ၆လုံး ကိန်းဂဏန်းဖြစ်ရပါမည်။")
                    return

                if amount < 1000:
                    await update.message.reply_text("⚠️ ငွေပမာဏသည် မှားယွင်းနေပါသည်။ အနည်းဆုံး ၁၀၀၀ MMK ဖြစ်ရပါမည်။")
                    return

                payment_method = context.user_data['topup_method']
                photo_message_id = context.user_data['topup_photo_message_id']

                db["topup_requests"][receipt_id] = {
                    "user_id": uid,
                    "status": "pending",
                    "amount": amount,
                    "payment_method": payment_method
                }
                save_db(db)

                keyboard = [[
                    InlineKeyboardButton("✅ လက်ခံရန်", callback_data=f"approve_topup_{receipt_id}"),
                    InlineKeyboardButton("💬 စာပို့ရန်", callback_data=f"message_topup_{receipt_id}"),
                    InlineKeyboardButton("❌ ငြင်းပယ်ရန်", callback_data=f"reject_topup_{receipt_id}")
                ]]

                await context.bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=update.message.chat.id,
                    message_id=photo_message_id)

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📬 ငွေဖြည့်တောင်းဆိုမှုအသစ်:\n"
                    f"👤 အသုံးပြုသူ: {uid}\n"
                    f"💳 နည်းလမ်း: {payment_method}\n"
                    f"🧾 လွှဲငွေ ID: {receipt_id}\n"
                    f"💰 ငွေပမာဏ: {amount} MMK",
                    reply_markup=InlineKeyboardMarkup(keyboard))

                await update.message.reply_text("⏳ Admin မှ စစ်ဆေးနေပါသည်...")

                # Clear user data
                del context.user_data['topup_method']
                del context.user_data['topup_photo_sent']
                del context.user_data['topup_photo_message_id']
                return
            except ValueError:
                await update.message.reply_text("⚠️ ငွေပမာဏသည် မှားယွင်းနေပါသည်။")
                return
            except:
                await update.message.reply_text("⚠️ ပုံစံသည် မှားယွင်းနေပါသည်။")
                return

        # Handle receipt purchase with receipt ID (for both direct receipt and KPay/Wave Pay)
        if ('buying_game' in context.user_data and context.user_data.get('receipt_step') == 'id') or \
           ('payment_method' in context.user_data and context.user_data.get('receipt_step') == 'id'):
            
            if not validate_receipt_id(text):
                await update.message.reply_text("⚠️ လွှဲငွေ ID သည် ၅လုံး သို့မဟုတ် ၆လုံး ကိန်းဂဏန်းဖြစ်ရပါမည်။")
                return

            # Get purchase details based on the method
            if 'payment_method' in context.user_data:
                # KPay/Wave Pay purchase
                game_type = context.user_data['buying_game']
                amount = context.user_data['buying_amount']
                quantity = context.user_data['buying_quantity']
                payment_method = context.user_data['payment_method']
                purchase_type = "kpay_wave"
            else:
                # Direct receipt purchase (existing)
                game_type = context.user_data['buying_game']
                amount = context.user_data['buying_amount']
                quantity = context.user_data['buying_quantity']
                payment_method = "receipt"
                purchase_type = "receipt"

            photo_message_id = context.user_data['receipt_photo_message_id']

            # Save to receipts database
            db["receipts"][text] = {
                "user_id": uid,
                "status": "pending",
                "game_type": game_type,
                "amount": amount,
                "quantity": quantity,
                "payment_method": payment_method,
                "purchase_type": purchase_type
            }
            save_db(db)

            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"
            
            # Determine payment method display name
            if payment_method == "kpay":
                payment_display = "KPay"
            elif payment_method == "wave":
                payment_display = "Wave Pay"
            else:
                payment_display = "လွှဲငွေ"

            keyboard = [[
                InlineKeyboardButton("✅ လက်ခံရန်", callback_data=f"approve_{text}"),
                InlineKeyboardButton("💬 စာပို့ရန်", callback_data=f"message_{text}"),
                InlineKeyboardButton("❌ ငြင်းပယ်ရန်", callback_data=f"reject_{text}")
            ]]

            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.message.chat.id,
                message_id=photo_message_id)

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📬 ကုတ်ဝယ်ယူမှု ({payment_display}):\n"
                f"👤 အသုံးပြုသူ: {uid}\n"
                f"🎮 ဂိမ်း: {game_name}\n"
                f"💎 {amount} {unit} x {quantity}\n"
                f"🧾 လွှဲငွေ ID: {text}\n"
                f"💳 နည်းလမ်း: {payment_display}",
                reply_markup=InlineKeyboardMarkup(keyboard))
            
            await update.message.reply_text("⏳ Admin မှ စစ်ဆေးနေပါသည်...")

            # Clear user data
            keys_to_delete = [
                'buying_game', 'buying_amount', 'buying_quantity', 
                'receipt_photo_sent', 'receipt_photo_message_id', 'receipt_step'
            ]
            for key in keys_to_delete:
                if key in context.user_data:
                    del context.user_data[key]
            
            # Clear payment method if exists
            if 'payment_method' in context.user_data:
                del context.user_data['payment_method']
            return


# ---------------- Admin Commands ----------------
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        args = context.args
        uid = int(args[0])
        amount = int(args[1])
        user = get_user(uid)
        user["balance"] = amount
        save_db(db)
        await update.message.reply_text(f"✅ အသုံးပြုသူ {uid} ၏ လက်ကျန်ငွေကို {amount} MMK သို့ပြောင်းပြီးပါပြီ")
    except:
        await update.message.reply_text("အသုံးပြုနည်း: /setbalance <user_id> <amount>")


async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # Interactive version
    keyboard = [[
        InlineKeyboardButton("🎮 Mobile Legends (Bal)", callback_data="addstock_MLBBbal")
    ], [
        InlineKeyboardButton("🎮 Mobile Legends (PH)", callback_data="addstock_MLBBph")
    ], [
        InlineKeyboardButton("🎮 PUPG Mobile", callback_data="addstock_PUPG")
    ]]
    await update.message.reply_text(
        "🎮 ဂိမ်းအမျိုးအစားရွေးချယ်ပါ:",
        reply_markup=InlineKeyboardMarkup(keyboard))


async def delstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 3:
        await update.message.reply_text("အသုံးပြုနည်း: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")
        return

    try:
        game_type = context.args[0]
        amount = context.args[1]
        code_to_delete = context.args[2]

        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text("ဂိမ်းအမျိုးအစား: MLBBbal, MLBBph, သို့မဟုတ် PUPG")
            return

        if game_type not in db["stock"] or amount not in db["stock"][game_type]:
            await update.message.reply_text("⚠️ ဒီဂိမ်းအမျိုးအစား သို့မဟုတ် ပမာဏ မရှိပါ။")
            return

        if code_to_delete in db["stock"][game_type][amount]:
            db["stock"][game_type][amount].remove(code_to_delete)
            save_db(db)

            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"
            await update.message.reply_text(f"✅ {game_name} {amount} {unit} မှ ကုတ် {code_to_delete} ကို ဖျက်ပြီးပါပြီ")
        else:
            await update.message.reply_text("⚠️ ဒီကုတ်ကို မတွေ့ပါ။")
    except:
        await update.message.reply_text("အသုံးပြုနည်း: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")


async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 3:
        await update.message.reply_text("အသုံးပြုနည်း: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")
        return

    try:
        game_type = context.args[0]
        amount = context.args[1]
        price = int(context.args[2])

        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text("ဂိမ်းအမျိုးအစား: MLBBbal, MLBBph, သို့မဟုတ် PUPG")
            return

        if game_type not in db["prices"]:
            db["prices"][game_type] = {}

        db["prices"][game_type][amount] = price
        save_db(db)

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await update.message.reply_text(f"✅ {game_name} {amount} {unit} ၏ ဈေးနှုန်းကို {price} MMK အဖြစ်သတ်မှတ်ပြီးပါပြီ")
    except:
        await update.message.reply_text("အသုံးပြုနည်း: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")


async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        method = context.args[0].title()
        phone = context.args[1]
        name = " ".join(context.args[2:])

        if method not in ["Wave", "Kpay"]:
            await update.message.reply_text("ငွေပေးချေမှုနည်းလမ်း: Wave သို့မဟုတ် KPay")
            return

        db["payment"][method] = {"phone": phone, "name": name}
        save_db(db)
        await update.message.reply_text(
            f"✅ {method} ပေးချေမှုအချက်အလက်ကို ပြင်ဆင်ပြီးပါပြီ\n📱 ဖုန်း: {phone}\n👤 အမည်: {name}"
        )
    except:
        await update.message.reply_text("အသုံးပြုနည်း: /setpayment <Wave/KPay> <phone> <name>")


async def viewhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        user = get_user(uid)
        if not user["history"]:
            await update.message.reply_text(f"အသုံးပြုသူ {uid} ၏ မှတ်တမ်းမရှိပါ")
            return

        history_text = ""
        for i, h in enumerate(user["history"], 1):
            history_text += f"{i}. {h}\n"

        await update.message.reply_text(f"📜 အသုံးပြုသူ {uid} ၏ မှတ်တမ်း:\n{history_text}")
    except:
        await update.message.reply_text("အသုံးပြုနည်း: /viewhistory <user_id>")


async def admhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # Calculate stock counts
    mlbbbal_count = sum(len(codes) for codes in db["stock"].get("MLBBbal", {}).values())
    mlbbph_count = sum(len(codes) for codes in db["stock"].get("MLBBph", {}).values())
    pupg_count = sum(len(codes) for codes in db["stock"].get("PUPG", {}).values())

    # Calculate total orders
    total_orders = 0
    for user_data in db["users"].values():
        total_orders += len(user_data.get("history", []))

    # Calculate total user balance
    total_user_balance = sum(user_data.get("balance", 0) for user_data in db["users"].values())

    # Calculate pending counts (only pending status)
    pending_receipts = len([r for r in db["receipts"].values() if r["status"] == "pending"])
    pending_topups = len([r for r in db["topup_requests"].values() if r["status"] == "pending"])
    pending_registrations = len(db.get("pending_registrations", {}))

    help_text = f"""
🛠️ Admin Commands:

/setbalance <user_id> <amount> - အသုံးပြုသူငွေစစ်ရန်
/addstock - ကုတ်များထည့်ရန် (အပြန်အလှန်)
/delstock <MLBBbal/MLBBph/PUPG> <amount> <code> - ကုတ်ဖျက်ရန်
/setprice <MLBBbal/MLBBph/PUPG> <amount> <price> - ဈေးနှုန်းသတ်မှတ်ရန်
/setpayment <Wave/Kpay> <phone> <name> - ပေးချေမှုအချက်အလက်ပြင်ရန်
/viewhistory <user_id> - အသုံးပြုသူမှတ်တမ်းကြည့်ရန်
/admhelp - ဤအကူအညီစာကိုပြရန်

📊 အချက်အလက်အကျဉ်းချုပ်:
🎮 MLBB Bal ကုတ်: {mlbbbal_count}
🎮 MLBB PH ကုတ်: {mlbbph_count}
🎮 PUPG ကုတ်: {pupg_count}
👥 အသုံးပြုသူ: {len(db["users"])}
📦 အော်ဒါစုစုပေါင်း: {total_orders}
💰 အသုံးပြုသူငွေစုစုပေါင်း: {total_user_balance:,} MMK
💹 ရောင်းရငွေစုစုပေါင်း: {db.get('sales_total', 0):,} MMK
⏳ စစ်ဆေးရန်လွှဲငွေ: {pending_receipts}
⏳ စစ်ဆေးရန်ငွေဖြည့်: {pending_topups}
⏳ စစ်ဆေးရန်အကောင့်ဝင်: {pending_registrations}

💡 ဥပမာကုဒ်များ:
/setprice MLBBbal 1000 2500
/setprice PUPG 60 1500
/delstock MLBBbal 1000 CODE123
/setpayment Kpay 09123456789 John Doe

🛠️ နောက်ထပ်ကုဒ်များ:
• အကောင့်ဝင်ရန် Admin လက်ခံမှသာအသုံးပြုနိုင်မည်
• ကုတ်အရေအတွက်များကို စစ်ဆေး၍ စာပြန်ပေးနိုင်သည်
• Admin ကို စာပို့နိုင်သည် (💬 ခလုတ်)
    """

    await update.message.reply_text(help_text)


# ---------------- Main ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("addstock", addstock))
    app.add_handler(CommandHandler("delstock", delstock))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(CommandHandler("setpayment", setpayment))
    app.add_handler(CommandHandler("viewhistory", viewhistory))
    app.add_handler(CommandHandler("admhelp", admhelp))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
