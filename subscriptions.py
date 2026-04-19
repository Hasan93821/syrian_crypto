import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
import asyncio
import random
from telegram.error import BadRequest
import json
import math
import pytz

SELECT_SUBSCRIPTION_PLAN, SELECT_TRADING_PAIRS, CONFIRM_SUBSCRIPTION = range(30, 33)

logger = logging.getLogger(__name__)

MONTHLY_COST = 10.0
ANNUAL_COST = 100.0
FREE_PLAN_DAILY_LIMIT = 3

PAIRS_PER_PAGE = 10


async def start_subscription_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يبدأ عملية الاشتراك في التوصيات التلقائية ويعرض خطط الاشتراك.
    """
    logger.info(f"User {update.effective_user.id} started subscription process.")
    user_id = update.effective_user.id

    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    user_data = get_user_data_func(user_id)

    if not user_data:
        message = update.message or update.callback_query.message
        await message.reply_text(escape_markdown("يرجى التسجيل أولاً باستخدام أمر /register.", version=2), parse_mode='MarkdownV2')
        return ConversationHandler.END

    get_subscription_info_func = context.application.bot_data.get('get_subscription_info_ref')
    subscription_info = get_subscription_info_func(user_id)

    message_to_use = update.message
    if update.callback_query:
        await update.callback_query.answer()
        message_to_use = update.callback_query.message

    current_plan_info = ""
    if subscription_info and subscription_info['is_subscribed']:
        plan_name = subscription_info['plan_name'] or ''
        expiry_date = subscription_info['expiry_date'] or ''
        pairs_list = subscription_info['subscribed_pairs']
        subscribed_pairs_str = ", ".join(pairs_list) if pairs_list else "لا توجد أزواج محددة"

        current_plan_info = escape_markdown(
            f"أنت مشترك حالياً في خطة {plan_name}.\n"
            f"تنتهي صلاحية اشتراكك في: {expiry_date}\n"
            f"أزواج التداول المشترك بها: {subscribed_pairs_str}\n\n",
            version=2
        )

    keyboard = [
        [InlineKeyboardButton(f"خطة شهرية - {MONTHLY_COST:.2f}$ 🗓️", callback_data="select_plan_monthly")],
        [InlineKeyboardButton(f"خطة سنوية - {ANNUAL_COST:.2f}$ yearly 📅", callback_data="select_plan_annual")],
        [InlineKeyboardButton(f"الخطة المجانية (حد {FREE_PLAN_DAILY_LIMIT} توصية يومياً) ✨", callback_data="select_plan_free")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"),
         InlineKeyboardButton("إلغاء ❌", callback_data="cancel_subscription")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = current_plan_info + escape_markdown("يرجى اختيار خطة الاشتراك التي تناسبك للحصول على توصيات التداول:", version=2)

    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    except BadRequest as e:
        logger.error(f"Failed to send subscription options: {e}")
        await message_to_use.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')

    return SELECT_SUBSCRIPTION_PLAN


async def select_subscription_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يحدد خطة الاشتراك المختارة ويطلب اختيار أزواج التداول.
    """
    query = update.callback_query
    await query.answer()
    plan_type = query.data.replace('select_plan_', '')
    context.user_data['chosen_plan'] = plan_type

    if plan_type == 'free':
        await send_confirmation_message(update, context)
        return CONFIRM_SUBSCRIPTION

    context.user_data['pair_selection_page'] = 0
    await send_pair_selection_message(update, context)
    return SELECT_TRADING_PAIRS


