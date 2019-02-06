import os
import inspect
import time
import logging
import threading
import multiprocessing as mp

from ._exceptions import SubprocessException
from ._mplogging import LogPipeThread, LogPipeHandler

log = logging.getLogger("better.multiprocessing.PoolManager")

class PoolProcess:
    """ A class to act as the interface for the users to create process classes. This allows a user to define
    any environment variables during the running of the pool.
    """
    def run(self, *args, **kwargs):
        raise NotImplementedError("The run function for the PoolProcess has not been implemented")

class PoolManager:
    """ Generate and manage interactions with a pool of processes

    Params:
        function: The function the process within the pool will be enacting

    Keyword Params:
        processes (int) = os.cpu_count(): The number of processes within the pool
        static_args (list) = []: A list of arugments/parameters to be passed to the processes functions
        queue_size (int) = None: The maximum number of items that can be placed into the work stream
        logging (logging.Logger) = None: Provide a logger for the system
        ordered (bool) = False: Toggle ordering of the returned outputs
    """

    _STANDBY = 10
    _RUNNING = 20
    _CLOSED = 30

    def __init__(self,
        target: callable,
        *,
        size: int = os.cpu_count(),
        static_args: list = [],
        queue_size: int = "auto",
        logger: logging.Logger = None,
        ordered: bool = False,
        daemon: bool = False
        ):

        self._state = self._STANDBY
        self._pool_size = size
        self._ordered = ordered
        self._returnIndex = 0
        self._returnCache = {}
        self.daemon = daemon
        self.static_args = static_args

        # Setup the send and receive queues, and determine the queue size
        if isinstance(queue_size, str):
            if queue_size == "auto": size = self._pool_size*2
            else: raise ValueError("Invalid value of queue size provided. ('auto', int)")
        else:
            size = queue_size

        self._sendQueue = mp.Queue(size)
        self._returnQueue = mp.Queue()

        # Wrap the user function
        self._function = self._user_function_wrapper(target)

        # Setup logging
        self._loggingPipe = None
        self._loggerThread = None
        self._loggers = {}
        if logger:
            try:
                if isinstance(logger, logging.Logger):  # Single logger object provided, add the logger
                    self.addLogger(logger)
                else:
                    loggerIter = iter(logger)  # iterable provided, iterate through loggers and add each one.
                    while True:
                        try:
                            self.addLogger(next(loggerIter))
                        except StopIteration:
                            break
            except:
                raise TypeError("Invalid type for argument logger: Takes Logger object or iterable yielding Loggers")

        self._processPool = []
        self._index = 0
        self._active = 0
        self._asyncThread = None
        self._clearingTasks = False
        self._is_alive_check = 0

    def addLogger(self, logger: logging.Logger) -> None:
        """ Add a logger to the pool to such that the logs produced by sub-processes that would have been passed to this
        logger name, are communicated back to this logger in the main processes.

        Params:
            logger (logging.Logger): The logger object that the pool is to pass log messaged too.

        Raises:
            RuntimeError: In the event that the Pool has already been started.
            TypeError: The object provided isn't a logger object
        """

        # Address usage errors
        if self._state != self._STANDBY:
            raise RuntimeError("Cannot add logger into child processes after the pool has been started")
        if not isinstance(logger, logging.Logger):
            raise TypeError("Invalid type of 'logger' argument passed")

        # In the event of a logger being used, add in a capture method for the pool's processes themselves
        if self._loggers is {}:
            processLoggerName = "better.multiprocessing.PoolManager.PoolProcess"
            self._loggers[processLoggerName] = logging.getLogger(processLoggerName)

        # Add the logger into the fold
        self._loggers[logger.name] = logger

    def removeLogger(self, logger_name: (str, logging.Logger)) -> None:
        """ Remove a logger that has been added to the pool, this can either by done by the name of the logger or the
        logger object itself

        Params:
            logger_name (str/logging.Logger): The logging object or name to be removed from the pool
        """
        if isinstance(logger_name, logging.Logger): del self._loggers[logger_name.name]
        else: del self._loggers[logger_name]

    def _put(self, item: (int, object), block: bool = True, timeout: float = None) -> None:
        """ Place an item into the sendQueue in a safe manner and ensure that the process shall not block forever
        waiting for work to be dequeued if their are no more children left to check it

        Params:
            item (int, object): An item to be sent to the pool of processes
            block (bool): while putting the item, if True, block until space is available else through error
            timeout (float): The length of time to block for given that the block is True

        Raises:
            RuntimeError: If all the processes in the pool have died and this method is called to place a piece of work
            mp.TimeoutError: A block timeout and an item could not be placed
        """

        if timeout is not None: start = time.time()
        while (self.isAlive() and (timeout is None or time.time() - start < timeout)):
            try:
                return self._sendQueue.put(item, block=False)
            except mp.queues.Full:
                if not block: raise

        if not self.isAlive(): raise RuntimeError("Empty pool")
        else: mp.TimeoutError("Timeout while attempting to place item: {}".format(item))

    def put(self, *items, block: bool = True, timeout: float = None) -> None:
        """ Place an item in the work stream, this will hold the inputs for the subprocesses. The method will block if
        the queue is full

        Params:
            item (object): The item to be passed to the subprocesses
            block (bool) = True: The placing attitude
            timeout (float) = None: A timeout for trying to place item
        """
        if items: items = tuple(items)
        else: raise TypeError("put method must take at least one argument")

        self._put((self._index, items), block=block, timeout=timeout)
        self._active += 1
        self._index += 1

    def putAsync(self, iterable: object):
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

            iterObj = iter(iterable)
            while self._state == self._RUNNING and not self._clearingTasks:
                try:
                    self.put(next(iterObj))
                except StopIteration:
                    log.debug("putThread: Concluded as iterable exhausted")
                    return

            log.debug("putThread: Externally closed - State: {}, emptying: {}".format(self._state, self._clearingTasks))

        self._asyncThread = threading.Thread(target=place, args=(iterable,))
        self._asyncThread.start()

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

        log.info("_get: attempting to get from return queue expected size {}".format(self._active))

        if timeout is not None: start = time.time()
        while ((self._active and self.isAlive()) and
               (timeout is None or time.time() - start < timeout)):
            try:
                index, value = self._returnQueue.get(False)
                self._active -= 1
                if isinstance(value, Exception): raise SubprocessException(index, value)
                return index, value
            except mp.queues.Empty:
                if not block: raise

        if not self._active: raise ValueError("Could not call get on items as there are no items to collect")
        elif not self.isAlive(): raise RuntimeError("All processes in the pool have terminated - no work to get")
        else: raise mp.TimeoutError("Time limit will trying to receive completed work has been exceeded")

    def get(self, block: bool = True, timeout: float = None) -> object:
        """ Collect an output processed from a subprocess and return it. If block, wait for an output, or wait for the
        appropriate output if ordered has been set

        Params:
            block (bool): block running until an item is returned
            timeout (float): time to wait for a response

        Returns:
            object: The output of the pool function
        """

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
                if self._returnIndex == index:
                    # The returned item is the item to return
                    self._returnIndex += 1
                    return value
                else:
                    # The returned item is yet to be asked for - store the item and attempt to get again
                    self._returnCache[index] = value
                    return self.get(block, timeout)  # Recursively attempt to collect item

        else:
            # Collect the first response and return it
            _, value = self._get(block, timeout)
            return value

    def getAll(self) -> [object]:
        """ Get all the items that have not already been returned, that were provided to be worked on

        Returns:
            [object]: A list of the returned outcomes still within the pool
        """
        while self._asyncThread and self._asyncThread.isAlive(): time.sleep(0.1)
        return [self.get() for _ in range(self._active)]

    def map(self, iterable) -> [object]:
        """ Apply the function to the items in the iterable and return the result

        Params:
            iterable (iterable): Target of map function, function is mapped onto each item of iterable

        Returns:
            [object]: The list of object outputs produced from the function
        """
        original = self._ordered
        self._ordered = True
        with self as manager:
            for i in iterable: manager.put(i)
            result = manager.getAll()
        self._ordered = original
        return result

    def start(self):
        """ Start the pool of processes """

        self._state = self._RUNNING

        # Set up the logging thread and handling
        if self._loggers:
            self._loggingPipe = mp.Pipe()
            self._loggerThread = LogPipeThread(self._loggingPipe, self._loggers)
            self._loggerThread.start()

        self._daemon = self.daemon

        for _ in range(self._pool_size):
            poolProcess = mp.Process(
                target=self._function,
                args=(
                    (self._loggers.keys(), self._loggingPipe),
                    self._sendQueue,
                    self._returnQueue,
                    self.static_args
                )
            )
            poolProcess.daemon = self.daemon
            poolProcess.start()
            self._processPool.append(poolProcess)

    def isAlive(self) -> int:
        """ Determine whether is pool is still alive. This is done by calling is alive on all the processes within the
        process pool. The value returned is the number of processes that are still alive, therefore when the pool is
        empty, the returned value can be equated to False

        Returns:
            int: The number of alive processes within the pool
        """
        if time.time() - self._is_alive_check < 5:
            return len(self._processPool) > 0

        self._is_alive_check = time.time()

        curractedPool = []
        for process in self._processPool:
            if process.is_alive():
                curractedPool.append(process)

        self._processPool = curractedPool
        return len(self._processPool) > 0

    def joinAsync(self) -> None:
        """ Wait for the async put thread if it is present, to join """
        if self._asyncThread:
            self._asyncThread.join()
            self._asyncThread = None

    def join(self):
        self.close()
        while self.isAlive(): time.sleep(0.1)

    def clearTasks(self) -> None:
        """ Clear the queue of tasks that have not yet been picked up by a pool processes """
        self._clearingTasks = True
        while not self._sendQueue.empty() or self._sendQueue.qsize():
            try:
                self._sendQueue.get(False)
                self._active -= 1
            except mp.queues.Empty:
                pass
        self._clearingTasks = False

    def close(self):
        if self._state == self._CLOSED: return
        self._state = self._CLOSED

        if self._loggingPipe:
            self._loggerThread.close()
            self._loggerThread.join()

        if self._asyncThread: self.joinAsync()


        try:
            for _ in range(self._pool_size): self._sendQueue.put(StopIteration(), False, 1)
            self._sendQueue.close()
            self._sendQueue.join_thread()
        except:
            pass

    def terminate(self):
        self.close()
        for p in self._processPool: p.terminate()
        self._processPool = []

    def __enter__(self):
        self.start()
        return self

    @staticmethod
    def _user_function_wrapper(user_worker):
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

            if inspect.isclass(user_worker) and issubclass(user_worker, PoolProcess):
                worker = user_worker(*static_args)
                function = worker.run
                static_args = []  # Static arguments are emptied as it is not to be passed to the run function
            else:
                function = user_worker

            while True:
                try:
                    # Collect an input for the subprocess - check whether process has been signalled to end
                    sub_input = sendQueue.get(True)
                    if isinstance(sub_input, StopIteration): break

                    # Break out the input into index and value
                    input_index, input_value = sub_input

                    # Run function with value and static arguments
                    output = function(*input_value, *static_args)

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
        self.close()
        if self._daemon: self.terminate()  # All child daemons are to be destroyed