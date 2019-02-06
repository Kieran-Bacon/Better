# Getting started with the PoolManager

The pool manager is meant to provide a single interface for interacting with sub-processes and does so by exposing various interfaces common to a few multiprocessing objects. The three most notable  structures that it exhibits are the `Pool`, `Process` and the `Queue` objects.

How one can initialise a `PoolManager` and you can then interact with the function that you've provided in a similar manner to how you would interact with a function:

```python
import better.multiprocessing as bmp

worker = lambda x: x**2

with bmp.PoolManager(worker) as pool:
    for i in range(10):
        pool.put(i)

pool = bmp.PoolManager(worker)
pool.start()

for i in range(10):
    pool.put(i)

pool.close()
```

For functions with multiple arguments, multiple arguments can be passed to the pool or even the functions signatures themselves.

```python
def multiply(a, b):
    return a * b

with bmp.PoolManager(multiply) as pool:
    bmp.put(10, 20)
    bmp.put((14,25))
```

## Working with static variables

For the instances where each task requires some variable that is static or final, the `static_args` parameter is used to pass these values and have them stored in the sub-process as to avoid sending them with each task.

In the event that the user provides the `PoolManager`'s target with a `PoolProcess`, the static arguments are passed to the init of the process instead of being passed into the run function. If you would like to access these values within the run function (while processing a task) the values should be stored against the instance.

```python
# User function handling static arguments
def worker(task, static):
    return task*stored

with bmp.PoolManager(worker, static_args=[10]) as pool:
    pool.put(10)

# User class handling static arguments
class Worker(PoolProcess):
    def __init__(self, static):
        self.value = static

    def run(self, task):
        return task*self.value

class Worker(PoolProcess):
with bmp.PoolManager(worker, static_args=[10]) as pool:
    pool.put(10)
```

## Logging within the Pool

The `PoolManager` allows the main process to handle logging that occurs within the sub-processes by capturing the logs from the selected loggers, and sending it back to the main process using a pipe. A thread is initialised to monitor and handle logging information from the sub-processes such that there is not blocking behaviour when handling logs.

To avoid having to call to `logging.getLogger()` one can set up the logger within the init of a `PoolProcess` such that the logger can then be accessed quickly.

Loggers that are defined in the global space can still be accessed, and they shall have the same conventional behaviour as before. Only specified loggers shall be intercepted and be altered to communicate their records back to the main processes.

```python
# The PoolProcess implementation of logging
class LogWorker(PoolProcess):

    def __init__(self):
        self.log = logging.getLogger("test")

    def run(self, task):
        self.log.info("This is going to be logged, and sent to the main process")
        return task*2  # do work

with PoolManager(LogWorker, logger=logging.getLogger("test")) as pool:
    pool.put(10)


# Getting a logger within a process function
def worker(task):
    log = logging.getLogger("test")
    log.info("This is going to be logged")
    return task*2

with PoolManager(LogWorker, logger=logging.getLogger("test")) as pool:
    pool.put(10)
```

## Reference Manual

### PoolManager(target, *, size, static_args, queue_size, ordered, logger, daemon)

`target` can be only either a class that extends `PoolProcess` or a method that is to be treated as the main function of the pool's processes.

```python
def sqrt(x):
    return x ** 0.5

PoolManager(sqrt).map([20,10,5,2])
PoolManager(lambda x: x**2).map([1,2,3,4,5,6,7])

with PoolManager(lambda x: x**2) as pool:
    for x in range(10): pool.put(x)
    result = pool.getAll()

# PoolProcess example
class Worker(PoolProcess):
    def run(self, x):
        return x**0.5

PoolManager(Worker).map([20,10,5,2])
```

`size` is the number of processes that are to be created within the pool. It's default value is given by `os.cpu_count()`

```python
PoolManager(lambda x: time.sleep(x), size = 4).map(range(100))
PoolManager(lambda x: time.sleep(x), size = 100).map(range(100))
```

`static_args` are arguments that are to accompany the dynamically passed items of work. They are unpacked and added to the items passed into the PoolManager queue when the user function is called.

```python
def multiply(x, y):
    return x * y

PoolManager(multiply, static_args=[10]).map([1,2,3,4])

with PoolManager(multiply, static_args=[10]) as pool:
    for x in range(1,5): pool.put(x)
    result = pool.getAll()
```