async def send_pair_selection_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يرسل رسالة اختيار أزواج التداول مع ترقيم الصفحات.
    """
    query = update.callback_query

    all_pairs = context.user_data.get('cached_all_pairs')
    if not all_pairs:
        if query:
            try:
                await query.edit_message_text(escape_markdown("⏳ جاري تحميل قائمة الأزواج، يرجى الانتظار...", version=2), parse_mode='MarkdownV2')
            except Exception:
                pass
        get_all_usdt_pairs_func = context.application.bot_data.get('get_all_usdt_pairs_ref')
        all_pairs = await get_all_usdt_pairs_func()
        context.user_data['cached_all_pairs'] = all_pairs

    logger.info(f"subscriptions.py: Using {len(all_pairs)} pairs.")

    selected_pairs = context.user_data.get('selected_pairs', [])
    current_page = context.user_data.get('pair_selection_page', 0)

    total_pairs = len(all_pairs)
    total_pages = math.ceil(total_pairs / PAIRS_PER_PAGE) if total_pairs > 0 else 1

    if current_page >= total_pages and total_pages > 0:
        current_page = total_pages - 1
        context.user_data['pair_selection_page'] = current_page
    elif current_page < 0:
        current_page = 0
        context.user_data['pair_selection_page'] = current_page

    start_index = current_page * PAIRS_PER_PAGE
    end_index = start_index + PAIRS_PER_PAGE
    pairs_on_page = all_pairs[start_index:end_index]

    keyboard = []
    for i in range(0, len(pairs_on_page), 2):
        row = []
        for pair in pairs_on_page[i:i+2]:
            button_text = f"{pair} {'✅' if pair in selected_pairs else '❌'}"
            row.append(InlineKeyboardButton(button_text, callback_data=f"pair_toggle_{pair}"))
        keyboard.append(row)

    pagination_buttons = []
    if total_pages > 1:
        if current_page > 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"pair_page_{current_page - 1}"))
        if current_page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"pair_page_{current_page + 1}"))

    if pagination_buttons:
        keyboard.append(pagination_buttons)

    keyboard.append([InlineKeyboardButton("تم الاختيار ✅", callback_data="select_pairs_done")])
    keyboard.append([InlineKeyboardButton("العودة لخطط الاشتراك ↩️", callback_data="back_to_plans")])
    keyboard.append([InlineKeyboardButton("إلغاء ❌", callback_data="cancel_subscription")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = escape_markdown(
        f"يرجى اختيار أزواج التداول التي ترغب في تلقي توصيات لها (صفحة {current_page + 1} من {total_pages}):",
        version=2
    )

    try:
        if query:
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    except BadRequest as e:
        logger.error(f"Failed to send pair selection message: {e}")
        message_to_use = update.callback_query.message if update.callback_query else update.message
        await message_to_use.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')


async def select_trading_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يتعامل مع اختيار أزواج التداول والتنقل بين الصفحات.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    selected_pairs = context.user_data.get('selected_pairs', [])

    if data.startswith('pair_toggle_'):
        pair = data.replace('pair_toggle_', '')
        if pair in selected_pairs:
            selected_pairs.remove(pair)
        else:
            selected_pairs.append(pair)
        context.user_data['selected_pairs'] = selected_pairs
        logger.info(f"User {update.effective_user.id} toggled pair {pair}. Selected: {selected_pairs}")
        await send_pair_selection_message(update, context)
        return SELECT_TRADING_PAIRS

    elif data.startswith('pair_page_'):
        new_page = int(data.replace('pair_page_', ''))
        context.user_data['pair_selection_page'] = new_page
        await send_pair_selection_message(update, context)
        return SELECT_TRADING_PAIRS

    elif data == 'select_pairs_done':
        if not selected_pairs:
            await query.answer("الرجاء اختيار زوج تداول واحد على الأقل.", show_alert=True)
            return SELECT_TRADING_PAIRS
        await send_confirmation_message(update, context)
        return CONFIRM_SUBSCRIPTION

    elif data == 'back_to_plans':
        context.user_data.pop('selected_pairs', None)
        context.user_data.pop('pair_selection_page', None)
        return await start_subscription_process(update, context)

    return SELECT_TRADING_PAIRS


async def send_confirmation_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يرسل رسالة تأكيد الاشتراك.
    """
    query = update.callback_query
    chosen_plan = context.user_data.get('chosen_plan')
    selected_pairs = context.user_data.get('selected_pairs', [])

    cost = 0.0
    plan_display_name = ""
    if chosen_plan == 'monthly':
        cost = MONTHLY_COST
        plan_display_name = "شهرية"
    elif chosen_plan == 'annual':
        cost = ANNUAL_COST
        plan_display_name = "سنوية"
    elif chosen_plan == 'free':
        plan_display_name = "مجانية"

    if chosen_plan == 'free':
        message_text = escape_markdown(
            f"لقد اخترت الخطة المجانية.\n"
            f"ستتلقى {FREE_PLAN_DAILY_LIMIT} توصية يومياً.\n",
            version=2
        )
    else:
        message_text = escape_markdown(
            f"لقد اخترت الخطة {plan_display_name}.\n"
            f"التكلفة: {cost:.2f} USD.\n",
            version=2
        )

    if selected_pairs:
        message_text += escape_markdown(f"أزواج التداول المختارة: {', '.join(selected_pairs)}\n", version=2)
    else:
        message_text += escape_markdown("لم يتم اختيار أزواج تداول. ستتلقى توصيات عشوائية أو حسب إعدادات البوت الافتراضية.", version=2)

    message_text += escape_markdown("\n\nهل أنت متأكد من رغبتك في الاشتراك بهذه الخطة؟", version=2)

    keyboard = [
        [InlineKeyboardButton("تأكيد الاشتراك ✅", callback_data="confirm_subscription")],
        [InlineKeyboardButton("العودة لاختيار الأزواج ↩️", callback_data="back_to_pairs")]
    ]
    if chosen_plan != 'free':
        keyboard.append([InlineKeyboardButton("العودة لخطط الاشتراك ↩️", callback_data="back_to_plans")])
    keyboard.append([InlineKeyboardButton("إلغاء ❌", callback_data="cancel_subscription")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    except BadRequest as e:
        logger.error(f"Failed to send confirmation message: {e}")
        await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='MarkdownV2')


async def confirm_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يؤكد الاشتراك ويخصم المبلغ من رصيد المحفظة.
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    chosen_plan = context.user_data.get('chosen_plan')
    selected_pairs = context.user_data.get('selected_pairs', [])

    get_user_data_func = context.application.bot_data.get('get_user_data_ref')
    update_wallet_balance_func = context.application.bot_data.get('update_wallet_balance_ref')
    update_subscription_status_func = context.application.bot_data.get('update_subscription_status_ref')
    update_subscribed_pairs_func = context.application.bot_data.get('update_subscribed_pairs_ref')

    user_data = get_user_data_func(user_id)
    wallet_balance = user_data.get('wallet_balance', 0.0)

    cost = 0.0
    expiry_date = None
    if chosen_plan == 'monthly':
        cost = MONTHLY_COST
        expiry_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    elif chosen_plan == 'annual':
        cost = ANNUAL_COST
        expiry_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
    elif chosen_plan == 'free':
        expiry_date = (datetime.now() + timedelta(days=365 * 10)).strftime('%Y-%m-%d %H:%M:%S')

    if chosen_plan != 'free' and wallet_balance < cost:
        await query.edit_message_text(
            escape_markdown("رصيدك في المحفظة غير كافٍ للاشتراك في هذه الخطة. يرجى إيداع المزيد من الأموال.", version=2),
            parse_mode='MarkdownV2'
        )
        context.user_data.clear()
        return ConversationHandler.END

    if chosen_plan != 'free':
        update_wallet_balance_func(user_id, -cost)

    update_subscription_status_func(user_id, True, chosen_plan, expiry_date)
    update_subscribed_pairs_func(user_id, selected_pairs)

    if chosen_plan == 'free':
        confirmation_message = escape_markdown(
            f"تهانينا! لقد تم تفعيل الخطة المجانية بنجاح. ستبدأ في تلقي {FREE_PLAN_DAILY_LIMIT} توصية يومياً.",
            version=2
        )
    else:
        confirmation_message = escape_markdown(
            f"تهانينا! لقد تم الاشتراك في الخطة {chosen_plan} بنجاح. تم خصم {cost:.2f} USD من محفظتك.",
            version=2
        )

    await query.edit_message_text(confirmation_message, parse_mode='MarkdownV2')

    context.application.job_queue.run_once(
        _send_immediate_recommendations,
        when=3,
        data={'user_id': user_id, 'selected_pairs': selected_pairs, 'plan_name': chosen_plan},
        name=f"immediate_rec_{user_id}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def _send_immediate_recommendations(context: ContextTypes.DEFAULT_TYPE):
    """
    يرسل توصيات فورية للمستخدم بعد الاشتراك مباشرة.
    """
    job_data = context.job.data
    user_id = job_data['user_id']
    selected_pairs = job_data['selected_pairs']
    plan_name = job_data['plan_name']

    if plan_name == 'free':
        daily_limit = FREE_PLAN_DAILY_LIMIT
    elif plan_name == 'monthly':
        daily_limit = 5
    elif plan_name == 'annual':
        daily_limit = 10
    else:
        daily_limit = 1

    get_crypto_data_func = context.application.bot_data.get('get_crypto_data_ref')
    generate_trading_signal_func = context.application.bot_data.get('generate_trading_signal_ref')
    format_signal_func = context.application.bot_data.get('format_signal_ref')
    update_daily_recommendations_count_func = context.application.bot_data.get('update_daily_recommendations_count_ref')
    get_user_data_func = context.application.bot_data.get('get_user_data_ref')

    await context.bot.send_message(
        user_id,
        escape_markdown("📊 جاري إعداد توصياتك الأولى، يرجى الانتظار...", version=2),
        parse_mode='MarkdownV2'
    )

    user_db = get_user_data_func(user_id)
    sent_count = user_db.get('daily_recommendations_count', 0)
    shuffled_pairs = selected_pairs[:]
    random.shuffle(shuffled_pairs)

    for pair in shuffled_pairs:
        if sent_count >= daily_limit:
            break
        try:
            df = await get_crypto_data_func(pair, '1h')
            if df is None or df.empty:
                logger.warning(f"No data for {pair} in immediate recommendations for user {user_id}.")
                continue
            signal = generate_trading_signal_func(df)
            if signal:
                formatted = format_signal_func(signal, pair)
                await context.bot.send_message(user_id, formatted, parse_mode='MarkdownV2')
                sent_count += 1
                update_daily_recommendations_count_func(user_id, sent_count)
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error in immediate recommendation for user {user_id}, pair {pair}: {e}")

    if sent_count == 0:
        await context.bot.send_message(
            user_id,
            escape_markdown("ℹ️ لا توجد إشارات قوية في الوقت الحالي. ستتلقى توصياتك في الساعة 9 صباحاً يومياً.", version=2),
            parse_mode='MarkdownV2'
        )


async def cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    يلغي عملية الاشتراك.
    """
    message = update.message
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            escape_markdown("تم إلغاء عملية الاشتراك.", version=2), parse_mode='MarkdownV2'
        )
    else:
        await message.reply_text(escape_markdown("تم إلغاء عملية الاشتراك.", version=2), parse_mode='MarkdownV2')
    context.user_data.clear()
    return ConversationHandler.END


async def check_and_send_daily_recommendations(context: ContextTypes.DEFAULT_TYPE):
    """
    تفحص المستخدمين المؤهلين وترسل لهم توصيات التداول اليومية.
    هذه الدالة ستُشغل بواسطة JobQueue.
    """
    logger.info("Running daily recommendations check...")
    get_all_users_data_func = context.application.bot_data.get('get_all_users_data_ref')
    get_subscription_info_func = context.application.bot_data.get('get_subscription_info_ref')
    update_daily_recommendations_count_func = context.application.bot_data.get('update_daily_recommendations_count_ref')
    get_crypto_data_func = context.application.bot_data.get('get_crypto_data_ref')
    generate_trading_signal_func = context.application.bot_data.get('generate_trading_signal_ref')
    format_signal_func = context.application.bot_data.get('format_signal_ref')

    all_users = get_all_users_data_func()

    damascus_tz = pytz.timezone('Asia/Damascus')
    now_damascus = datetime.now(damascus_tz)
    today = now_damascus.strftime('%Y-%m-%d')
    logger.info(f"Current time in Damascus: {now_damascus}. Today's date: {today}")

    for user_id_str, user_info in all_users.items():
        user_id = int(user_id_str)
        logger.info(f"Checking recommendations for user: {user_id}")

        last_recommendation_date = user_info.get('last_recommendation_date')
        if last_recommendation_date != today:
            logger.info(f"Resetting daily recommendation count for user {user_id}.")
            update_daily_recommendations_count_func(user_id, 0)
            user_info['daily_recommendations_count'] = 0

        subscription_info = get_subscription_info_func(user_id)
        logger.info(f"Subscription info for user {user_id}: {subscription_info}")

        if not subscription_info:
            continue

        is_subscribed = subscription_info.get('is_subscribed')
        expiry_date_str = subscription_info.get('expiry_date')
        is_active_subscription = False
        if is_subscribed and expiry_date_str:
            try:
                expiry_dt_utc = datetime.strptime(expiry_date_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
                now_utc = datetime.now(pytz.utc)
                is_active_subscription = expiry_dt_utc > now_utc
            except ValueError as e:
                logger.error(f"Error parsing expiry date for user {user_id}: {expiry_date_str} - {e}")
                is_active_subscription = False

        if not is_active_subscription:
            logger.info(f"User {user_id} is not subscribed or subscription expired. Skipping.")
            continue

        plan_name = subscription_info['plan_name']
        daily_limit = 0
        if plan_name == "monthly":
            daily_limit = 5
        elif plan_name == "annual":
            daily_limit = 10
        elif plan_name == "free":
            daily_limit = FREE_PLAN_DAILY_LIMIT

        sent_count = user_info.get('daily_recommendations_count', 0)

        if sent_count >= daily_limit:
            logger.info(f"User {user_id} reached daily limit. Skipping.")
            continue

        subscribed_pairs = user_info.get('subscribed_pairs', [])
        if not subscribed_pairs:
            logger.info(f"User {user_id} has no subscribed pairs. Skipping.")
            continue

        random.shuffle(subscribed_pairs)

        for pair in subscribed_pairs:
            if sent_count >= daily_limit:
                break
            try:
                df = await get_crypto_data_func(pair, '1h')
                if df is None or df.empty:
                    logger.warning(f"No data fetched for {pair} for user {user_id}.")
                    continue

                signal = generate_trading_signal_func(df)

                if signal:
                    formatted_signal = format_signal_func(signal, pair)
                    await context.bot.send_message(user_id, formatted_signal, parse_mode='MarkdownV2')
                    sent_count += 1
                    update_daily_recommendations_count_func(user_id, sent_count)
                    await asyncio.sleep(0.5)
                else:
                    logger.info(f"No strong signal for {pair} for user {user_id}.")
            except BadRequest as e:
                logger.error(f"Failed to send recommendation to user {user_id} for pair {pair}: {e}")
            except Exception as e:
                logger.error(f"Error generating or sending signal for user {user_id}, pair {pair}: {e}")

    logger.info("Daily recommendations check completed.")
