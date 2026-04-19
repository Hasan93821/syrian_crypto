import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          ConversationHandler, MessageHandler, filters, ContextTypes)
from telegram.helpers import escape_markdown
from datetime import timedelta, datetime, time
import re
import pytz

from config import (BOT_TOKEN, ADMIN_CHAT_ID, USDT_CWALLET_ADDRESS,
                    USDT_BINANCE_ADDRESS, USDT_EXTERNAL_ADDRESS,
                    SHAM_CASH_NUMBER, SYRIATEL_CASH_NUMBER, PAYER_ACCOUNT,
                    BANK_TRANSFER_DETAILS, WEBHOOK_URL, WEBHOOK_PORT,
                    WEBHOOK_LISTEN, WEBHOOK_CERT, WEBHOOK_KEY)

from reg import (register_bot_callback, receive_full_name, receive_address,
                 receive_phone_number, cancel_registration, start_edit_registration,
                 ASKING_FULL_NAME, ASKING_ADDRESS, ASKING_PHONE_NUMBER, CONFIRM_EDIT,
                 init_db, get_user_data, update_wallet_balance, update_investment_balance,
                 get_all_users_data, update_subscription_status, get_subscription_info,
                 update_subscribed_pairs, update_daily_recommendations_count)

from deposit import (SELECT_DEPOSIT_METHOD, ASKING_DEPOSIT_AMOUNT, ENTER_DEPOSIT_TXID,
                     SELECT_WITHDRAW_METHOD, ASKING_WITHDRAW_AMOUNT, ASKING_WITHDRAW_ACCOUNT_DETAILS,
                     ASKING_INVEST_AMOUNT,
                     send_admin_notification, start_deposit, select_deposit_method,
                     select_usdt_wallet_type, receive_deposit_amount, enter_deposit_txid,
                     cancel_deposit, start_withdraw, select_withdraw_method,
                     select_usdt_withdraw_wallet_type, receive_withdraw_amount,
                     receive_withdraw_account_details,
                     cancel_withdraw, start_invest_in_bot, receive_invest_amount, cancel_invest)

from admin_panel import (ADMIN_MENU, SEND_MESSAGE_TO_ALL, GET_USER_ID_FOR_WALLET, GET_WALLET_AMOUNT,
                         GET_USER_ID_FOR_INVESTMENT, GET_INVESTMENT_AMOUNT,
                         admin_control_panel, handle_admin_callback, handle_admin_message_input,
                         handle_transaction_callback, admin_show_users_paginated, admin_view_user_details)

from subscriptions import (SELECT_SUBSCRIPTION_PLAN, SELECT_TRADING_PAIRS, CONFIRM_SUBSCRIPTION,
                           start_subscription_process, select_subscription_plan,
                           send_pair_selection_message, select_trading_pairs,
                           send_confirmation_message, confirm_subscription, cancel_subscription,
                           check_and_send_daily_recommendations)

