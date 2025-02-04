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
        """Stop the Docker container."""
        try:
            container = self.client.containers.get(self.container_name)
            container.stop()
            self.log.info(f"Container {self.container_name} stopped.")
            self.webhook.edit_message(f"Container {self.container_name} stopped.")
        except docker.errors.NotFound:
            self.log.error(f"Container {self.container_name} not found.")
            self.webhook.edit_message(f"Container {self.container_name} not found.")
        except Exception as e:
            self.log.error(f"Error stopping container {self.container_name}: {e}")
            self.webhook.edit_message(f"Error stopping container {self.container_name}: {e}")

    def start(self):
        """Start the Docker container."""
        try:
            container = self.client.containers.get(self.container_name)
            container.start()
            self.log.info(f"Container {self.container_name} started.")
            self.webhook.edit_message(f"Container {self.container_name} started.")
        except docker.errors.NotFound:
            self.log.error(f"Container {self.container_name} not found.")
            self.webhook.edit_message(f"Container {self.container_name} not found.")
        except Exception as e:
            self.log.error(f"Error starting container {self.container_name}: {e}")
            self.webhook.edit_message(f"Error starting container {self.container_name}: {e}")
