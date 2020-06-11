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
        """ Определяет, работает ли воркер над некоторой задачей в данный момент времени

        :return:
        """
        return self._running

    def is_stopped(self):
        """ Определяет, остановлен ли воркер в данный момент времени после получения команды finish()

        :return:
        """
        return self._stopped


