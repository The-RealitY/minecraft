"""Latency Cog"""
import time


from discord.ext.commands import Cog, command,check

from mc_backup.utils.permission import check_role
from mc_backup.utils.response import send_message, edit_message


class Ping(Cog):
    """Get network Latency between you and server"""

    def __init__(self, bot):
        """@param bot:"""
        self._bot = bot

    @command("ping", help="Calculate The Latency Of The Server.")
    @check(check_role)
    async def ping_command(self, ctx):
        """

        @param ctx:
        @return:
        """
        start_time = int(round(time.time() * 1000))
        msg = await send_message(ctx, "Starting Ping Test...!")
        end_time = int(round(time.time() * 1000))
        await edit_message(msg, content=f"{end_time - start_time} ms")


async def setup(bot):
    """@param bot:"""
    await bot.add_cog(Ping(bot))
