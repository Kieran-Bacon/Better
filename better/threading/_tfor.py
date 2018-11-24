import os
import uuid
import time
import threading
import queue

from ._threads import Feeder

def tfor(function, iterable, *, thread_count: int = os.cpu_count(), ordered: bool = False, yields: bool = False):

    # A collection of the results of applying the function to the iterable items.
    completeQueue = queue.Queue()

    # Start the feeder thread and begin working on content
    feeder_thread = Feeder(iterable, function, completeQueue, thread_count=thread_count)
    feeder_thread.start()

    def _tforGenerator(completeQueue, ordered):
        """ Creates a generator that will yield values from the completeQueue when they are generated, allowing for 
        working on results while others are being produced 
        
        Params:
            completeQueue (queue.Queue): The collection the items are to be returned too
            ordered (bool): Toggle to ensure that the result is ordered or not
        """
        index, returning = 0, []
        while feeder_thread.is_alive() or not completeQueue.empty():
            # Continue until the workers have all finished, and all the completed tasks have been collected
            try:
                jobindex, output = completeQueue.get_nowait()
                if len(returning) - 1 < jobindex:
                    for _ in range(jobindex - (len(returning) - 1)): returning.append(None)

                # The method is to yield responses
                if ordered:
                    # Check whether the recently returned item is to be yielded out of the gate
                    if jobindex == index:
                        yield output
                        index += 1
                    else:
                        # Save the item and check whether the correct item has been returned previously
                        returning[jobindex] = output

                        while returning[index] is not None:
                            yield returning[index]
                            returning[index] = None
                            index += 1
                    continue
                else:
                    yield output
                    continue

                completeQueue.task_done()
            except queue.Empty: pass
    if yields: return _tforGenerator(completeQueue, ordered)

    # The main thread generating the out put and returning
    returning = []
    while feeder_thread.is_alive() or not completeQueue.empty():
        try:
            jobindex, output = completeQueue.get_nowait()
            returning.append((jobindex, output))
            completeQueue.task_done()
        except queue.Empty: pass

    # Return and order if toggled
    return [v[1] for v in sorted(returning, key=lambda x: x[0])] if ordered else [v[1] for v in returning]

def dtfor(**kwargs):
    def wrap(function):
        def method(iterable):
            return tfor(function, iterable, **kwargs)
        return method
    return wrap