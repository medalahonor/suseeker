import inspect
import colorama
from gevent.lock import RLock


class LogTypes:
    DEBUG = colorama.Fore.LIGHTYELLOW_EX + 'DEBUG' + colorama.Style.RESET_ALL
    INFO = colorama.Fore.BLUE + 'INFO' + colorama.Style.RESET_ALL
    SUCCESS = colorama.Fore.GREEN + 'SUCCESS' + colorama.Style.RESET_ALL
    WARNING = colorama.Fore.YELLOW + 'WARNING' + colorama.Style.RESET_ALL
    ERROR = colorama.Fore.RED + 'ERROR' + colorama.Style.RESET_ALL


class Logger:
    def __init__(self, args):
        self.args = args

        self.print_lock = RLock()

    def _print(self, type, msg):
        with self.print_lock:
            f = inspect.currentframe().f_back.f_back

            if self.args.verbosity == 3:
                print(f'[{type}][{f.f_globals["__name__"]}][{f.f_code.co_name}]: {msg}')
            else:
                print(f'[{type}]: {msg}')

    def debug(self, msg):
        if self.args.verbosity == 3:
            self._print(LogTypes.DEBUG, msg)

    def info(self, msg):
        if self.args.verbosity >= 1:
            self._print(LogTypes.INFO, msg)

    def success(self, msg):
        if self.args.verbosity >= 1:
            self._print(LogTypes.SUCCESS, msg)

    def warning(self, msg):
        if self.args.verbosity >= 2:
            self._print(LogTypes.WARNING, msg)

    def error(self, msg):
        if self.args.verbosity >= 2:
            self._print(LogTypes.ERROR, msg)