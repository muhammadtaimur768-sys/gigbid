"""`python -m worker` starts the Arq worker."""
from arq import run_worker

from worker.settings import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)  # type: ignore[arg-type]
