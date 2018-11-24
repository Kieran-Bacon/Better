import os
import logging
import threading
import multiprocessing as mp

class Communication:
    """ An object to handle communication with the pool manager 
    
    Params:
        processes (int): The number of processes the pool is maintaining

    Unordered Params:
        logging (bool): Toggle to implement logging between children and main process
        ordered (bool): Toggle the output to be ordered
        queue_size (int): The total number of items that can be placed into the work stream
    """

    def __init__(self, processes: int, *, logging: bool = False, ordered: bool = False, queue_size: int = None):

        self.active = 0  # The number of current work that is active
        self.processes = processes  # The maximun number of processes
        self._logging = logging  # A bool to toggle whether logging is active or not
        self._ordered = ordered  # A bool to toggle whether the output are to be ordered or simply returned
        if self._ordered:
            self._returnIndex = 0
            self._returnCache = {}

        if isinstance(queue_size, bool) and queue_size is False: size = None
        else: size = queue_size if queue_size is not None else self.processes*2
        
        self.loggingPipe = mp.Pipe()
        self.sendQueue = mp.Queue(size)
        self.returnQueue = mp.Queue()

        self._index = 0

    def put(self, item, block: bool = True, timeout: float = None) -> None:
        """ Place an item in the work stream, this will hold the inputs for the subprocesses. The method will block if
        the queue is full

        Params:
            item (object): The item to be passed to the subprocesses
            block (bool) = True: The placing attitude
            timeout (float) = None: A timeout for trying to place item 
        """
        self.sendQueue.put((self._index, item), block=block, timeout=timeout)
        self.active += 1
        self._index += 1

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
            self.active -= 1
            if self._ordered:
                if self._returnIndex in self._returnCache:
                    # Collect the item from the cache - previously returned and stored to be placed in order
                    value = self._returnCache[self._returnIndex]
                    del self._returnCache[self._returnIndex]
                    self._returnIndex += 1
                    return value
                else:
                    # Collect the result - collect a value from the queue
                    index, value = self.returnQueue.get(block, timeout)
                    if self._returnIndex == index:
                        # The returned item is the item to return
                        self._returnIndex += 1
                        return value
                    else:
                        # The returned item is yet to be asked for - store the item and attempt to get again
                        self._returnCache[index] = value
                        return self.get(block, timeout)

            # Collect the first response and return it
            _, value = self.returnQueue.get(block, timeout)
            return value
        except Exception:
            self.active += 1
            raise

    def connection(self) -> None:
        """ Return the connection items of the class, to be used by the subprocess handler """
        return (self.loggingPipe, self.sendQueue, self.returnQueue)

    def getall(self) -> [object]:
        """ Get all the items that have not already been returned, that were provided to be worked on 
        
        Returns:
            [object]: A list of the returned outcomes still within the pool
        """
        return [self.get() for _ in range(self.active)]

    def close(self) -> None:
        """ Close down internal communication objects """
        pass

class PoolManager:
    """ Generate and manage interactions with a pool of processes

    Params:
        function: The function the process within the pool will be enacting

    Keyword Params:
        processes (int) = os.cpu_count(): The number of processes within the pool
        static_args (list) = []: A list of arugments/parameters to be passed to the processes functions
        queue_size (int) = None: The maximun number of items that can be placed into the work stream
        logging (bool) = False: Toggle logging within the sub processes
        ordered (bool) = False: Toggle ordering of the returned outputs
    """ 

    def __init__(self,
        function: callable,
        *,
        processes: int = os.cpu_count(),
        static_args: list = [],
        queue_size: int = None,
        logging: bool = False,
        ordered: bool = False):
        
        self.processes = processes
        self.function = self._user_function_wrapper(function)
        self.static_args = static_args
        self._queue_size = queue_size
        self._logging = logging
        self._ordered = ordered

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

        self.manager = Communication(
            self.processes,
            logging = self._logging,
            ordered = self._ordered,
            queue_size = self._queue_size
        )
        self._pool = mp.Pool(self.processes, self.function, (*self.manager.connection(), self.static_args))

        if self._logging: raise NotImplementedError()

        return self.manager

    @staticmethod
    def loggingThread(logger, pipe, signal):
        """ Handle messages from a pipe into a logger """
        pass

    @staticmethod
    def _user_function_wrapper(function):
        def pool_process(loggingPipe: mp.Pipe, sendQueue: mp.Queue, returnQueue: mp.Queue, static_args: list):

            while True:
                try:
                    # Collect an input for the subprocess - check whether process signaled to end
                    sub_input = sendQueue.get(True)
                    if isinstance(sub_input, StopIteration): break

                    # Break out the input into index and value
                    input_index, input_value = sub_input

                    # Run function with value and static arguments
                    output = function(input_value, *static_args)

                    # Return the result
                    returnQueue.put((input_index, output))
                except StopIteration:
                    break

        return pool_process

    def __exit__(self, a, b, c):

        self._pool.close()
        self._pool.terminate()
        self._pool.join()
        self.manager.close()