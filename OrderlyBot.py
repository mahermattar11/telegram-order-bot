import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import sqlite3
from flask import Flask  # ← مكتبة Flask المضافة
import threading  # ← لتشغيل Flask في الخلفية

# ================= FLASK SERVER =================
# إنشاء تطبيق Flask بسيط للـ Health Check
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "✅ Bot is running!", 200

@web_app.route('/health')
def health():
    return "🟢 Healthy", 200

def run_flask():
    """تشغيل Flask على منفذ 10000"""
    web_app.run(host='0.0.0.0', port=10000, debug=False)

# تشغيل Flask في خيط منفصل
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
print("✅ Flask health check server started on port 10000")

# ================= BOT SETTINGS =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5812937391

# ================= DATABASE =================
conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    product TEXT,
    name TEXT,
    phone TEXT,
    address TEXT,
    quantity TEXT,
    size TEXT,
    language TEXT
)
""")
conn.commit()

# ================= TEXTS =================
TEXT = {
    "lang": {
        "ar": "اختر نوع النشاط:",
        "en": "Choose business type:"
    },
    "category": {
        "ar": ["🍔 طعام", "👕 ملابس"],
        "en": ["🍔 Food", "👕 Clothing"]
    },
    "ask_product": {
        "ar": "اختر المنتج:",
        "en": "Choose product:"
    },
    "ask_name": {
        "ar": "اكتب اسمك:",
        "en": "Enter your name:"
    },
    "ask_phone": {
        "ar": "اكتب رقم الهاتف:",
        "en": "Enter phone number:"
    },
    "ask_address": {
        "ar": "اكتب العنوان:",
        "en": "Enter address:"
    },
    "ask_quantity": {
        "ar": "اكتب الكمية:",
        "en": "Enter quantity:"
    },
    "ask_size": {
        "ar": "اكتب المقاس:",
        "en": "Enter size:"
    },
    "confirm": {
        "ar": "✅ تم استلام طلبك، سنتواصل معك قريبًا",
        "en": "✅ Order received, we will contact you soon"
    }
}

PRODUCTS = {
    "food": ["🍕 Pizza", "🍔 Burger", "🥗 Salad"],
    "clothing": ["👕 T-Shirt", "👖 Jeans", "🧥 Jacket"]
}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
        ]
    ]
    await update.message.reply_text(
        "اختر اللغة / Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CALLBACK =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # Language
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        context.user_data["lang"] = lang

        keyboard = [
            [
                InlineKeyboardButton(TEXT["category"][lang][0], callback_data="cat_food"),
                InlineKeyboardButton(TEXT["category"][lang][1], callback_data="cat_clothing")
            ]
        ]
        await query.edit_message_text(
            TEXT["lang"][lang],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Category
    elif data.startswith("cat_"):
        category = data.split("_")[1]
        context.user_data["category"] = category
        lang = context.user_data["lang"]

        keyboard = [
            [InlineKeyboardButton(p, callback_data=f"prod_{p}")]
            for p in PRODUCTS[category]
        ]

        await query.edit_message_text(
            TEXT["ask_product"][lang],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Product
    elif data.startswith("prod_"):
        product = data.replace("prod_", "")
        context.user_data["product"] = product
        lang = context.user_data["lang"]

        await query.edit_message_text(TEXT["ask_name"][lang])
        context.user_data["step"] = "name"

# ================= MESSAGES =================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    lang = context.user_data.get("lang")

    if step == "name":
        context.user_data["name"] = update.message.text
        await update.message.reply_text(TEXT["ask_phone"][lang])
        context.user_data["step"] = "phone"

    elif step == "phone":
        context.user_data["phone"] = update.message.text
        await update.message.reply_text(TEXT["ask_address"][lang])
        context.user_data["step"] = "address"

    elif step == "address":
        context.user_data["address"] = update.message.text
        await update.message.reply_text(TEXT["ask_quantity"][lang])
        context.user_data["step"] = "quantity"

    elif step == "quantity":
        context.user_data["quantity"] = update.message.text
        if context.user_data["category"] == "clothing":
            await update.message.reply_text(TEXT["ask_size"][lang])
            context.user_data["step"] = "size"
        else:
            await save_order(update, context)

    elif step == "size":
        context.user_data["size"] = update.message.text
        await save_order(update, context)

# ================= SAVE ORDER =================
async def save_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data

    cursor.execute("""
    INSERT INTO orders
    (category, product, name, phone, address, quantity, size, language)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["category"],
        data["product"],
        data["name"],
        data["phone"],
        data["address"],
        data["quantity"],
        data.get("size", ""),
        data["lang"]
    ))
    conn.commit()

    await update.message.reply_text(TEXT["confirm"][data["lang"]])

    # Notify admin
    msg = f"""
📦 New Order
Type: {data['category']}
Product: {data['product']}
Name: {data['name']}
Phone: {data['phone']}
Address: {data['address']}
Quantity: {data['quantity']}
Size: {data.get('size', '-')}
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg)

    context.user_data.clear()

# ================= RUN BOT =================
def main():
    print("🚀 Starting OrderlyBot with Flask health check...")
    
    # إنشاء وتشغيل البوت
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("✅ Bot is running...")
    app.run_polling()

# ================= START EVERYTHING =================
if __name__ == '__main__':
    main()