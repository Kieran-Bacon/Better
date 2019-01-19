import os
import time
import logging
import threading
import multiprocessing as mp

from ._exceptions import SubprocessException
from ._mplogging import LogPipeThread, LogPipeHandler

class Communication:
    """ An object to handle communication with the pool manager

    Params:
        processes (int): The number of processes the pool is maintaining

    Unordered Params:
        loggers (dict): A dictionary of loggers mapping logger name to logger object
        ordered (bool): Toggle the output to be ordered
        queue_size (int): The total number of items that can be placed into the work stream
    """

    _RUNNING = 10
    _CLOSED = 20

    def __init__(self, pool, *, loggers: dict = {}, ordered: bool = False, queue_size: int = None):

        self._pool = pool
        self._state = self._RUNNING
        self._active = 0  # The number of current work that is active
        self._pool_size = pool._pool_size  # The maximun number of processes
        self._ordered = ordered  # A bool to toggle whether the output are to be ordered or simply returned

        # Structures for ensuring ordered response from processes
        if self._ordered:
            self._returnIndex = 0
            self._returnCache = {}

        # Set up default values for queue size
        if isinstance(queue_size, bool) and queue_size is False: size = None
        else: size = queue_size if queue_size is not None else self._pool_size*2

        # Set up the logging thread and handling
        self._logger_names = list(loggers.keys())
        self._loggingPipe = None
        if loggers:
            self._loggingPipe = mp.Pipe()
            self._loggerThread = LogPipeThread(self._loggingPipe, loggers)
            self._loggerThread.start()

        # Generic send and receive queues
        self._sendQueue = mp.Queue(size)
        self._returnQueue = mp.Queue()

        self._index = 0
        self._asyncThread = None
        self._clearingTasks = False

    def put(self, *items, block: bool = True, timeout: float = None) -> None:
        """ Place an item in the work stream, this will hold the inputs for the subprocesses. The method will block if
        the queue is full

        Params:
            item (object): The item to be passed to the subprocesses
            block (bool) = True: The placing attitude
            timeout (float) = None: A timeout for trying to place item
        """
        if len(items) < 1: raise TypeError("put method must take at least one argument")
        if len(items) == 1: items = items[0]
        else: items = tuple(items)

        self._sendQueue.put((self._index, items), block=block, timeout=timeout)
        self._active += 1
        self._index += 1

    def put_async(self, iterable: object):
        """ Take a iterable of tasks and send the items to the waiting processes without blocking the main threads
        execution. This method sets up a thread that shall iterate through the provided iterable and add them to the
        send queue. It shall exit when the state of this object is no longer "RUNNING" or when the iterable is exhausted

        Params:
            iterable (object): An object that can be passed to the iter() function

        Raises:
            RuntimeError: This method cannot be called more than once during the lifetime of this object, Runtime error
                raised if it is
        """

        if self._asyncThread: raise RuntimeError("Cannot call put_async multiple times. Async Thread running already")

        def place(iterable):
            iterobj = iter(iterable)
            task = next(iterobj)
            while self._state == self._RUNNING and not self._clearingTasks:
                try:
                    self.put(task, block=False)
                except mp.queues.Full:
                    continue

                try:
                    task = next(iterobj)
                except StopIteration:
                    break

        self._asyncThread = threading.Thread(target=place, args=(iterable,))
        self._asyncThread.start()

    def get(self, block: bool = True, timeout: float = None) -> object:
        """ Collect an output processed from a subprocess and return it. If block, wait for an output, or wait for the
        appropriate output if ordered has been set

        Params:
            block (bool): block running until an item is returned
            timeout (float): time to wait for a response

        Returns:
            object: The output of the pool function
        """
        try:
            self._active -= 1
            if self._ordered:
                if self._returnIndex in self._returnCache:
                    # Collect the item from the cache - previously returned and stored to be placed in order
                    value = self._returnCache[self._returnIndex]
                    del self._returnCache[self._returnIndex]
                    self._returnIndex += 1
                    return value
                else:
                    # Collect the result - collect a value from the queue
                    index, value = self._get(block, timeout)
                    if isinstance(value, Exception): raise SubprocessException(index, value)
                    if self._returnIndex == index:
                        # The returned item is the item to return
                        self._returnIndex += 1
                        return value
                    else:
                        # The returned item is yet to be asked for - store the item and attempt to get again
                        self._returnCache[index] = value
                        return self.get(block, timeout)

            # Collect the first response and return it
            index, value = self._get(block, timeout)
            if isinstance(value, Exception): raise SubprocessException(index, value)
            return value
        except Exception:
            self._active += 1
            raise

    def _get(self, block: bool, timeout: float) -> tuple:
        """ Get from the return queue a response. Ensure that the current program doesn't block for forseeable failures.

        Params:
            block (bool): Indicated whether the get method should block
            timeout (float): The time the process should wait to receive a response for

        Returns:
            tuple: The index of the work and the object generated by the user function

        Raises:
            mp.queues.Empty: if the method is called without blocking and there is nothing to collect from the queue
            RuntimeError: When the process was not able to collect anything due to their not being any processes running
            mp.TimeoutError: When the call exceeds the allowed specified time
        """

        if timeout is not None: start = time.time()
        while ((not self._returnQueue.empty() or self._pool.is_alive()) and
               (timeout is None or time.time() - start < timeout)):
            try:
                return self._returnQueue.get_nowait()
            except mp.queues.Empty:
                if not block: raise

        if not self._pool.is_alive(): raise RuntimeError("All processes in the pool have terminated - no work to get")
        else: raise mp.TimeoutError("Time limit will trying to receive completed work has been exceeded")

    def clearTasks(self) -> None:
        """ Clear the queue of tasks that have not yet been picked up by a pool processes """
        self._clearingTasks = True
        while not self._sendQueue.empty() or self._sendQueue.qsize():
            try:
                self._sendQueue.get_nowait()
                self._active -= 1
            except mp.queues.Empty:
                pass
        self._clearingTasks = False

    def connection(self) -> None:
        """ Return the connection items of the class, to be used by the subprocess handler """
        return ((self._logger_names, self._loggingPipe), self._sendQueue, self._returnQueue)

    def getall(self) -> [object]:
        """ Get all the items that have not already been returned, that were provided to be worked on

        Returns:
            [object]: A list of the returned outcomes still within the pool
        """
        while self._asyncThread and self._asyncThread.is_alive(): time.sleep(0.1)
        return [self.get() for _ in range(self._active)]

    def is_alive(self) -> int:
        return self._pool.is_alive()

    def close(self) -> None:
        """ Close down internal communication objects """
        if self._state == self._CLOSED: return
        self._state = self._CLOSED

        if self._loggingPipe:
            self._loggerThread.close()
            self._loggerThread.join()

        if self._asyncThread: self._asyncThread.join()

        for _ in range(self._pool_size): self._sendQueue.put(StopIteration())
        self._sendQueue.close()
        self._sendQueue.join_thread()

    def join_async(self) -> None:
        """ Wait for the async put thread if it is present, to join """
        if self._asyncThread: self._asyncThread.join()

    def join(self) -> None:
        """ wait for all the processes to conclude and then exit """
        self.close()
        self._pool.join()

    def terminate(self) -> None:
        """ Terminate all the running processes """
        self.close()
        self._pool.terminate()

