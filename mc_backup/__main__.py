import os
import time

from discord.ext import commands

from mc_backup import bot, DISCORD_BOT_TOKEN, log, BACKUP_INTERVAL,  wh, MC_DATA_PATH, BACKUP_PATH, RETENTION, GDRIVE_ID, ARCHIVE, time_zone
from mc_backup.utils.drive import Gdrive
from mc_backup.utils.file import FileArchive
from mc_backup.utils.scheduler import SchedulerManager
from mc_backup.utils.health import HealthChecker
from mc_backup.utils.server import HealthServer


def create_backup():
    """
    Create a backup with comprehensive error handling and progress tracking.
    """
    backup_start_time = time.time()
    
    try:
        # Initialize backup process
        wh.send_message("🚀 Backup Process Started")
        log.info("Starting backup process")
        
        # Validate paths and permissions
        if not os.path.exists(MC_DATA_PATH):
            error_msg = f"❌ Minecraft data path does not exist: {MC_DATA_PATH}"
            log.error(error_msg)
            return wh.send_message(error_msg)
        
        if not os.access(MC_DATA_PATH, os.R_OK):
            error_msg = f"❌ No read permission for Minecraft data path: {MC_DATA_PATH}"
            log.error(error_msg)
            return wh.send_message(error_msg)
        
        # Initialize backup components
        compress = FileArchive(wh, log, MC_DATA_PATH, BACKUP_PATH, RETENTION)
        
        # Compress the data with retry logic
        wh.edit_message("📦 Starting compression...")
        archived_path = compress.compress_to_zip()
        
        if not archived_path:
            error_msg = "❌ Backup Process Failed: Compression failed after multiple attempts"
            log.error(error_msg)
            return wh.send_message(error_msg)
        
        # Validate the created archive
        if not os.path.exists(archived_path):
            error_msg = "❌ Backup Process Failed: Archive file was not created"
            log.error(error_msg)
            return wh.send_message(error_msg)
        
        archive_size = os.path.getsize(archived_path)
        log.info(f"Archive created successfully: {archive_size / (1024*1024):.2f} MB")
        
        # Retain local backups (cleanup old ones)
        wh.edit_message("🧹 Cleaning up old local backups...")
        compress.retain_backup()
        
        # Upload to Google Drive
        wh.edit_message("☁️ Uploading to Google Drive...")
        gd = Gdrive(wh, log, GDRIVE_ID, RETENTION, ARCHIVE, time_zone)
        uploaded_status = gd.backup(archived_path)
        
        if not uploaded_status:
            error_msg = "❌ Backup Process Failed: Google Drive upload failed"
            log.error(error_msg)
            return wh.send_message(error_msg)
        
        # Calculate total backup time
        total_time = time.time() - backup_start_time
        
        # Success message with statistics
        success_msg = (
            f"✅ Backup Process Completed Successfully!\n"
            f"📁 Filename: {compress.filename}\n"
            f"📊 Size: {archive_size / (1024*1024):.2f} MB\n"
            f"⏱️ Total Time: {total_time:.1f} seconds\n"
            f"🚀 Speed: {archive_size / total_time / (1024*1024):.2f} MB/s"
        )
        
        log.info(f"Backup completed successfully in {total_time:.1f}s")
        return wh.edit_message(success_msg)
        
    except Exception as e:
        error_msg = f"❌ Backup Process Failed: Unexpected error - {str(e)}"
        log.error(f"Backup process failed with unexpected error: {e}", exc_info=True)
        return wh.send_message(error_msg)


@bot.event
async def on_ready():
    """Load all cogs and initialize the bot."""
    log.info("Loading Cogs, Please Wait...!")
    wh.send_message("🔄 Loading Cogs...")
    
    cog_dir = os.path.join(os.getcwd(), 'mc_backup', "cogs")
    loaded_cogs = []
    failed_cogs = []
    
    try:
        for root, _, files in os.walk(cog_dir):
            for filename in files:
                if filename.endswith(".py") and filename != "__init__.py":
                    try:
                        rel_path = os.path.relpath(
                            os.path.join(root, filename), os.path.join(os.getcwd(), 'mc_backup')
                        )
                        cog_module = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
                        cog_module = f"mc_backup.{cog_module}"
                        
                        await bot.load_extension(cog_module)
                        loaded_cogs.append(filename)
                        log.info(f"Loaded cog: {filename}")
                        
                    except Exception as e:
                        failed_cogs.append((filename, str(e)))
                        log.error(f"Failed to load cog {filename}: {e}")
        
        if loaded_cogs:
            log.info(f"Successfully loaded {len(loaded_cogs)} cogs: {', '.join(loaded_cogs)}")
        
        if failed_cogs:
            log.warning(f"Failed to load {len(failed_cogs)} cogs: {[name for name, _ in failed_cogs]}")
            for name, error in failed_cogs:
                log.error(f"  - {name}: {error}")
        
        # Send status message
        if failed_cogs:
            wh.send_message(f"⚠️ BackUp Server Online\n✅ Loaded: {len(loaded_cogs)} cogs\n❌ Failed: {len(failed_cogs)} cogs")
        else:
            wh.send_message(f"✅ BackUp Server Online\n🎯 All {len(loaded_cogs)} cogs loaded successfully")
            
    except Exception as e:
        log.error(f"Error during cog loading: {e}")
        wh.send_message(f"❌ BackUp Server Online with errors\nError: {str(e)}")


@bot.event
async def on_command_error(ctx, error):
    """Handles all errors raised during command invocation with better logging."""
    error_type = type(error)
    
    # Log the error for debugging
    log.error(f"Command error in {ctx.command}: {error}", exc_info=True)
    
    # Handle different error types
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Sorry, that command does not exist. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`\nUsage: `{ctx.command.signature}`")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("🔒 You do not have the required permissions to use this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}\nUsage: `{ctx.command.signature}`")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
    elif isinstance(error, commands.CommandError):
        await ctx.send(f"❌ Command error: {str(error)}")
    else:
        await ctx.send("❌ An unexpected error occurred. Please try again later.")
        log.error(f"Unexpected error in command {ctx.command}: {error}", exc_info=True)


if __name__ == "__main__":
    scheduler = None
    health_server = None
    
    try:
        # Validate required environment variables
        if not DISCORD_BOT_TOKEN:
            log.error("DISCORD_BOT_TOKEN is not set!")
            exit(1)
        
        if not DISCORD_WEBHOOK_URL:
            log.warning("DISCORD_WEBHOOK_URL is not set! Webhook notifications will not work.")
        
        # Initialize health checker and server
        log.info("Initializing health monitoring...")
        health_checker = HealthChecker(log)
        health_server = HealthServer(port=8080, health_checker=health_checker)
        health_server.start()
        log.info("Health server started on port 8080")
        
        # Initialize scheduler
        log.info("Initializing scheduler...")
        scheduler = SchedulerManager(log)
        
        # Add backup job
        log.info(f"Adding backup job with interval: {BACKUP_INTERVAL}")
        scheduler.add_interval_job("MineCraftBedRockBackup", create_backup, BACKUP_INTERVAL)
        
        # Start the bot
        log.info("Starting Discord bot...")
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
        
    except KeyboardInterrupt:
        log.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        log.error(f"Fatal error during startup: {e}", exc_info=True)
    finally:
        # Cleanup
        if scheduler:
            log.info("Shutting down scheduler...")
            scheduler.shutdown()
        
        if health_server:
            log.info("Shutting down health server...")
            health_server.stop()
        
        log.info("Shutdown complete")
