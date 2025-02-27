import logging
import os

import discord
import pytz
from discord.ext.commands import Bot

from mc_backup.utils.command import MyHelpCommand
from mc_backup.utils.container import DockerContainer
from mc_backup.utils.notifi import ProcessWebhook
from mc_backup.utils.scheduler import SchedulerManager

TZ = os.getenv('TZ', 'Asia/Kolkata')
MC_DATA_PATH = os.path.join(os.getcwd(), 'data')
BACKUP_PATH = os.path.join(os.getcwd(), 'backup')
BACKUP_INTERVAL = os.getenv('BACKUP_INTERVAL', '30M')
RETENTION = int(os.getenv('RETENTION', 5))
ARCHIVE = int(os.getenv('ARCHIVE', 7))
GDRIVE_ID = os.getenv('GDRIVE_ID', 'root')
LOG_FILE = os.path.join(os.getcwd(), 'system.log')
MC_CONTAINER_NAME = "mc-br"
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', '')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
DISCORD_AUTH_ROLES = [int(i) for i in os.getenv('DISCORD_AUTH_ROLES', "0").split(',')]
# Create logger formatter
logging.basicConfig(
    format=f"|| {__name__} || %(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(f"{LOG_FILE}", encoding="UTF-8"),
              logging.StreamHandler()],
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.DEBUG,
)
log = logging.getLogger(__name__)
time_zone = pytz.timezone(TZ)
bot = Bot("!", intents=discord.Intents.all(), help_command=MyHelpCommand())
wh = ProcessWebhook(DISCORD_WEBHOOK_URL, log, time_zone)
