import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID', 0))

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PORT = os.getenv("WEBHOOK_PORT")
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN")
WEBHOOK_CERT = os.getenv("WEBHOOK_CERT")
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")

USDT_CWALLET_ADDRESS = os.environ.get('USDT_CWALLET_ADDRESS', '')
USDT_BINANCE_ADDRESS = os.environ.get('USDT_BINANCE_ADDRESS', '')
USDT_EXTERNAL_ADDRESS = os.environ.get('USDT_EXTERNAL_ADDRESS', '')

SHAM_CASH_NUMBER = os.environ.get('SHAM_CASH_NUMBER', '')
SYRIATEL_CASH_NUMBER = os.environ.get('SYRIATEL_CASH_NUMBER', '')
PAYER_ACCOUNT = os.environ.get('PAYER_ACCOUNT', '')
BANK_TRANSFER_DETAILS = os.environ.get('BANK_TRANSFER_DETAILS', '')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set.")
if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID environment variable not set.")
if not USDT_CWALLET_ADDRESS:
    raise ValueError("USDT_CWALLET_ADDRESS environment variable not set.")
if not USDT_BINANCE_ADDRESS:
    raise ValueError("USDT_BINANCE_ADDRESS environment variable not set.")
if not USDT_EXTERNAL_ADDRESS:
    raise ValueError("USDT_EXTERNAL_ADDRESS environment variable not set.")
if not SHAM_CASH_NUMBER:
    raise ValueError("SHAM_CASH_NUMBER environment variable not set.")
if not SYRIATEL_CASH_NUMBER:
    raise ValueError("SYRIATEL_CASH_NUMBER environment variable not set.")
if not PAYER_ACCOUNT:
    raise ValueError("PAYER_ACCOUNT environment variable not set.")
if not BANK_TRANSFER_DETAILS:
    raise ValueError("BANK_TRANSFER_DETAILS environment variable not set.")
