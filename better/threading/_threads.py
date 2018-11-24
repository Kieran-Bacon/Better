import queue
import threading

class Feeder(threading.Thread):

    def __init__(self, iterable, function, completeQueue: queue.Queue, *, thread_count: int = 100, daemon = None):
        threading.Thread.__init__(self, group = None, daemon = daemon)

        self.iterable = iterable
        self.function = function

        self.workQueue = queue.Queue()
        self.completeQueue = completeQueue

        self.thread_count = thread_count

        self.working = True

    def run(self):

        active_threads = 0
        thread_pool = []

        def worker(workQueue, completeQueue):
            # Shared working bool indicates works should stay alive
            while self.working:
                try:
                    index, item = workQueue.get_nowait()
                    completeQueue.put((index, self.function(item)))
                    workQueue.task_done()
                except queue.Empty:
                    pass

        for index, item in enumerate(self.iterable):
            # Expand thread pool iteratively until it has reached capacity to avoid unnecessary threads
            if active_threads < self.thread_count:
                thread = threading.Thread(target=worker, args=(self.workQueue, self.completeQueue,))
                thread.start()
                thread_pool.append(thread)
                active_threads += 1

            # Send work to the threads
            self.workQueue.put((index, item))

        self.workQueue.join()

        self.working = False
        for t in thread_pool: t.join()