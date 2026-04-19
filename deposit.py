import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
import uuid
import asyncio

logger = logging.getLogger(__name__)

# تعريف حالات المحادثة
SELECT_DEPOSIT_METHOD, ASKING_DEPOSIT_AMOUNT, ENTER_DEPOSIT_TXID = range(10, 13)
# إضافة ASKING_WITHDRAW_ACCOUNT_DETAILS كحالة جديدة في تسلسل السحب
SELECT_WITHDRAW_METHOD, ASKING_WITHDRAW_AMOUNT, ASKING_WITHDRAW_ACCOUNT_DETAILS = range(13, 16)
ASKING_INVEST_AMOUNT = 16 # تأكد من وجود هذا السطر

method_name = {
    'usdt': 'USDT (TRC20)', 'sham_cash': 'شام كاش', 'syriatel_cash': 'سيرياتيل كاش',
    'payer': 'باير', 'bank_transfer': 'تحويل بنكي'
}

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message_text: str, reply_markup=None):
    """
    دالة مساعدة لإرسال إشعارات للأدمن.
    """
    admin_chat_id = context.application.bot_data.get('ADMIN_CHAT_ID')
    if admin_chat_id:
        try:
            await context.bot.send_message(admin_chat_id, message_text, parse_mode='MarkdownV2', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")

# --- دوال الإيداع ---
async def start_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يبدأ عملية الإيداع ويعرض طرق الإيداع المتاحة.
    """
    user_id = update.effective_user.id
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)

    if not user_data:
        message = update.message or update.callback_query.message
        await message.reply_text(escape_markdown("يرجى التسجيل أولاً باستخدام أمر /register.", version=2), parse_mode='MarkdownV2')
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("USDT (TRC20)", callback_data="deposit_usdt")],
        [InlineKeyboardButton("شام كاش", callback_data="deposit_sham_cash")],
        [InlineKeyboardButton("سيرياتيل كاش", callback_data="deposit_syriatel_cash")],
        [InlineKeyboardButton("باير", callback_data="deposit_payer")],
        [InlineKeyboardButton("تحويل بنكي", callback_data="deposit_bank_transfer")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
         InlineKeyboardButton("إلغاء ❌", callback_data="cancel_deposit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_to_edit = update.message
    if update.callback_query:
        await update.callback_query.answer()
        message_to_edit = update.callback_query.message
        try:
            await message_to_edit.edit_text(
                escape_markdown("يرجى اختيار طريقة الإيداع:", version=2),
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error editing message in start_deposit: {e}")
            await message_to_edit.reply_text(
                escape_markdown("يرجى اختيار طريقة الإيداع:", version=2),
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
    else:
        await message_to_edit.reply_text(
            escape_markdown("يرجى اختيار طريقة الإيداع:", version=2),
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    return SELECT_DEPOSIT_METHOD

async def select_deposit_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يحدد طريقة الإيداع المختارة ويعرض التفاصيل.
    """
    query = update.callback_query
    await query.answer()
    method = query.data.replace('deposit_', '')
    context.user_data['deposit_method'] = method

    if method == 'usdt':
        keyboard = [
            [InlineKeyboardButton("USDT (TRC20) - محفظة C", callback_data="usdt_deposit_cwallet")],
            [InlineKeyboardButton("USDT (TRC20) - بايننس", callback_data="usdt_deposit_binance")],
            [InlineKeyboardButton("USDT (TRC20) - محفظة خارجية", callback_data="usdt_deposit_external")],
            [InlineKeyboardButton("العودة لطرق الإيداع ↩️", callback_data="deposit_menu")], # زر للعودة
            [InlineKeyboardButton("إلغاء ❌", callback_data="cancel_deposit")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            escape_markdown("يرجى اختيار نوع محفظة USDT:", version=2),
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
        return SELECT_DEPOSIT_METHOD # البقاء في نفس الحالة لاختيار نوع محفظة USDT
    else:
        await query.edit_message_text(escape_markdown(f"لقد اخترت الإيداع عبر {method_name[method]}. يرجى إدخال المبلغ الذي ترغب في إيداعه:", version=2), parse_mode='MarkdownV2')
        return ASKING_DEPOSIT_AMOUNT

async def select_usdt_wallet_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يحدد نوع محفظة USDT المختارة.
    """
    query = update.callback_query
    await query.answer()
    wallet_type = query.data.replace('usdt_deposit_', '')
    context.user_data['usdt_wallet_type'] = wallet_type

    usdt_cwallet_address = context.application.bot_data.get('USDT_CWALLET_ADDRESS')
    usdt_binance_address = context.application.bot_data.get('USDT_BINANCE_ADDRESS')
    usdt_external_address = context.application.bot_data.get('USDT_EXTERNAL_ADDRESS')

    address_info = ""
    copy_address = ""
    if wallet_type == 'cwallet':
        copy_address = usdt_cwallet_address or ""
        address_info = f"عنوان محفظة USDT (TRC20) C: `{usdt_cwallet_address}`"
    elif wallet_type == 'binance':
        copy_address = usdt_binance_address or ""
        address_info = f"عنوان محفظة USDT (TRC20) بايننس: `{usdt_binance_address}`"
    elif wallet_type == 'external':
        copy_address = usdt_external_address or ""
        address_info = f"عنوان محفظة USDT (TRC20) الخارجية: `{usdt_external_address}`"

    copy_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 نسخ العنوان", copy_text=CopyTextButton(text=copy_address))],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]) if copy_address else InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])

    await query.edit_message_text(
        escape_markdown(f"لقد اخترت الإيداع عبر USDT (TRC20) - {method_name['usdt']}.\n\n"
                       f"{address_info}\n\n"
                       f"يرجى إدخال المبلغ الذي ترغب في إيداعه:", version=2),
        parse_mode='MarkdownV2',
        reply_markup=copy_markup
    )
    return ASKING_DEPOSIT_AMOUNT

async def receive_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يستقبل المبلغ المراد إيداعه.
    """
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text(escape_markdown("المبلغ يجب أن يكون أكبر من صفر. يرجى إدخال مبلغ صحيح:", version=2), parse_mode='MarkdownV2')
            return ASKING_DEPOSIT_AMOUNT

        context.user_data['deposit_amount'] = amount
        method = context.user_data.get('deposit_method')

        if method in ['sham_cash', 'syriatel_cash', 'payer', 'bank_transfer']:
            details = ""
            copy_number = ""
            if method == 'sham_cash':
                copy_number = context.application.bot_data.get('SHAM_CASH_NUMBER') or ""
                details = f"حساب شام كاش: `{copy_number}`"
            elif method == 'syriatel_cash':
                copy_number = context.application.bot_data.get('SYRIATEL_CASH_NUMBER') or ""
                details = f"رقم سيرياتيل كاش: `{copy_number}`"
            elif method == 'payer':
                copy_number = context.application.bot_data.get('PAYER_ACCOUNT') or ""
                details = f"حساب باير: `{copy_number}`"
            elif method == 'bank_transfer':
                copy_number = context.application.bot_data.get('BANK_TRANSFER_DETAILS') or ""
                details = f"تفاصيل التحويل البنكي: `{copy_number}`"

            copy_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 نسخ رقم الحساب", copy_text=CopyTextButton(text=copy_number))],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
            ]) if copy_number else InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])

            await update.message.reply_text(
                escape_markdown(f"لقد اخترت إيداع `{amount:.2f}` USD عبر {method_name[method]}.\n\n"
                               f"{details}\n\n"
                               f"بعد إتمام عملية التحويل، يرجى إدخال معرّف المعاملة (Transaction ID) أو صورة إيصال التحويل للمتابعة:", version=2),
                parse_mode='MarkdownV2',
                reply_markup=copy_markup
            )
            return ENTER_DEPOSIT_TXID
        else: # USDT
            await update.message.reply_text(
                escape_markdown(f"لقد اخترت إيداع `{amount:.2f}` USD عبر USDT. بعد إتمام عملية التحويل، يرجى إدخال معرّف المعاملة (Transaction ID) للمتابعة:", version=2),
                parse_mode='MarkdownV2'
            )
            return ENTER_DEPOSIT_TXID

    except ValueError:
        await update.message.reply_text(escape_markdown("المبلغ غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
        return ASKING_DEPOSIT_AMOUNT

async def enter_deposit_txid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يستقبل معرّف المعاملة ويبلغ الأدمن.
    """
    txid = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('deposit_amount')
    method = context.user_data.get('deposit_method')
    usdt_wallet_type = context.user_data.get('usdt_wallet_type', 'N/A')

    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)
    user_full_name = user_data.get('full_name', 'غير معروف')

    transaction_id = str(uuid.uuid4())
    context.application.bot_data['pending_transactions'][transaction_id] = {
        'user_id': user_id,
        'amount': amount,
        'method': method,
        'txid': txid,
        'type': 'deposit'
    }

    admin_message = (
        f"💰 *طلب إيداع جديد*\n"
        f"👤 *المستخدم*: {escape_markdown(user_full_name, version=2)} \\(`{user_id}`\\)\n"
        f"💵 *المبلغ*: `{amount:.2f}` USD\n"
        f"💳 *الطريقة*: {escape_markdown(method_name.get(method, 'غير معروف'), version=2)}"
    )
    if method == 'usdt':
        admin_message += f" \\(نوع المحفظة: {escape_markdown(usdt_wallet_type, version=2)}\\)"
    admin_message += f"\n🆔 *معرّف المعاملة/الإيصال*: `{escape_markdown(txid, version=2)}`"

    keyboard = [
        [InlineKeyboardButton("موافقة ✅", callback_data=f"approve_transaction_{transaction_id}")],
        [InlineKeyboardButton("رفض ❌", callback_data=f"reject_transaction_{transaction_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    send_admin_notification_func = context.application.bot_data.get('send_admin_notification_ref')
    await send_admin_notification_func(context, admin_message, reply_markup)

    await update.message.reply_text(
        escape_markdown("تم استلام طلب الإيداع الخاص بك بنجاح. سيتم مراجعته من قبل الأدمن قريباً.", version=2),
        parse_mode='MarkdownV2'
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يلغي عملية الإيداع.
    """
    message = update.message
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(escape_markdown("تم إلغاء عملية الإيداع.", version=2), parse_mode='MarkdownV2')
    else:
        await message.reply_text(escape_markdown("تم إلغاء عملية الإيداع.", version=2), parse_mode='MarkdownV2')
    context.user_data.clear()
    return ConversationHandler.END

# --- دوال السحب ---
async def start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يبدأ عملية السحب ويعرض طرق السحب المتاحة.
    """
    user_id = update.effective_user.id
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)

    if not user_data:
        message = update.message or update.callback_query.message
        await message.reply_text(escape_markdown("يرجى التسجيل أولاً باستخدام أمر /register.", version=2), parse_mode='MarkdownV2')
        return ConversationHandler.END
    
    if user_data.get('wallet_balance', 0.0) <= 0:
        message = update.message or update.callback_query.message
        await message.reply_text(escape_markdown("رصيد محفظتك لا يكفي لإجراء عملية سحب.", version=2), parse_mode='MarkdownV2')
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("USDT (TRC20)", callback_data="withdraw_usdt")],
        [InlineKeyboardButton("شام كاش", callback_data="withdraw_sham_cash")],
        [InlineKeyboardButton("سيرياتيل كاش", callback_data="withdraw_syriatel_cash")],
        [InlineKeyboardButton("باير", callback_data="withdraw_payer")],
        [InlineKeyboardButton("تحويل بنكي", callback_data="withdraw_bank_transfer")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
         InlineKeyboardButton("إلغاء ❌", callback_data="cancel_withdraw")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_to_edit = update.message
    if update.callback_query:
        await update.callback_query.answer()
        message_to_edit = update.callback_query.message
        try:
            await message_to_edit.edit_text(
                escape_markdown("يرجى اختيار طريقة السحب:", version=2),
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error editing message in start_withdraw: {e}")
            await message_to_edit.reply_text(
                escape_markdown("يرجى اختيار طريقة السحب:", version=2),
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
    else:
        await message_to_edit.reply_text(
            escape_markdown("يرجى اختيار طريقة السحب:", version=2),
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
    return SELECT_WITHDRAW_METHOD

async def select_withdraw_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يحدد طريقة السحب المختارة.
    """
    query = update.callback_query
    await query.answer()
    method = query.data.replace('withdraw_', '')
    context.user_data['withdraw_method'] = method

    if method == 'usdt':
        keyboard = [
            [InlineKeyboardButton("USDT (TRC20) - محفظة C", callback_data="usdt_withdraw_cwallet")],
            [InlineKeyboardButton("USDT (TRC20) - بايننس", callback_data="usdt_withdraw_binance")],
            [InlineKeyboardButton("USDT (TRC20) - محفظة خارجية", callback_data="usdt_withdraw_external")],
            [InlineKeyboardButton("العودة لطرق السحب ↩️", callback_data="withdraw_menu")], # زر للعودة
            [InlineKeyboardButton("إلغاء ❌", callback_data="cancel_withdraw")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            escape_markdown("يرجى اختيار نوع محفظة USDT للسحب:", version=2),
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
        return SELECT_WITHDRAW_METHOD # البقاء في نفس الحالة لاختيار نوع محفظة USDT
    else:
        await query.edit_message_text(escape_markdown(f"لقد اخترت السحب عبر {method_name[method]}. يرجى إدخال المبلغ الذي ترغب في سحبه:", version=2), parse_mode='MarkdownV2')
        return ASKING_WITHDRAW_AMOUNT

async def select_usdt_withdraw_wallet_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يحدد نوع محفظة USDT للسحب.
    """
    query = update.callback_query
    await query.answer()
    wallet_type = query.data.replace('usdt_withdraw_', '')
    context.user_data['usdt_withdraw_wallet_type'] = wallet_type

    await query.edit_message_text(
        escape_markdown(f"لقد اخترت السحب عبر USDT (TRC20) - {method_name['usdt']}. يرجى إدخال المبلغ الذي ترغب في سحبه:", version=2),
        parse_mode='MarkdownV2'
    )
    return ASKING_WITHDRAW_AMOUNT

async def receive_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يستقبل المبلغ المراد سحبه ويطلب تفاصيل الحساب.
    """
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text(escape_markdown("المبلغ يجب أن يكون أكبر من صفر. يرجى إدخال مبلغ صحيح:", version=2), parse_mode='MarkdownV2')
            return ASKING_WITHDRAW_AMOUNT

        user_id = update.effective_user.id
        get_user_data_func = context.application.bot_data.get('get_user_data_ref')
        user_data = get_user_data_func(user_id)

        if user_data.get('wallet_balance', 0.0) < amount:
            await update.message.reply_text(escape_markdown("رصيدك في المحفظة غير كافٍ لإجراء هذه العملية.", version=2), parse_mode='MarkdownV2')
            return ConversationHandler.END

        context.user_data['withdraw_amount'] = amount
        method = context.user_data.get('withdraw_method')
        usdt_wallet_type = context.user_data.get('usdt_withdraw_wallet_type', 'N/A')

        # بناء الرسالة لطلب تفاصيل الحساب بناءً على طريقة السحب
        prompt_message = ""
        if method == 'usdt':
            prompt_message = f"لقد اخترت السحب عبر USDT (TRC20) - {method_name['usdt']}. يرجى إدخال عنوان محفظة USDT الخاصة بك للسحب عليها:"
        elif method == 'sham_cash':
            prompt_message = "لقد اخترت السحب عبر شام كاش. يرجى إدخال رقم هاتف شام كاش الخاص بك للسحب عليه:"
        elif method == 'syriatel_cash':
            prompt_message = "لقد اخترت السحب عبر سيرياتيل كاش. يرجى إدخال رقم هاتف سيرياتيل كاش الخاص بك للسحب عليه:"
        elif method == 'payer':
            prompt_message = "لقد اخترت السحب عبر باير. يرجى إدخال رقم حساب باير الخاص بك للسحب عليه:"
        elif method == 'bank_transfer':
            prompt_message = "لقد اخترت السحب عبر التحويل البنكي. يرجى إدخال تفاصيل حسابك البنكي (اسم البنك، رقم الحساب، اسم صاحب الحساب):"
        
        await update.message.reply_text(escape_markdown(prompt_message, version=2), parse_mode='MarkdownV2')
        return ASKING_WITHDRAW_ACCOUNT_DETAILS # الانتقال إلى الحالة الجديدة لطلب تفاصيل الحساب

    except ValueError:
        await update.message.reply_text(escape_markdown("المبلغ غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
        return ASKING_WITHDRAW_AMOUNT

async def receive_withdraw_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يستقبل تفاصيل حساب السحب ويبلغ الأدمن.
    """
    account_details = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('withdraw_amount')
    method = context.user_data.get('withdraw_method')
    usdt_wallet_type = context.user_data.get('usdt_withdraw_wallet_type', 'N/A')

    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)
    user_full_name = user_data.get('full_name', 'غير معروف')

    transaction_id = str(uuid.uuid4())
    context.application.bot_data['pending_transactions'][transaction_id] = {
        'user_id': user_id,
        'amount': amount,
        'method': method,
        'account_details': account_details, # حفظ تفاصيل الحساب
        'type': 'withdraw'
    }

    admin_message = (
        f"💸 *طلب سحب جديد*\n"
        f"👤 *المستخدم*: {escape_markdown(user_full_name, version=2)} \\(`{user_id}`\\)\n"
        f"💵 *المبلغ*: `{amount:.2f}` USD\n"
        f"💳 *الطريقة*: {escape_markdown(method_name.get(method, 'غير معروف'), version=2)}\n"
        f"📝 *تفاصيل الحساب*: `{escape_markdown(account_details, version=2)}`" # إضافة تفاصيل الحساب
    )
    if method == 'usdt':
        admin_message += f" \\(نوع المحفظة: {escape_markdown(usdt_wallet_type, version=2)}\\)"

    keyboard = [
        [InlineKeyboardButton("موافقة ✅", callback_data=f"approve_transaction_{transaction_id}")],
        [InlineKeyboardButton("رفض ❌", callback_data=f"reject_transaction_{transaction_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    send_admin_notification_func = context.application.bot_data.get('send_admin_notification_ref')
    await send_admin_notification_func(context, admin_message, reply_markup)

    await update.message.reply_text(
        escape_markdown("تم استلام طلب السحب الخاص بك بنجاح. سيتم مراجعته من قبل الأدمن قريباً.", version=2),
        parse_mode='MarkdownV2'
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يلغي عملية السحب.
    """
    message = update.message
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(escape_markdown("تم إلغاء عملية السحب.", version=2), parse_mode='MarkdownV2')
    else:
        await message.reply_text(escape_markdown("تم إلغاء عملية السحب.", version=2), parse_mode='MarkdownV2')
    context.user_data.clear()
    return ConversationHandler.END

# --- دوال الاستثمار في البوت ---
async def start_invest_in_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يبدأ عملية الاستثمار في البوت.
    """
    user_id = update.effective_user.id
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)

    if not user_data:
        message = update.message or update.callback_query.message
        await message.reply_text(escape_markdown("يرجى التسجيل أولاً باستخدام أمر /register.", version=2), parse_mode='MarkdownV2')
        return ConversationHandler.END

    message_to_edit = update.message
    if update.callback_query:
        await update.callback_query.answer()
        message_to_edit = update.callback_query.message
        invest_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])
        try:
            await message_to_edit.edit_text(
                escape_markdown("يرجى إدخال المبلغ الذي ترغب في استثماره في البوت:", version=2),
                parse_mode='MarkdownV2',
                reply_markup=invest_markup
            )
        except Exception as e:
            logger.error(f"Error editing message in start_invest_in_bot: {e}")
            await message_to_edit.reply_text(
                escape_markdown("يرجى إدخال المبلغ الذي ترغب في استثماره في البوت:", version=2),
                parse_mode='MarkdownV2',
                reply_markup=invest_markup
            )
    else:
        invest_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]])
        await message_to_edit.reply_text(
            escape_markdown("يرجى إدخال المبلغ الذي ترغب في استثماره في البوت:", version=2),
            parse_mode='MarkdownV2',
            reply_markup=invest_markup
        )
    return ASKING_INVEST_AMOUNT

async def receive_invest_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يستقبل المبلغ المراد استثماره ويخصمه من رصيد المحفظة ويضيفه لرصيد الاستثمار.
    """
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text(escape_markdown("المبلغ يجب أن يكون أكبر من صفر. يرجى إدخال مبلغ صحيح:", version=2), parse_mode='MarkdownV2')
            return ASKING_INVEST_AMOUNT

        user_id = update.effective_user.id
        get_user_data_func = context.application.bot_data.get('get_user_data_ref')
        user_data = get_user_data_func(user_id)

        if user_data.get('wallet_balance', 0.0) < amount:
            await update.message.reply_text(escape_markdown("رصيدك في المحفظة غير كافٍ لإجراء هذه العملية.", version=2), parse_mode='MarkdownV2')
            return ConversationHandler.END

        update_wallet_balance_func = context.application.bot_data.get('update_wallet_balance_ref')
        update_investment_balance_func = context.application.bot_data.get('update_investment_balance_ref')
        
        update_wallet_balance_func(user_id, -amount)
        update_investment_balance_func(user_id, amount)

        await update.message.reply_text(
            escape_markdown(f"تم استثمار مبلغ `{amount:.2f}` USD في البوت بنجاح. يمكنك التحقق من رصيد استثمارك باستخدام أمر /balance.", version=2),
            parse_mode='MarkdownV2'
        )
        
        user_full_name = user_data.get('full_name', 'غير معروف')
        admin_message = (
            f"📈 *استثمار جديد في البوت*\n"
            f"👤 *المستخدم*: {escape_markdown(user_full_name, version=2)} \\(`{user_id}`\\)\n"
            f"💵 *المبلغ*: `{amount:.2f}` USD"
        )
        send_admin_notification_func = context.application.bot_data.get('send_admin_notification_ref')
        await send_admin_notification_func(context, admin_message)

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(escape_markdown("المبلغ غير صالح. يرجى إدخال رقم صحيح:", version=2), parse_mode='MarkdownV2')
        return ASKING_INVEST_AMOUNT

async def cancel_invest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يلغي عملية الاستثمار.
    """
    message = update.message
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(escape_markdown("تم إلغاء عملية الاستثمار.", version=2), parse_mode='MarkdownV2')
    else:
        await message.reply_text(escape_markdown("تم إلغاء عملية الاستثمار.", version=2), parse_mode='MarkdownV2')
    context.user_data.clear()
    return ConversationHandler.END

