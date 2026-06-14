"""Windows-friendly RQ worker entrypoint."""

from __future__ import annotations

import sys

from rq import SimpleWorker

from metaos.tasks.queueing import QueueName, redis_connection, rq_queue


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    queue_names = args or [QueueName.ingest.value, QueueName.index.value, QueueName.rag.value]
    queues = [rq_queue(name) for name in queue_names]
    worker = SimpleWorker(queues, connection=redis_connection())
    worker.work()


if __name__ == "__main__":
    main()