from trading_data import (get_all_usdt_pairs, get_crypto_data, generate_trading_signal, format_signal)


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def set_my_commands(application: Application):
    """تعيين أوامر البوت."""
    await application.bot.set_my_commands([
        ("start", "بدء البوت"),
        ("register", "تسجيل / تعديل البيانات"),
        ("balance", "التحقق من الرصيد"),
        ("deposit", "إيداع الأموال"),
        ("withdraw", "سحب الأموال"),
        ("invest", "الاستثمار في بوت التداول الآلي"),
        ("recommendations", "الحصول على توصيات تداول"),
        ("my_subscription", "إدارة اشتراكي"),
        ("about", "حول البوت"),
        ("contact", "تواصل معنا"),
    ])
    logger.info("تم تعيين أوامر البوت.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة التعامل مع أمر /start."""
    user_id = update.effective_user.id
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)

    if user_data is None:
        keyboard = [[InlineKeyboardButton("تسجيل البيانات 📝", callback_data="register_now")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        welcome_text = (
            "مرحباً بك في بوت Syrian Crypto\n"
            "هذا البوت مخصص للراغبين في تعلم تداول العملات الرقمية في سوريا.\n"
            "يمكنك هنا الحصول على توصيات لتداول العملات الرقمية للدخول في صفقات "
            "وإعطاء نسبة نجاح عالية للصفقات.\n"
            "كما يمكنك الاشتراك في بوت التداول الآلي الخاص بنا والذي يعطي عائداً "
            "استثمارياً يصل إلى 35 بالمئة وسحب الأرباح بشكل شهري.\n"
            "عليك التسجيل أولاً، زودنا ببياناتك لتحصل على أفضل تجربة."
        )
        await update.message.reply_text(
            escape_markdown(welcome_text, version=2),
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    else:
        await Show_main_menu(update, context)


async def Show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة لعرض القائمة الرئيسية."""
    keyboard = [
        [InlineKeyboardButton("إيداع 💰", callback_data="deposit_menu"),
         InlineKeyboardButton("سحب 💸", callback_data="withdraw_menu")],
        [InlineKeyboardButton("الاستثمار في بوت التداول الآلي 📈", callback_data="invest_menu")],
        [InlineKeyboardButton("توصيات التداول 📊", callback_data="recommendations_menu")],
        [InlineKeyboardButton("رصيدي 💵", callback_data="my_balance")],
        [InlineKeyboardButton("اشتراكي 💎", callback_data="my_subscription")],
        [InlineKeyboardButton("تعديل بياناتي 📝", callback_data="edit_my_data")],
        [InlineKeyboardButton("حول البوت ℹ️", callback_data="about_bot"),
         InlineKeyboardButton("تواصل معنا 📞", callback_data="contact_us")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = "أهلاً بك في القائمة الرئيسية. اختر ما تريد:"

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(escape_markdown(message_text, version=2), reply_markup=reply_markup, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Error editing message for main menu: {e}")
            await update.callback_query.message.reply_text(escape_markdown(message_text, version=2), reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(escape_markdown(message_text, version=2), reply_markup=reply_markup, parse_mode='MarkdownV2')


async def go_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """العودة للقائمة الرئيسية وإنهاء المحادثة."""
    context.user_data.clear()
    await Show_main_menu(update, context)
    return ConversationHandler.END


async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دالة التعامل مع أمر /register."""
    return await register_bot_callback(update, context)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دالة التعامل مع أمر /balance."""
    user_id = update.effective_user.id
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)
    message = update.message or (update.callback_query.message if update.callback_query else None)

    if user_data:
        wallet_balance = user_data.get('wallet_balance', 0.0)
        investment_balance = user_data.get('investment_balance', 0.0)
        balance_text = escape_markdown(
            f"💵 رصيدك الحالي في المحفظة: {wallet_balance:.2f} USD\n"
            f"📈 رصيد استثمارك الحالي: {investment_balance:.2f} USD",
            version=2
        )
        back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])
        await message.reply_text(balance_text, parse_mode='MarkdownV2', reply_markup=back_markup)
    else:
        await message.reply_text(escape_markdown("يرجى التسجيل أولاً باستخدام أمر /register.", version=2), parse_mode='MarkdownV2')

    if update.callback_query:
        await update.callback_query.answer()


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة التعامل مع أمر /about."""
    message_text = escape_markdown(
        "بوت التداول الآلي يوفر لك وصولاً سهلاً وسريعاً لخدمات الإيداع والسحب والاستثمار في التداول، "
        "بالإضافة إلى توصيات التداول اليومية وميزات لوحة تحكم الأدمن. "
        "نحن نهدف لتبسيط عملية التداول وجعلها في متناول الجميع."
        "\n\nللبدء، يمكنك استخدام الأوامر في القائمة أو اختيار الخيارات من القائمة الرئيسية."
        "\n\nإذا واجهت أي مشاكل، لا تتردد في التواصل معنا عبر أمر /contact.", version=2)
    message = update.message or (update.callback_query.message if update.callback_query else None)
    back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])
    await message.reply_text(message_text, parse_mode='MarkdownV2', reply_markup=back_markup)
    if update.callback_query:
        await update.callback_query.answer()


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة التعامل مع أمر /contact."""
    message_text = escape_markdown(
        "يمكنك التواصل مع الدعم الفني عبر البريد الإلكتروني أو صفحتنا على Telegram."
        "\n\n📧 البريد الإلكتروني: l2044180@gmail.com"
        "\n📱 قناة التلجرام: https://t.me/+BoJKRMxvawBhZjA0"
        "\n\nسنكون سعداء بمساعدتك!", version=2)
    message = update.message or (update.callback_query.message if update.callback_query else None)
    back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])
    await message.reply_text(message_text, parse_mode='MarkdownV2', reply_markup=back_markup)
    if update.callback_query:
        await update.callback_query.answer()


async def handle_unhandled_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة للتعامل مع الرسائل غير المفهومة."""
    await update.message.reply_text(escape_markdown(
        "عذراً، لم أفهم طلبك. يرجى استخدام الأوامر من القائمة أو أزرار القائمة الرئيسية."
        "\n\nيمكنك استخدام /start للعودة إلى البداية.", version=2), parse_mode='MarkdownV2')


def setup_handlers(application: Application):
    """دالة إعداد جميع المعالجات."""
    registration_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('register', register_command),
            CallbackQueryHandler(register_bot_callback, pattern='^register_now$'),
            CallbackQueryHandler(register_command, pattern='^edit_my_data$')
        ],
        states={
            ASKING_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_full_name)],
            ASKING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_address)],
            ASKING_PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone_number)],
            CONFIRM_EDIT: [CallbackQueryHandler(start_edit_registration, pattern='^start_edit_registration$')]
        },
        fallbacks=[CommandHandler("cancel", cancel_registration), CallbackQueryHandler(cancel_registration, pattern='^cancel_registration$'), CallbackQueryHandler(go_to_main_menu, pattern='^main_menu$')]
    )

    deposit_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('deposit', start_deposit),
            CallbackQueryHandler(start_deposit, pattern='^deposit_menu$')
        ],
        states={
            SELECT_DEPOSIT_METHOD: [
                CallbackQueryHandler(select_deposit_method, pattern='^deposit_'),
                CallbackQueryHandler(select_usdt_wallet_type, pattern='^usdt_deposit_'),
                CallbackQueryHandler(start_deposit, pattern='^deposit_menu$')
            ],
            ASKING_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deposit_amount)],
            ENTER_DEPOSIT_TXID: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_deposit_txid)],
        },
        fallbacks=[CommandHandler("cancel", cancel_deposit), CallbackQueryHandler(cancel_deposit, pattern='^cancel_deposit$'), CallbackQueryHandler(go_to_main_menu, pattern='^main_menu$')]
    )

    withdraw_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('withdraw', start_withdraw),
            CallbackQueryHandler(start_withdraw, pattern='^withdraw_menu$')
        ],
        states={
            SELECT_WITHDRAW_METHOD: [
                CallbackQueryHandler(select_withdraw_method, pattern='^withdraw_'),
                CallbackQueryHandler(select_usdt_withdraw_wallet_type, pattern='^usdt_withdraw_')
            ],
            ASKING_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_amount)],
            ASKING_WITHDRAW_ACCOUNT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_account_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel_withdraw), CallbackQueryHandler(cancel_withdraw, pattern='^cancel_withdraw$'), CallbackQueryHandler(go_to_main_menu, pattern='^main_menu$')]
    )

    invest_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('invest', start_invest_in_bot),
            CallbackQueryHandler(start_invest_in_bot, pattern='^invest_menu$')
        ],
        states={
            ASKING_INVEST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_invest_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel_invest), CallbackQueryHandler(cancel_invest, pattern='^cancel_invest$'), CallbackQueryHandler(go_to_main_menu, pattern='^main_menu$')]
    )

    subscription_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('recommendations', start_subscription_process),
            CommandHandler('my_subscription', start_subscription_process),
            CallbackQueryHandler(start_subscription_process, pattern='^(recommendations_menu|my_subscription)$')
        ],
        states={
            SELECT_SUBSCRIPTION_PLAN: [CallbackQueryHandler(select_subscription_plan, pattern=r'^select_plan_(monthly|annual|free)$')],
            SELECT_TRADING_PAIRS: [CallbackQueryHandler(select_trading_pairs, pattern=r'^(pair_toggle_.+|pair_page_\d+|select_pairs_done|back_to_plans)$')],
            CONFIRM_SUBSCRIPTION: [CallbackQueryHandler(confirm_subscription, pattern=r'^(confirm_subscription|back_to_pairs)$')]
        },
        fallbacks=[CommandHandler("cancel", cancel_subscription), CallbackQueryHandler(cancel_subscription, pattern='^cancel_subscription$'), CallbackQueryHandler(go_to_main_menu, pattern='^main_menu$')]
    )

    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_control_panel)],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(handle_admin_callback, pattern='^admin_'),
                CallbackQueryHandler(admin_show_users_paginated, pattern=r'^admin_show_users_page_'),
                CallbackQueryHandler(admin_view_user_details, pattern=r'^admin_view_user_')
            ],
            SEND_MESSAGE_TO_ALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message_input)],
            GET_USER_ID_FOR_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message_input)],
            GET_WALLET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message_input)],
            GET_USER_ID_FOR_INVESTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message_input)],
            GET_INVESTMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message_input)],
        },
        fallbacks=[CallbackQueryHandler(Show_main_menu, pattern='^go_main$')],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END
        }
    )

    application.add_handler(admin_conv_handler)
    application.add_handler(registration_conv_handler)
    application.add_handler(deposit_conv_handler)
    application.add_handler(withdraw_conv_handler)
    application.add_handler(invest_conv_handler)
    application.add_handler(subscription_conv_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("contact", contact_command))

    application.add_handler(CallbackQueryHandler(handle_transaction_callback, pattern=r'^(approve|reject)_transaction_'))

    application.add_handler(CallbackQueryHandler(Show_main_menu, pattern='^go_main$'))
    application.add_handler(CallbackQueryHandler(go_to_main_menu, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(balance_command, pattern='^my_balance$'))
    application.add_handler(CallbackQueryHandler(about_command, pattern='^about_bot$'))
    application.add_handler(CallbackQueryHandler(contact_command, pattern='^contact_us$'))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unhandled_message))