`queue_size` works like `mp.Queue(queue_size)` restricts the amount of work that can exist in the queue waiting to be worked on by a process. This is to help ensure that the main process doesn't waste memory unnecessarily and that the queue itself doesn't get filled up to potentially break. The default value for this twice the number of processes within the pool. See `Communication` above.

`ordered` is a boolean with a default of `False`. It indicates whether the returned outputs should be in order of their placement or whether they can be in the order they work completed.

`logger` is to take a `logging.Logger` object. The logger is to be used to capture all the logging output within the sub-processes that would have logged through a logger with the same name. This allows the main-thread to govern how the logging of a multiprocessing system shall work.

`daemon` is a boolean value with a default of `True`. It indicates whether the pool's processes should be daemonized on creation.

### addLogger(logger: logging.Logger) -> None

Adds the `logger` object to this Pool. This indicates to the Pool that logs made to this logger within the sub-process should be passed back to the main processes and handled by this logger specifically.

This function cannot be called when the pool has already been started, as the sub-processes have already been initialised to handle the loggers previously specified. This shall cause this function to raise a `RuntimeError`.

This function shall raise a `TypeError` in the event that the object passed isn't a `logging.Logger` object.

### removeLogger(logger: str/logging.Logger) -> None

Remove a `logger` object from this Pool instance. This function can either take the logger object itself, or it's name.

This function shall raise a `KeyError` in the event that this pool doesn't have a logger corresponding the the arguments provided.

```python
pool = PoolManager(worker)
pool.addLogger(logging.getLogger("test"))
pool.removeLogger("test")
pool.start()
# ...
```

### put(items: object, block: bool = True, timeout: float = None) -> None

When the pool has been started and the Pool's processes are alive, Put passes the `items` through to the process to be worked on. Items put into the pool are passed through to the user defined function to be processed.

If the `queue_size` parameter was set in the init of the PoolManager, the put command shall only be able to place queue_size lots of items before it either blocks or throws a `mp.Queues.Full` exception.

If `block` is False, the method shall not wait to place an item into the task queue and as a result, in the event that the queue is full this function shall throw a `mp.queues.Full` exception.

If `block` is True, this method shall wait in the event that the queue is full until there is space. It shall wait forever or until the time specified by `timeout`.

### putAsync(iterable: object) -> None

Send tasks to the pool's processes without blocking the main process, and when the send queue is available to have items sent.

This method starts a feeder thread that shall continue until the pool is closed. This method can only be called once.

### get(block: bool = True, timeout: float = None) -> object

Collect from the pool of processes the output of processing an item that has been passed into the Pool. If the PoolManager parameter `ordered` has been set, the nth call to get shall attempt to collect the return value for the nth item placed into the pool.

In the event that this function is called when there hasn't been a corresponding item placed into the pool to generate a return value, a `ValueError` is raised.

In the event that the sub-processes have already concluded (safely or not) such that there are no more processes to produce a return value, a `RuntimeError` is raised.

By default, this function shall block until it has something to get, however, this behaviour can be altered by the keyword argument `block`. When set to false, the method shall return instantly and raise an `mp.queues.Empty` if there was nothing to collect. Alternatively, one can set a timeout, that shall only block for the specified time.

> NOTE: When attempting to collect the outputs of tasks in an ordered environment, results that have been returned before they are required are stored to be returned later. The method then recursively calls itself until it collects the right output value to return. One should consider the impact of having a long running first task, it is potentially possible to hit the recursion depth limit, or to hold memory for outputs that have not yet become available

### map(iterable) -> [object]

Apply the map function using the pool, this shall apply the pools function to each of the items in the iterable and return an list of the returned values in the order the processes completed the work.

### start() -> None

Start the processes with the user's target. Populate the pool with processes and set up all the communication structures.

### isAlive() -> bool

Determine whether there are processes alive within the pool. This method calls `is_alive()` on each of the pool processes and returns True if any are alive. This shall remove concluded processes from the pool. The answer for this function shall be cached for any subsequent calls within the next 5 seconds.

### joinAsync() -> None

This method blocks until the joinAsync thread has concluded (when it has finished placing its tasks into the send queue).

### join() -> None

This method closes the pool and blocks until the sub-processes have concluded.

### clearTasks() -> None

Empties out the feeding task queue, this stops sub-processes from working on tasks put into the feed before this method has been called.

### close() -> None

Close the pool, signal the processes to stop working and to end any communication threads such as logging and the putAsync threads.

### terminate() -> None

Call terminate on all sub-processes within the pool and stop computation immediately. This shall close all open connections and empty the pool.