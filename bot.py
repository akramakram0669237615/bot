"""
بوت تيليغرام للتجار — متجري
يعمل مع API: http://dzify.gt.tc/api/index.php

pip install pyTelegramBotAPI requests
"""

import telebot
import requests
import json
import threading
import time

# ══════════════════════════════════════════════
#  الإعدادات — غيّر هذه القيم فقط
# ══════════════════════════════════════════════
BOT_TOKEN = "8798266830:AAEjvy6HZnbb_z4ZWPWaEWQoOA80D1sWAUg"   # من @BotFather
API_URL   = "http://dzify.gt.tc/api/index.php"

# ══════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# حفظ بيانات المستخدمين في الذاكرة
# { chat_id: { token, store_name, user_name, last_order_id } }
users = {}

# ══════════════════════════════════════════════
#  ألوان الحالات
# ══════════════════════════════════════════════
STATUS_AR = {
    "pending":   "🟡 جديد",
    "confirmed": "🔵 مؤكد",
    "shipped":   "🟣 مشحون",
    "delivered": "🟢 مُسلَّم",
    "cancelled": "🔴 ملغي",
    "returned":  "⚫ مُعاد",
}

STATUS_KEYS = list(STATUS_AR.keys())

# ══════════════════════════════════════════════
#  API Helpers
# ══════════════════════════════════════════════
def api_post(route, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(
            f"{API_URL}?route={route}",
            json=body, headers=headers, timeout=10
        )
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def api_get(route, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(
            f"{API_URL}?route={route}",
            headers=headers, timeout=10
        )
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def api_patch(route, body, token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        r = requests.patch(
            f"{API_URL}?route={route}",
            json=body, headers=headers, timeout=10
        )
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ══════════════════════════════════════════════
#  لوحة المفاتيح
# ══════════════════════════════════════════════
def main_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📦 طلباتي", "🆕 الطلبات الجديدة")
    kb.row("📊 إحصائيات", "🔄 تحديث")
    kb.row("🚪 تسجيل الخروج")
    return kb

def status_keyboard(order_id):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for key, label in STATUS_AR.items():
        btns.append(
            telebot.types.InlineKeyboardButton(
                label, callback_data=f"status:{order_id}:{key}"
            )
        )
    kb.add(*btns)
    kb.add(telebot.types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel"))
    return kb

def orders_keyboard(orders):
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for o in orders[:10]:  # أول 10 طلبات
        label = f"{STATUS_AR.get(o['status'],'?')} | {o['order_ref']} — {o['customer_name']}"
        kb.add(telebot.types.InlineKeyboardButton(
            label, callback_data=f"order:{o['id']}"
        ))
    return kb

# ══════════════════════════════════════════════
#  تنسيق رسائل الطلبات
# ══════════════════════════════════════════════
def format_order(o):
    status = STATUS_AR.get(o.get("status", ""), "❓ غير معروف")
    loc    = " • ".join(filter(None, [o.get("wilaya_name"), o.get("commune_name")])) or "—"
    dlv    = "🏠 منزل" if o.get("delivery_type") == "home" else "🏢 مكتب"
    total  = float(o.get("total", 0))

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 <b>{o.get('order_ref', '—')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>الزبون:</b> {o.get('customer_name', '—')}\n"
        f"📞 <b>الهاتف:</b> {o.get('customer_phone', '—')}\n"
        f"📍 <b>العنوان:</b> {loc}\n"
        f"🚚 <b>التوصيل:</b> {dlv}\n"
        f"💰 <b>الإجمالي:</b> {total:,.0f} دج\n"
        f"📋 <b>الحالة:</b> {status}\n"
        f"🕐 <b>التاريخ:</b> {o.get('created_at', '—')[:10]}\n"
    )

def format_order_detail(o):
    items = o.get("items", [])
    items_text = ""
    for item in items:
        name  = item.get("product_name") or item.get("name", "—")
        qty   = item.get("qty", 1)
        price = float(item.get("line_total") or item.get("price", 0))
        var   = f"\n    ↳ {item['variant_info']}" if item.get("variant_info") else ""
        items_text += f"  • {name} × {qty} = {price:,.0f} دج{var}\n"

    status = STATUS_AR.get(o.get("status", ""), "❓")
    loc    = " • ".join(filter(None, [o.get("wilaya_name"), o.get("commune_name")])) or "—"
    dlv    = "🏠 منزل" if o.get("delivery_type") == "home" else "🏢 مكتب"

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 <b>{o.get('order_ref','—')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>الزبون:</b> {o.get('customer_name','—')}\n"
        f"📞 <b>الهاتف:</b> <a href='tel:{o.get('customer_phone','')}'>{o.get('customer_phone','—')}</a>\n"
        f"📍 <b>العنوان:</b> {loc}\n"
        f"🚚 <b>التوصيل:</b> {dlv}\n"
        f"{'🎁 <b>كود خصم:</b> ' + o['promo_code'] + chr(10) if o.get('promo_code') else ''}"
        f"\n🛍 <b>المنتجات:</b>\n{items_text or '  لا توجد منتجات\n'}"
        f"\n💵 المجموع الفرعي: {float(o.get('subtotal',0)):,.0f} دج\n"
        f"📦 الشحن: {float(o.get('shipping_price',0)):,.0f} دج\n"
        f"💰 <b>الإجمالي: {float(o.get('total',0)):,.0f} دج</b>\n"
        f"\n📋 <b>الحالة:</b> {status}\n"
        f"🕐 <b>التاريخ:</b> {o.get('created_at','—')[:10]}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

# ══════════════════════════════════════════════
#  حالة تسجيل الدخول المؤقتة
# ══════════════════════════════════════════════
# { chat_id: "waiting_email" | "waiting_password" }
login_state = {}
login_temp  = {}  # { chat_id: email }

# ══════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    cid = msg.chat.id
    if cid in users:
        u = users[cid]
        bot.send_message(cid,
            f"👋 مرحباً <b>{u['user_name']}</b>!\n"
            f"🏪 متجرك: <b>{u['store_name']}</b>\n\n"
            f"اختر ما تريد:",
            reply_markup=main_keyboard()
        )
    else:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login"))
        bot.send_message(cid,
            "👋 <b>مرحباً في بوت متجري!</b>\n\n"
            "📲 هذا البوت يتيح لك:\n"
            "• استقبال إشعارات الطلبات الجديدة فوراً\n"
            "• عرض قائمة طلباتك\n"
            "• تغيير حالة أي طلب\n\n"
            "اضغط <b>تسجيل الدخول</b> للبدء:",
            reply_markup=kb
        )

# ══════════════════════════════════════════════
#  Callback Queries
# ══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    cid  = call.message.chat.id
    data = call.data

    # ── بدء تسجيل الدخول
    if data == "login":
        login_state[cid] = "waiting_email"
        bot.answer_callback_query(call.id)
        bot.send_message(cid, "📧 أرسل <b>البريد الإلكتروني</b> الخاص بحسابك:")
        return

    # ── إلغاء
    if data == "cancel":
        bot.answer_callback_query(call.id, "تم الإلغاء")
        bot.delete_message(cid, call.message.message_id)
        return

    # ── فتح تفاصيل طلب
    if data.startswith("order:"):
        order_id = data.split(":")[1]
        bot.answer_callback_query(call.id, "⏳ جاري التحميل...")
        show_order_detail(cid, order_id)
        return

    # ── تغيير حالة طلب
    if data.startswith("status:"):
        _, order_id, new_status = data.split(":")
        bot.answer_callback_query(call.id, "⏳ جاري التحديث...")
        do_update_status(cid, call.message, order_id, new_status)
        return

# ══════════════════════════════════════════════
#  رسائل النص
# ══════════════════════════════════════════════
@bot.message_handler(func=lambda m: True)
def on_message(msg):
    cid  = msg.chat.id
    text = msg.text.strip() if msg.text else ""

    # ── مراحل تسجيل الدخول
    if cid in login_state:
        handle_login_step(cid, text)
        return

    # ── التاجر غير مسجّل
    if cid not in users:
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="login"))
        bot.send_message(cid, "⚠️ يجب تسجيل الدخول أولاً:", reply_markup=kb)
        return

    token = users[cid]["token"]

    # ── أوامر القائمة
    if text in ["📦 طلباتي", "/orders"]:
        send_orders_list(cid, token)

    elif text in ["🆕 الطلبات الجديدة", "/new"]:
        send_orders_list(cid, token, status="pending")

    elif text in ["📊 إحصائيات", "/stats"]:
        send_stats(cid, token)

    elif text in ["🔄 تحديث", "/refresh"]:
        bot.send_message(cid, "🔄 جاري التحديث...")
        send_orders_list(cid, token)

    elif text in ["🚪 تسجيل الخروج", "/logout"]:
        do_logout(cid)

    else:
        bot.send_message(cid,
            "اختر من القائمة أدناه 👇",
            reply_markup=main_keyboard()
        )

# ══════════════════════════════════════════════
#  خطوات تسجيل الدخول
# ══════════════════════════════════════════════
def handle_login_step(cid, text):
    state = login_state.get(cid)

    if state == "waiting_email":
        if "@" not in text or "." not in text:
            bot.send_message(cid, "❌ البريد غير صحيح، أعد المحاولة:")
            return
        login_temp[cid] = text
        login_state[cid] = "waiting_password"
        bot.send_message(cid, "🔑 أرسل <b>كلمة المرور</b>:")

    elif state == "waiting_password":
        email    = login_temp.get(cid, "")
        password = text
        bot.send_message(cid, "⏳ جاري التحقق...")

        resp = api_post("auth/login", {"email": email, "password": password})

        if resp.get("status") == "success":
            data = resp["data"]
            users[cid] = {
                "token":      data["token"],
                "store_name": data["store"]["name"],
                "user_name":  data["user"]["name"],
                "store_id":   data["store"]["id"],
                "last_order_id": 0,
            }
            login_state.pop(cid, None)
            login_temp.pop(cid, None)

            bot.send_message(cid,
                f"✅ <b>تم تسجيل الدخول بنجاح!</b>\n\n"
                f"👤 <b>الاسم:</b> {data['user']['name']}\n"
                f"🏪 <b>المتجر:</b> {data['store']['name']}\n\n"
                f"ستصلك إشعارات الطلبات الجديدة تلقائياً 🔔",
                reply_markup=main_keyboard()
            )
            # جلب الطلبات فوراً
            send_orders_list(cid, data["token"])
        else:
            login_state.pop(cid, None)
            login_temp.pop(cid, None)
            msg_err = resp.get("message", "فشل تسجيل الدخول")
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("🔄 حاول مجدداً", callback_data="login"))
            bot.send_message(cid, f"❌ <b>{msg_err}</b>", reply_markup=kb)

# ══════════════════════════════════════════════
#  عرض الطلبات
# ══════════════════════════════════════════════
def send_orders_list(cid, token, status=None):
    route = "orders?limit=20"
    if status:
        route += f"&status={status}"

    resp = api_get(route, token)
    if resp.get("status") != "success":
        bot.send_message(cid, "❌ تعذّر جلب الطلبات")
        return

    orders = resp.get("data", {}).get("orders", [])
    total  = resp.get("data", {}).get("pagination", {}).get("total", 0)

    if not orders:
        lbl = f" بحالة ({STATUS_AR.get(status,'')})" if status else ""
        bot.send_message(cid, f"📭 لا توجد طلبات{lbl}")
        return

    title = f"🆕 الطلبات الجديدة" if status == "pending" else f"📦 طلباتك الأخيرة"
    bot.send_message(cid,
        f"{title} ({total} طلب إجمالاً)\n"
        f"اضغط على أي طلب لعرض تفاصيله:",
        reply_markup=orders_keyboard(orders)
    )

# ══════════════════════════════════════════════
#  تفاصيل طلب
# ══════════════════════════════════════════════
def show_order_detail(cid, order_id):
    if cid not in users:
        return
    token = users[cid]["token"]
    resp  = api_get(f"orders/{order_id}", token)

    if resp.get("status") != "success":
        bot.send_message(cid, "❌ تعذّر جلب تفاصيل الطلب")
        return

    order = resp["data"]
    text  = format_order_detail(order)

    bot.send_message(cid, text,
        reply_markup=status_keyboard(order_id),
        disable_web_page_preview=True
    )

# ══════════════════════════════════════════════
#  تحديث الحالة
# ══════════════════════════════════════════════
def do_update_status(cid, msg, order_id, new_status):
    if cid not in users:
        return
    token = users[cid]["token"]
    resp  = api_patch(f"orders/{order_id}/status", {"status": new_status}, token)

    if resp.get("status") == "success":
        label = STATUS_AR.get(new_status, new_status)
        try:
            bot.edit_message_reply_markup(cid, msg.message_id, reply_markup=None)
        except:
            pass
        bot.send_message(cid,
            f"✅ <b>تم تحديث الحالة بنجاح!</b>\n"
            f"🧾 الطلب #{order_id}\n"
            f"📋 الحالة الجديدة: {label}"
        )
    else:
        bot.send_message(cid,
            f"❌ فشل التحديث: {resp.get('message','خطأ غير معروف')}"
        )

# ══════════════════════════════════════════════
#  إحصائيات
# ══════════════════════════════════════════════
def send_stats(cid, token):
    resp = api_get("orders?limit=100", token)
    if resp.get("status") != "success":
        bot.send_message(cid, "❌ تعذّر جلب الإحصائيات")
        return

    orders = resp.get("data", {}).get("orders", [])
    total  = resp.get("data", {}).get("pagination", {}).get("total", 0)

    counts = {}
    revenue = 0
    for o in orders:
        s = o.get("status", "")
        counts[s] = counts.get(s, 0) + 1
        if s == "delivered":
            revenue += float(o.get("total", 0))

    lines = "\n".join(
        f"{STATUS_AR.get(k,'?')}: <b>{v}</b>"
        for k, v in counts.items()
    )

    bot.send_message(cid,
        f"📊 <b>إحصائيات متجرك</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 إجمالي الطلبات: <b>{total}</b>\n\n"
        f"{lines}\n\n"
        f"💰 إيرادات المُسلَّم: <b>{revenue:,.0f} دج</b>"
    )

# ══════════════════════════════════════════════
#  تسجيل الخروج
# ══════════════════════════════════════════════
def do_logout(cid):
    name = users.get(cid, {}).get("user_name", "")
    users.pop(cid, None)
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🔐 تسجيل الدخول مجدداً", callback_data="login"))
    bot.send_message(cid,
        f"👋 وداعاً <b>{name}</b>!\nتم تسجيل الخروج بنجاح.",
        reply_markup=kb
    )

# ══════════════════════════════════════════════
#  مراقبة الطلبات الجديدة (كل 30 ثانية)
# ══════════════════════════════════════════════
def watch_new_orders():
    while True:
        time.sleep(30)
        for cid, u in list(users.items()):
            try:
                resp = api_get("orders?limit=5&status=pending", u["token"])
                if resp.get("status") != "success":
                    continue
                orders = resp.get("data", {}).get("orders", [])
                for o in orders:
                    oid = o["id"]
                    if oid > u.get("last_order_id", 0):
                        users[cid]["last_order_id"] = oid
                        text = (
                            f"🔔 <b>طلب جديد وصل!</b>\n\n"
                            + format_order(o)
                        )
                        kb = telebot.types.InlineKeyboardMarkup()
                        kb.add(telebot.types.InlineKeyboardButton(
                            "📋 عرض التفاصيل وتغيير الحالة",
                            callback_data=f"order:{oid}"
                        ))
                        bot.send_message(cid, text, reply_markup=kb)
            except Exception as e:
                print(f"خطأ في المراقبة: {e}")

# ══════════════════════════════════════════════
#  تشغيل البوت
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("✅ البوت يعمل...")
    # تشغيل مراقبة الطلبات في خلفية منفصلة
    t = threading.Thread(target=watch_new_orders, daemon=True)
    t.start()
    # تشغيل البوت
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
