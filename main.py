CONFIRM_SUBSCRIPTION: [
    CallbackQueryHandler(confirm_subscription, pattern=r'^confirm_subscription$'),
    CallbackQueryHandler(select_trading_pairs, pattern=r'^back_to_pairs$')
]