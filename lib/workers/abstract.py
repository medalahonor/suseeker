class AbstractWorker:
    def __init__(self):
        self._running = False
        self._finish = False
        self._stopped = False

    def run(self):
        raise NotImplementedError

    def finish(self):
        self._finish = True

    def is_running(self):
        return self._running

    def is_stopped(self):
        return self._stopped