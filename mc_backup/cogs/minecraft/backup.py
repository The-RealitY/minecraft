"""Latency Cog"""
import os
from datetime import datetime

from discord import Embed
from discord.ext.commands import Cog, command, check

from mc_backup import BACKUP_PATH, time_zone
from mc_backup.utils.permission import check_role
from mc_backup.utils.response import send_message


class Backup(Cog):
    """Get network Latency between you and server"""

    def __init__(self, bot):
        """@param bot:"""
        self._bot = bot

    @command("backup", help="View All Available Backups")
    @check(check_role)
    async def backup_command(self, ctx):
        """

        @param ctx:
        @return:
        """
        embed = Embed(title="Backups", description="Listing all the Backup", timestamp=datetime.now(tz=time_zone))

        result = "\n".join([i.name for idx, i in enumerate(os.scandir(BACKUP_PATH), start=1)])
        embed.add_field(
            name="Filename", value=result, inline=False
        )
        return await send_message(ctx, embed=embed)


async def setup(bot):
    """@param bot:"""
    await bot.add_cog(Backup(bot))
