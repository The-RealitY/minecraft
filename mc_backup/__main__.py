import os

from discord.ext import commands

from mc_backup import bot, DISCORD_BOT_TOKEN, log, BACKUP_INTERVAL, SchedulerManager, wh, MC_DATA_PATH, BACKUP_PATH, RETENTION, GDRIVE_ID, ARCHIVE, time_zone
from mc_backup.utils.drive import Gdrive
from mc_backup.utils.file import FileArchive


def create_backup():
    # Initialize backup object and file compression utility
    wh.send_message("Backup Process Started")
    compress = FileArchive(wh, log, MC_DATA_PATH, BACKUP_PATH, RETENTION)
    # Compress the data and handle failure
    archived_path = compress.compress_to_zip()
    if not archived_path:
        return wh.send_message("Last Backup Process Failed while Zipping, See Logs...")
    # Retain the backup locally (keeping the latest backups)
    compress.retain_backup()
    # Initialize Google Drive backup class
    gd = Gdrive(wh, log, GDRIVE_ID, RETENTION, ARCHIVE,time_zone)
    uploaded_status = gd.backup(archived_path)
    # Handle upload failure
    if not uploaded_status:
        return wh.send_message("Last Backup Process Failed while Uploading to Gdrive, See Logs...")
    # Mark backup as successful and commit to database
    log.info("Backup was successfully completed.")
    return wh.edit_message(f"Last Backup Process Succeed\nFilename: {compress.filename}\n")


@bot.event
async def on_ready():
    """@return:"""
    log.info("Loading Cogs, Please Wait...!")
    cog_dir = os.path.join(os.getcwd(), 'mc_backup', "cogs")
    for root, _, files in os.walk(cog_dir):
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                rel_path = os.path.relpath(
                    os.path.join(root, filename), os.path.join(os.getcwd(), 'mc_backup')
                )
                cog_module = os.path.splitext(rel_path)[0].replace(
                    os.path.sep, "."
                )
                cog_module = f"mc_backup.{cog_module}"
                await bot.load_extension(cog_module)
    log.info("All Cogs Are Loaded Successfully")
    wh.send_message("BackUp Server Online")


@bot.event
async def on_command_error(ctx, error):
    """Handles all errors raised during command invocation."""
    match type(error):
        case commands.CommandNotFound:
            await ctx.send("Sorry, that command does not exist.")
        case commands.MissingRequiredArgument:
            await ctx.send(f"Missing required argument: {error.param}")
        case commands.CheckFailure:
            await ctx.send("You do not have the required permissions to use this command.")
        case commands.CommandError:
            await ctx.send(f"An error occurred: {str(error)}")
        case _:
            await ctx.send("An unexpected error occurred.")


if __name__ == "__main__":
    scheduler = SchedulerManager(log)
    scheduler.add_interval_job("MineCraftBedRockBackup", create_backup, BACKUP_INTERVAL)
    bot.run(DISCORD_BOT_TOKEN,
            log_handler=None
            )
