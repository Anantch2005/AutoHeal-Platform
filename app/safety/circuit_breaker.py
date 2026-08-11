from collections import defaultdict
from datetime import datetime, timedelta


class CircuitBreaker:

    def __init__(
        self,
        max_attempts: int = 3,
        window_minutes: int = 30,
    ):
        self.max_attempts = max_attempts
        self.window = timedelta(minutes=window_minutes)

        self.attempts = defaultdict(list)

    def allow(
        self,
        job_name: str,
        category: str,
    ) -> bool:

        key = f"{job_name}:{category}"

        now = datetime.utcnow()

        # Remove old attempts
        self.attempts[key] = [
            timestamp
            for timestamp in self.attempts[key]
            if now - timestamp < self.window
        ]

        if len(self.attempts[key]) >= self.max_attempts:
            return False

        self.attempts[key].append(now)

        return True

    def get_attempt_count(
        self,
        job_name: str,
        category: str,
    ) -> int:

        key = f"{job_name}:{category}"

        now = datetime.utcnow()

        self.attempts[key] = [
            timestamp
            for timestamp in self.attempts[key]
            if now - timestamp < self.window
        ]

        return len(self.attempts[key])

    def reset(
        self,
        job_name: str,
        category: str,
    ):
        key = f"{job_name}:{category}"

        self.attempts.pop(key, None)