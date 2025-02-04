from datetime import datetime

from discord import SyncWebhook, Embed


class ProcessWebhook:
    def __init__(self, wh_url, log, timezone):
        """
        Initializes the ProcessWebhook with the webhook URL and logging utility.
        """
        self.webhook = SyncWebhook.from_url(wh_url)
        self.message_id = None  # To store the ID of the first message sent
        self.log = log
        self.timezone = timezone

    def send_message(self, description, color=0x3498db):
        """
        Sends a new embed message to the webhook and saves the message ID for future edits.
        """
        try:
            embed = Embed(title="Backup Server Process", description=description, color=color, timestamp=datetime.now(tz=self.timezone))
            message = self.webhook.send(embed=embed, wait=True)
            self.message_id = message.id  # Store the ID of the message
        except Exception as e:
            self.log.error(f"Failed to Send Webhook: {e}")
        return self

    def edit_message(self, description, color=0x3498db):
        """
        Edits the embed message using the saved message ID.
        """
        if self.message_id is None:
            return self
        try:
            embed = Embed(title="Backup Server Process", description=description, color=color, timestamp=datetime.now(tz=self.timezone))
            self.webhook.edit_message(self.message_id, embed=embed)
        except Exception as e:
            self.log.error(f"Failed to edit message: {e}")
        return self
