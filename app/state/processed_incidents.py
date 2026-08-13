from threading import Lock


class ProcessedIncidents:

    def __init__(self):
        self._processed: set[str] = set()
        self._lock = Lock()

    def key(
        self,
        job_name: str,
        build_number: int,
    ) -> str:
        return f"{job_name}:{build_number}"

    def is_processed(
        self,
        job_name: str,
        build_number: int,
    ) -> bool:

        key = self.key(
            job_name,
            build_number,
        )

        with self._lock:
            return key in self._processed

    def mark_processed(
        self,
        job_name: str,
        build_number: int,
    ) -> None:

        key = self.key(
            job_name,
            build_number,
        )

        with self._lock:
            self._processed.add(key)