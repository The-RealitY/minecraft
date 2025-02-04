from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


class SchedulerManager:
    def __init__(self, log):
        """Initialize the APScheduler with a database-backed job store."""
        self.scheduler = BackgroundScheduler(
            jobstores={
                'default': MemoryJobStore()
            },
            executors={
                'default': ThreadPoolExecutor(10)
            },
            job_defaults={
                'coalesce': False,
                'max_instances': 1
            }
        )
        self.log = log
        self.safe_start_scheduler()

        # Register listeners for logging or debugging
        self.scheduler.add_listener(self.job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    def safe_start_scheduler(self):
        try:
            self.scheduler.start()
        except Exception as e:
            self.log.error(f"Database schema issue: {e}")
            return None

    def job_listener(self, event):
        """Log job execution or errors."""
        if event.exception:
            self.log.error(f"Job {event.job_id} failed: {event.exception}")
        else:
            self.log.info(f"Job {event.job_id} executed successfully.")

    def add_one_time_job(self, job_id, func, run_date, args=None):
        """Add a new one-time job to the scheduler."""
        self.remove_job(job_id)  # Remove existing job if it exists
        try:
            self.scheduler.add_job(
                func=func,
                trigger='date',
                run_date=run_date,
                args=args,
                id=job_id  # Unique identifier for the job
            )
            self.log.info(f"One-time job {job_id} added, scheduled for {run_date}.")
        except Exception as e:
            self.log.error(f"Failed to add one-time job {job_id}: {e}")

    def add_daily_job(self, job_id, func, hour=0, minute=0, second=0, args=None):
        """Add a recurring daily job at a specified time."""
        self.remove_job(job_id)  # Remove existing job if it exists
        try:
            trigger = CronTrigger(hour=hour, minute=minute, second=second)
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                args=args,
                id=job_id,  # Unique identifier for the job
                replace_existing=True  # Allow replacement of jobs with the same ID
            )
            self.log.info(f"Daily job {job_id} added to run at {hour:02}:{minute:02}:{second:02}.")
        except Exception as e:
            self.log.error(f"Failed to add daily job {job_id}: {e}")

    def add_interval_job(self, job_id, func, interval, args=None):
        """
        Add a recurring job at a specified interval.

        :param job_id: Unique identifier for the job.
        :param func: Function to execute.
        :param interval: Interval in the format '1H', '30M', '10S'.
        :param args: Arguments to pass to the function.
        """
        self.remove_job(job_id)  # Remove existing job if it exists
        try:
            # Parse interval
            seconds = self._parse_interval(interval)
            trigger = IntervalTrigger(seconds=seconds)
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                args=args,
                id=job_id,  # Unique identifier for the job
                replace_existing=True,  # Allow replacement of jobs with the same ID
                misfire_grace_time=30
            )
            self.log.info(f"Interval job {job_id} added to run every {interval}.")
        except Exception as e:
            self.log.error(f"Failed to add interval job {job_id}: {e}")

    def _parse_interval(self, interval):
        """Parse interval strings like '1H', '30M', '10S' into seconds."""
        self.log.info("Parsing the given Interval")
        unit = interval[-1].upper()
        value = int(interval[:-1])
        if unit == 'H':
            return value * 3600
        elif unit == 'M':
            return value * 60
        elif unit == 'S':
            return value
        else:
            raise ValueError(f"Invalid interval format: {interval}")

    def remove_job(self, job_id):
        """Remove a job by its ID."""
        try:
            self.scheduler.remove_job(job_id)
            self.log.info(f"Existing job {job_id} removed before adding a new one.")
        except JobLookupError:
            self.log.info(f"No existing job found with ID {job_id}, proceeding to add a new one.")
        except Exception as e:
            self.log.error(f"Failed to remove job {job_id}: {e}")

    def get_job(self, job_id):
        """Retrieve a job by its ID."""
        try:
            return self.scheduler.get_job(job_id)
        except JobLookupError:
            return None

    def shutdown(self):
        """Gracefully shut down the scheduler."""
        self.scheduler.shutdown()
        self.log.info("Scheduler shut down.")
