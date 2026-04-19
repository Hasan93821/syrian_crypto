import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
import math
import asyncio

logger = logging.getLogger(__name__)

ADMIN_MENU, SEND_MESSAGE_TO_ALL, GET_USER_ID_FOR_WALLET, GET_WALLET_AMOUNT, \
GET_USER_ID_FOR_INVESTMENT, GET_INVESTMENT_AMOUNT = range(20, 26)

USERS_PER_PAGE = 5


async def admin_control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض لوحة تحكم الأدمن."""
    user_id = update.effective_user.id
    admin_chat_id = context.application.bot_data.get('ADMIN_CHAT_ID')

    if user_id != admin_chat_id:
        await update.message.reply_text(escape_markdown("عذراً، هذا الأمر متاح للأدمن فقط.", version=2), parse_mode='MarkdownV2')
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("إدارة المستخدمين 👥", callback_data="admin_manage_users")],
        [InlineKeyboardButton("إدارة الرصيد 💵", callback_data="admin_manage_balance")],
        [InlineKeyboardButton("إرسال رسالة جماعية 📣", callback_data="admin_broadcast_message")],
        [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data="go_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = escape_markdown("مرحباً أيها الأدمن! هذه لوحة تحكم البوت:", version=2)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Error editing admin control panel message: {e}")
            await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    return ADMIN_MENU


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتعامل مع ردود اتصال لوحة تحكم الأدمن."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_manage_users":
        return await admin_show_users_paginated(update, context, page=0)

    elif data == "admin_manage_balance":
        keyboard = [
            [InlineKeyboardButton("إضافة رصيد محفظة ➕", callback_data="admin_add_wallet_balance")],
            [InlineKeyboardButton("خصم رصيد محفظة ➖", callback_data="admin_deduct_wallet_balance")],
            [InlineKeyboardButton("إضافة رصيد استثمار 📈", callback_data="admin_add_investment_balance")],
            [InlineKeyboardButton("خصم رصيد استثمار 📉", callback_data="admin_deduct_investment_balance")],
            [InlineKeyboardButton("العودة للوحة الأدمن ↩️", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(escape_markdown("اختر إدارة الرصيد:", version=2), reply_markup=reply_markup, parse_mode='MarkdownV2')
        return ADMIN_MENU

    elif data == "admin_broadcast_message":
        await query.edit_message_text(escape_markdown("أدخل الرسالة التي تريد إرسالها لجميع المستخدمين:", version=2), parse_mode='MarkdownV2')
        context.user_data['admin_action'] = 'broadcast'
        return SEND_MESSAGE_TO_ALL

    elif data == "admin_add_wallet_balance":
        await query.edit_message_text(escape_markdown("أدخل ID المستخدم الذي تريد إضافة رصيد محفظة له:", version=2), parse_mode='MarkdownV2')
        context.user_data['admin_action'] = 'add_wallet'
        context.user_data.pop('target_user_id', None)
        return GET_USER_ID_FOR_WALLET

    elif data == "admin_deduct_wallet_balance":
        await query.edit_message_text(escape_markdown("أدخل ID المستخدم الذي تريد خصم رصيد محفظة منه:", version=2), parse_mode='MarkdownV2')
        context.user_data['admin_action'] = 'deduct_wallet'
        context.user_data.pop('target_user_id', None)
        return GET_USER_ID_FOR_WALLET

    elif data == "admin_add_investment_balance":
        await query.edit_message_text(escape_markdown("أدخل ID المستخدم الذي تريد إضافة رصيد استثمار له:", version=2), parse_mode='MarkdownV2')
        context.user_data['admin_action'] = 'add_investment'
        context.user_data.pop('target_user_id', None)
        return GET_USER_ID_FOR_INVESTMENT

    elif data == "admin_deduct_investment_balance":
        await query.edit_message_text(escape_markdown("أدخل ID المستخدم الذي تريد خصم رصيد استثمار منه:", version=2), parse_mode='MarkdownV2')
        context.user_data['admin_action'] = 'deduct_investment'
        context.user_data.pop('target_user_id', None)
        return GET_USER_ID_FOR_INVESTMENT

    elif data == "admin_menu":
        return await admin_control_panel(update, context)

    return ADMIN_MENU


async def handle_admin_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتعامل مع المدخلات من الأدمن بناءً على الحالة والخطوة الحالية."""

    admin_action = context.user_data.get('admin_action')
    target_user_id = context.user_data.get('target_user_id')

    if admin_action == 'broadcast':
        message_to_send = update.message.text
        get_all_users_data_func = context.application.bot_data.get('get_all_users_data_ref')
        all_users = get_all_users_data_func()

        sent_count = 0
        for user_id_str, user_info in all_users.items():
            try:
                uid = int(user_id_str)
                await context.bot.send_message(uid, escape_markdown(message_to_send, version=2), parse_mode='MarkdownV2')
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id_str}: {e}")

        await update.message.reply_text(escape_markdown(f"تم إرسال الرسالة إلى {sent_count} مستخدم بنجاح.", version=2), parse_mode='MarkdownV2')
        context.user_data.clear()
        return ADMIN_MENU

    elif admin_action in ('add_wallet', 'deduct_wallet'):
        if target_user_id is None:
            try:
                target_user_id = int(update.message.text)
                context.user_data['target_user_id'] = target_user_id
                await update.message.reply_text(escape_markdown("أدخل المبلغ:", version=2), parse_mode='MarkdownV2')
                return GET_WALLET_AMOUNT
            except ValueError:
                await update.message.reply_text(escape_markdown("معرف المستخدم غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
                return GET_USER_ID_FOR_WALLET
        else:
            try:
                amount = float(update.message.text)
                action = admin_action

                update_wallet_balance_func = context.application.bot_data.get('update_wallet_balance_ref')
                get_user_data_func = context.application.bot_data.get('get_user_data_ref')

                user_data = get_user_data_func(target_user_id)
                if not user_data:
                    await update.message.reply_text(escape_markdown("المستخدم غير موجود.", version=2), parse_mode='MarkdownV2')
                    context.user_data.clear()
                    return ADMIN_MENU

                if action == 'add_wallet':
                    update_wallet_balance_func(target_user_id, amount)
                    await update.message.reply_text(escape_markdown(f"تم إضافة {amount:.2f} USD لرصيد محفظة المستخدم {target_user_id}.", version=2), parse_mode='MarkdownV2')
                elif action == 'deduct_wallet':
                    if user_data.get('wallet_balance', 0.0) < amount:
                        await update.message.reply_text(escape_markdown("رصيد المستخدم غير كافٍ للخصم.", version=2), parse_mode='MarkdownV2')
                        context.user_data.clear()
                        return ADMIN_MENU
                    update_wallet_balance_func(target_user_id, -amount)
                    await update.message.reply_text(escape_markdown(f"تم خصم {amount:.2f} USD من رصيد محفظة المستخدم {target_user_id}.", version=2), parse_mode='MarkdownV2')

                context.user_data.clear()
                return ADMIN_MENU
            except ValueError:
                await update.message.reply_text(escape_markdown("المبلغ غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
                return GET_WALLET_AMOUNT

    elif admin_action in ('add_investment', 'deduct_investment'):
        if target_user_id is None:
            try:
                target_user_id = int(update.message.text)
                context.user_data['target_user_id'] = target_user_id
                await update.message.reply_text(escape_markdown("أدخل المبلغ:", version=2), parse_mode='MarkdownV2')
                return GET_INVESTMENT_AMOUNT
            except ValueError:
                await update.message.reply_text(escape_markdown("معرف المستخدم غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
                return GET_USER_ID_FOR_INVESTMENT
        else:
            try:
                amount = float(update.message.text)
                action = admin_action

                update_investment_balance_func = context.application.bot_data.get('update_investment_balance_ref')
                get_user_data_func = context.application.bot_data.get('get_user_data_ref')

                user_data = get_user_data_func(target_user_id)
                if not user_data:
                    await update.message.reply_text(escape_markdown("المستخدم غير موجود.", version=2), parse_mode='MarkdownV2')
                    context.user_data.clear()
                    return ADMIN_MENU

                if action == 'add_investment':
                    update_investment_balance_func(target_user_id, amount)
                    await update.message.reply_text(escape_markdown(f"تم إضافة {amount:.2f} USD لرصيد استثمار المستخدم {target_user_id}.", version=2), parse_mode='MarkdownV2')
                elif action == 'deduct_investment':
                    if user_data.get('investment_balance', 0.0) < amount:
                        await update.message.reply_text(escape_markdown("رصيد الاستثمار للمستخدم غير كافٍ للخصم.", version=2), parse_mode='MarkdownV2')
                        context.user_data.clear()
                        return ADMIN_MENU
                    update_investment_balance_func(target_user_id, -amount)
                    await update.message.reply_text(escape_markdown(f"تم خصم {amount:.2f} USD من رصيد استثمار المستخدم {target_user_id}.", version=2), parse_mode='MarkdownV2')

                context.user_data.clear()
                return ADMIN_MENU
            except ValueError:
                await update.message.reply_text(escape_markdown("المبلغ غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
                return GET_INVESTMENT_AMOUNT

    return ADMIN_MENU


async def handle_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يتعامل مع ردود اتصال موافقة/رفض المعاملات المعلقة من الأدمن.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    parts = data.split('_', 2)
    if len(parts) < 3:
        await query.edit_message_text(escape_markdown("بيانات المعاملة غير صالحة.", version=2), parse_mode='MarkdownV2')
        return

    action = parts[0]
    transaction_id = parts[2]

    pending_transactions = context.application.bot_data.get('pending_transactions')
    transaction_info = pending_transactions.pop(transaction_id, None)

    if not transaction_info:
        await query.edit_message_text(escape_markdown("هذه المعاملة لم تعد معلقة أو تم التعامل معها مسبقاً.", version=2), parse_mode='MarkdownV2')
        return

    user_id = transaction_info['user_id']
    amount = transaction_info['amount']
    tx_type = transaction_info['type']

    send_admin_notification_func = context.application.bot_data.get('send_admin_notification_ref')
    update_wallet_balance_func = context.application.bot_data.get('update_wallet_balance_ref')
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')

    user_data = get_user_data_func(user_id)
    user_full_name = user_data.get('full_name', 'غير معروف') if user_data else 'غير معروف'

    if action == 'approve':
        if tx_type == 'deposit':
            update_wallet_balance_func(user_id, amount)
            await context.bot.send_message(user_id, escape_markdown(f"✅ تم الموافقة على طلب إيداعك بمبلغ {amount:.2f} USD. تم إضافة المبلغ إلى محفظتك.", version=2), parse_mode='MarkdownV2')
            await query.edit_message_text(escape_markdown(f"تم الموافقة على طلب إيداع المستخدم {user_full_name} ({user_id}) بمبلغ {amount:.2f} USD.", version=2), parse_mode='MarkdownV2')
        elif tx_type == 'withdraw':
            update_wallet_balance_func(user_id, -amount)
            await context.bot.send_message(user_id, escape_markdown(f"✅ تم الموافقة على طلب سحبك بمبلغ {amount:.2f} USD. سيصل المبلغ إلى حسابك قريباً.", version=2), parse_mode='MarkdownV2')
            await query.edit_message_text(escape_markdown(f"تم الموافقة على طلب سحب المستخدم {user_full_name} ({user_id}) بمبلغ {amount:.2f} USD.", version=2), parse_mode='MarkdownV2')
    elif action == 'reject':
        await context.bot.send_message(user_id, escape_markdown(f"❌ تم رفض طلبك بمبلغ {amount:.2f} USD. يرجى التواصل مع الدعم للمزيد من التفاصيل.", version=2), parse_mode='MarkdownV2')
        await query.edit_message_text(escape_markdown(f"تم رفض طلب المستخدم {user_full_name} ({user_id}) بمبلغ {amount:.2f} USD.", version=2), parse_mode='MarkdownV2')


async def admin_show_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> int:
    """
    يعرض قائمة بالمستخدمين مع ترقيم الصفحات.
    """
    query = update.callback_query
    if query and query.data.startswith('admin_show_users_page_'):
        page = int(query.data.split('_')[-1])
        await query.answer()

    get_all_users_data_func = context.application.bot_data.get('get_all_users_data_ref')
    all_users_dict = get_all_users_data_func()
    all_users = list(all_users_dict.values())

    total_users = len(all_users)
    total_pages = math.ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1

    start_index = page * USERS_PER_PAGE
    end_index = start_index + USERS_PER_PAGE
    users_on_page = all_users[start_index:end_index]

    if not users_on_page:
        message_text = escape_markdown("لا يوجد مستخدمون لعرضهم.", version=2)
        keyboard = [[InlineKeyboardButton("العودة للوحة الأدمن ↩️", callback_data="admin_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        return ADMIN_MENU

    message_text = escape_markdown(f"قائمة المستخدمين (صفحة {page + 1} من {total_pages}):\n", version=2)
    keyboard = []
    for user in users_on_page:
        user_full_name = user.get('full_name', 'N/A')
        user_id = user['user_id']
        wallet_balance = user.get('wallet_balance', 0.0)
        investment_balance = user.get('investment_balance', 0.0)
        is_subscribed = '✅' if user.get('is_subscribed') else '❌'

        message_text += escape_markdown(
            f"\n👤 الاسم: {user_full_name}\n"
            f"🆔 ID: {user_id}\n"
            f"💵 المحفظة: {wallet_balance:.2f} USD\n"
            f"📈 الاستثمار: {investment_balance:.2f} USD\n"
            f"🌟 مشترك: {is_subscribed}\n",
            version=2
        )
        keyboard.append([InlineKeyboardButton(f"عرض تفاصيل {user_full_name}", callback_data=f"admin_view_user_{user_id}")])

    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"admin_show_users_page_{page - 1}"))
    if page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"admin_show_users_page_{page + 1}"))

    if pagination_buttons:
        keyboard.append(pagination_buttons)

    keyboard.append([InlineKeyboardButton("العودة للوحة الأدمن ↩️", callback_data="admin_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Error editing message in admin_show_users_paginated: {e}")
            await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')

    return ADMIN_MENU


async def admin_view_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يعرض تفاصيل مستخدم محدد.
    """
    query = update.callback_query
    await query.answer()
    user_id_to_view = int(query.data.replace('admin_view_user_', ''))

    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user = get_user_data_func(user_id_to_view)

    if not user:
        await query.edit_message_text(escape_markdown("المستخدم غير موجود.", version=2), parse_mode='MarkdownV2')
        return ADMIN_MENU

    is_subscribed_text = '✅' if user.get('is_subscribed') else '❌'
    message_text = escape_markdown(
        f"👤 تفاصيل المستخدم: {user.get('full_name', 'N/A')}\n"
        f"🆔 ID: {user['user_id']}\n"
        f"📍 العنوان: {user.get('address', 'N/A')}\n"
        f"📞 رقم الهاتف: {user.get('phone_number', 'N/A')}\n"
        f"💵 رصيد المحفظة: {user.get('wallet_balance', 0.0):.2f} USD\n"
        f"📈 رصيد الاستثمار: {user.get('investment_balance', 0.0):.2f} USD\n"
        f"🌟 مشترك: {is_subscribed_text}\n",
        version=2
    )
    if user.get('is_subscribed'):
        pairs_str = ', '.join(user.get('subscribed_pairs', [])) or 'لا يوجد'
        message_text += escape_markdown(
            f"   - الخطة: {user.get('subscription_plan', 'N/A')}\n"
            f"   - تنتهي في: {user.get('expiry_date', 'N/A')}\n"
            f"   - أزواج التداول: {pairs_str}\n"
            f"   - توصيات اليوم: {user.get('daily_recommendations_count', 0)}\n",
            version=2
        )

    keyboard = [[InlineKeyboardButton("العودة لإدارة المستخدمين ↩️", callback_data="admin_manage_users")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    return ADMIN_MENU
