"""Latency Cog"""

from discord.ext.commands import Cog, command, check

from mc_backup import wh, log, MC_DATA_PATH, BACKUP_PATH, RETENTION, DockerContainer, MC_CONTAINER_NAME
from mc_backup.utils.file import FileArchive
from mc_backup.utils.permission import check_role
from mc_backup.utils.response import send_message


class Restore(Cog):
    """Get network Latency between you and server"""

    def __init__(self, bot):
        """@param bot:"""
        self._bot = bot

    @command("restore", help="Restore the Specific Backups")
    @check(check_role)
    async def restore_command(self, ctx, filename):
        """

        @param ctx:
        @return:
        @param filename:
        """
        wh.send_message("Restore Process was Initiated")
        file = FileArchive(wh, log, MC_DATA_PATH, BACKUP_PATH, RETENTION)
        mcc = DockerContainer(wh, MC_CONTAINER_NAME, log)
        try:
            mcc.stop()
            response = file.decompress_zip(filename)
            if not response:
                return await send_message(ctx, "Failed to Restore the Backup, See Logs For More Info")
            wh.send_message("Last Restore Process Was Successfully Completed")
            return await send_message(ctx, "Restore was Successfully Completed")
        finally:
            mcc.start()


async def setup(bot):
    """@param bot:"""
    await bot.add_cog(Restore(bot))
