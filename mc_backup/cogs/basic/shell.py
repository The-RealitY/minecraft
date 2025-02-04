"""Terminal Cog"""
import os
import subprocess

from discord.ext.commands import Cog, command, check

from mc_backup.utils.permission import check_role
from mc_backup.utils.response import send_message, edit_message


class Shell(Cog):
    """Execute the commands in terminal"""

    def __init__(self, bot):
        """@param bot:"""
        self._bot = bot

    @command(
        "shell", help="Send Terminal Command To Execute On Machine."
    )
    @check(check_role)
    async def shell_discord(self, ctx, *args):
        """

        @param ctx:
        @param args:
        @return:
        """
        cmd = " ".join(args)
        msg = await send_message(ctx, "Running the command...")
        content = "**Shell Out**\n"
        file = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                encoding="UTF-8",
                errors="ignore",
            )
            stdout, stderr = process.communicate()
            if stdout or stderr:
                if len(stdout) + len(stderr) > 2000:
                    # Output is too long, save it to a file
                    with open(
                            os.path.join(self._bot.context.directory,
                                         "shell_out.txt"),
                            "w",
                    ) as f:
                        f.write(
                            f"**** Execution Failed ****\n{stderr}\n\n**** \
                                                    Execution Success ****\n{stdout}"
                        )
                    content += "Output is too long, saved to a file."
                    file = os.path.join(self._bot.context.directory, "shell_out.txt")
                else:
                    if stdout:
                        content += f"```<---Execution Succeed--->\n\n{stdout}```"
                    if stderr:
                        content += f"```<---Execution Failed--->\n\n{stdout}```"
            else:
                content += "***Unknown Status***\nExecution May Passed Or Failed..!"
        except subprocess.SubprocessError as e:
            content += f"***Unable To Execute The Command***\n{str(e)}"
        finally:
            await edit_message(msg, content, files=file)


async def setup(bot):
    """@param bot:"""
    await bot.add_cog(Shell(bot))