class PoolManager:
    """ Generate and manage interactions with a pool of processes

    Params:
        function: The function the process within the pool will be enacting

    Keyword Params:
        processes (int) = os.cpu_count(): The number of processes within the pool
        static_args (list) = []: A list of arugments/parameters to be passed to the processes functions
        queue_size (int) = None: The maximun number of items that can be placed into the work stream
        logging (logging.Logger) = None: Provide a logger for the system
        ordered (bool) = False: Toggle ordering of the returned outputs
    """

    def __init__(self,
        function: callable,
        *,
        processes: int = os.cpu_count(),
        static_args: list = [],
        queue_size: int = None,
        logger: logging.Logger = None,
        ordered: bool = False,
        daemon: bool = True):

        self._pool_size = processes
        self._function = self._user_function_wrapper(function)
        self.daemon = daemon
        self.static_args = static_args
        self._queue_size = queue_size

        # Setup logging
        self._loggers = {}
        if logger: self.addLogger(logger)

        self._ordered = ordered
        self._processPool = []
        self._is_alive_check = 0

    def addLogger(self, logger: logging.Logger) -> None:
        """ Add a logger to the pool to such that the logs produced by sub-processes that would have been passed to this
        logger name, are communicated back to this logger in the main processes.

        Params:
            logger (logging.Logger): The logger object that the pool is to pass log messaged too.
        """
        if self._loggers is {}: self._loggers["PoolWorker"] = logging.getLogger("PoolWorker")
        self._loggers[logger.name] = logger

    def removeLogger(self, logger_name: (str, logging.Logger)) -> None:
        """ Remove a logger that has been added to the pool, this can either by done by the name of the logger or the
        logger object itself

        Params:
            logger_name (str/logging.Logger): The logging object or name to be removed from the pool
        """
        if isinstance(logger_name, logging.Logger): del self._loggers[logger_name.name]
        else: del self._loggers[logger_name]

    def map(self, iterable) -> [object]:
        """ Apply the function to the items in the iterable and return the result

        Params:
            iterable (iterable): Target of map function, function is mapped onto each item of iterable

        Returns:
            [object]: The list of object outputs produced from the function
        """
        orginal = self._ordered
        self._ordered = True
        with self as manager:
            self._ordered = orginal
            for i in iterable: manager.put(i)
            return manager.getall()

    def __enter__(self):

        self._manager = Communication(
            self,
            loggers = self._loggers,
            ordered = self._ordered,
            queue_size = self._queue_size
        )

        self._daemon = self.daemon

        for _ in range(self._pool_size):
            poolProcess = mp.Process(target=self._function, args=(*self._manager.connection(), self.static_args))
            poolProcess.daemon = self.daemon
            poolProcess.start()
            self._processPool.append(poolProcess)

        return self._manager

    @staticmethod
    def _user_function_wrapper(function):
        def pool_process(loggingPipe: mp.Pipe, sendQueue: mp.Queue, returnQueue: mp.Queue, static_args: list):

            logPipe = None
            if None not in loggingPipe: # The user wants to pass logging through back to the main process
                logging.getLogger().disabled = True
                logger_names, logPipe = loggingPipe

                pipeHandler = LogPipeHandler(logPipe)

                for name in logger_names:
                    logger = logging.getLogger(name)
                    logger.handlers = []
                    logger.propagate = False
                    logger.addHandler(pipeHandler)

            while True:
                try:
                    # Collect an input for the subprocess - check whether process signaled to end
                    sub_input = sendQueue.get(True)
                    if isinstance(sub_input, StopIteration): break

                    # Break out the input into index and value
                    input_index, input_value = sub_input

                    # Run function with value and static arguments
                    if isinstance(input_value, tuple): output = function(*input_value, *static_args)
                    else:                              output = function(input_value, *static_args)

                    # Return the result
                    returnQueue.put((input_index, output))
                except StopIteration:
                    break
                except MemoryError:
                    break
                except Exception as e:
                    returnQueue.put((input_index, e))

            if logPipe: logPipe[0].close()
        return pool_process

    def __exit__(self, a, b, c):
        self._manager.close()
        if self._daemon: self.terminate()  # All child daemons are to be destroyed

    def is_alive(self) -> int:
        """ Determine whether is pool is still alive. This is done by calling is alive on all the processes within the
        process pool. The value returned is the number of processes that are still alive, therefore when the pool is
        empty, the returned value can be equated to False

        Returns:
            int: The number of alive processes within the pool
        """
        if time.time() - self._is_alive_check < 5:
            self._is_alive_check = time.time()
            return len(self._processPool)

        curractedPool = []
        for process in self._processPool:
            if process.is_alive():
                curractedPool.append(process)

        self._processPool = curractedPool
        return len(self._processPool)

    def join(self):
        self._manager.close()
        while self.is_alive(): time.sleep(0.1)

    def terminate(self):
        for p in self._processPool: p.terminate()
        self._processPool = []