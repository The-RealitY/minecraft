import docker
import docker.errors


class DockerContainer:
    def __init__(self, wh, container_name, log):
        """Initialize the DockerContainer class with the container's name."""
        self.webhook = wh
        self.container_name = container_name
        self.log = log
        # Initialize the Docker client
        self.client = docker.from_env()

    def stop(self):
        """Stop the Docker container and ensure it's fully stopped."""
        try:
            container = self.client.containers.get(self.container_name)
            container.stop()
            container.wait()  # Ensures that the container is fully stopped
            self.log.info(f"Container {self.container_name} fully stopped.")
            self.webhook.edit_message(f"Container {self.container_name} fully stopped.")
        except docker.errors.NotFound:
            self.log.error(f"Container {self.container_name} not found.")
            self.webhook.edit_message(f"Container {self.container_name} not found.")
        except Exception as e:
            self.log.error(f"Error stopping container {self.container_name}: {e}")
            self.webhook.edit_message(f"Error stopping container {self.container_name}: {e}")

    def restart(self):
        """Restart the Docker container."""
        try:
            container = self.client.containers.get(self.container_name)
            container.restart()
            self.log.info(f"Container {self.container_name} restarted.")
            self.webhook.edit_message(f"Container {self.container_name} restarted.")
        except docker.errors.NotFound:
            self.log.error(f"Container {self.container_name} not found.")
            self.webhook.edit_message(f"Container {self.container_name} not found.")
        except Exception as e:
            self.log.error(f"Error restarting container {self.container_name}: {e}")
            self.webhook.edit_message(f"Error restarting container {self.container_name}: {e}")