async def post_init_setup(application: Application):
    """دالة إعداد ما بعد التهيئة لتشغيل المهام غير المتزامنة."""
    await set_my_commands(application)
    daily_recommendation_time = time(hour=9, minute=0, tzinfo=pytz.timezone('Asia/Damascus'))
    application.job_queue.run_daily(check_and_send_daily_recommendations, daily_recommendation_time, name="daily_recommendations")
    logger.info(f"تم جدولة إرسال التوصيات اليومية في {daily_recommendation_time}.")

    try:
        logger.info("جاري تحميل أزواج USDT مسبقاً...")
        pairs = await get_all_usdt_pairs()
        logger.info(f"تم تحميل {len(pairs)} زوج USDT مسبقاً.")
    except Exception as e:
        logger.warning(f"تعذّر تحميل الأزواج مسبقاً: {e}")


def _start_health_server():
    """يشغل خادم HTTP بسيط للتحقق من صحة التطبيق عند النشر."""
    port = int(os.environ.get('PORT', 8080))

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is running OK')

        def log_message(self, format, *args):
            pass

    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health check server started on port {port}.")
    server.serve_forever()


def main():
    """الدالة الرئيسية لتشغيل البوت."""
    health_thread = threading.Thread(target=_start_health_server, daemon=True)
    health_thread.start()

    init_db()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init_setup).build()

    app.bot_data.update({
        'get_user_data_ref': get_user_data,
        'update_wallet_balance_ref': update_wallet_balance,
        'update_investment_balance_ref': update_investment_balance,
        'get_all_users_data_ref': get_all_users_data,
        'update_subscriptionStatus_ref': update_subscription_status,
        'get_subscription_info_ref': get_subscription_info,
        'update_subscribed_pairs_ref': update_subscribed_pairs,
        'update_daily_recommendations_count_ref': update_daily_recommendations_count,
        'send_admin_notification_ref': send_admin_notification,
        'ADMIN_CHAT_ID': ADMIN_CHAT_ID,
        'get_all_usdt_pairs_ref': get_all_usdt_pairs,
        'get_crypto_data_ref': get_crypto_data,
        'generate_trading_signal_ref': generate_trading_signal,
        'format_signal_ref': format_signal,
        'check_and_send_daily_recommendations_ref': check_and_send_daily_recommendations,
        'pending_transactions': {},
        'USDT_CWALLET_ADDRESS': USDT_CWALLET_ADDRESS,
        'USDT_BINANCE_ADDRESS': USDT_BINANCE_ADDRESS,
        'USDT_EXTERNAL_ADDRESS': USDT_EXTERNAL_ADDRESS,
        'SHAM_CASH_NUMBER': SHAM_CASH_NUMBER,
        'SYRIATEL_CASH_NUMBER': SYRIATEL_CASH_NUMBER,
        'PAYER_ACCOUNT': PAYER_ACCOUNT,
        'BANK_TRANSFER_DETAILS': BANK_TRANSFER_DETAILS,
        'logger': logger
    })

    setup_handlers(app)

    try:
        logger.info("✅ بدء الـ Polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.exception("❌ خطأ أثناء تشغيل البوت:", exc_info=e)


if __name__ == '__main__':
    main()
