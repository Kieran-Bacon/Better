import multiprocessing as mp

class Queue(mp.queues.Queue):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, ctx=mp.get_context())
        self._lock = mp.Lock()
        self._acquired = False
        self._size = mp.Value('i', 0, lock = False)

    def __enter__(self):
        print("Acquiring the fucking lock?")
        self._acquired = True
        self._lock.acquire()

    def __exit__(self, *args):
        self._lock.release()
        self._acquired = False
        print("losing the fucking lock")
        print(self._size.value)

    def put(self, *args, **kwargs):

        super().put(*args, **kwargs)


        print("Put called")

        if self._acquired:
            self._size.value += 1
        else:
            with self._lock:
                self._size.value += 1

        super().put(*args, **kwargs)

    def get(self, *args, **kwargs):

        #print("Getting Value from Queue of size {}".format(self._size.value))
        if self._acquired:
            self._size.value -= 1
        else:
            with self._lock:
                self._size.value -= 1

        try:
            return super().get(*args, **kwargs)
        except mp.queues.Empty:
            self._size.value = 0
            raise


    def qsize(self):
        """ Reliable implementation of multiprocessing.Queue.qsize() """
        return self._size.value

    def empty(self):
        """ Reliable implementation of multiprocessing.Queue.empty() """
        return not self.qsize()


    def _locker(self, f):

        def wrapper(*args, **kwargs):

            if self._acquired:
                return f(*args, **kwargs)

            else:
                self._lock.acquire()
                returnValue = f(*args, **kwargs)
                self._lock.release()

# import multiprocessing as mp

# class Queue(mp.queues.Queue):

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs, ctx=mp.get_context())
#         self._lock = mp.Lock()
#         self._acquired = False
#         self._size = mp.Value('i', 0, lock = False)

#     def __enter__(self):
#         print("Acquiring the fucking lock?")
#         self._acquired = True
#         self._lock.acquire()

#     def __exit__(self, *args):
#         self._lock.release()
#         self._acquired = False
#         print("losing the fucking lock")
#         print(self._size.value)

#     def put(self, *args, **kwargs):
#         print("Put called")

#         if self._acquired:
#             self._size.value += 1
#         else:
#             with self._lock:
#                 self._size.value += 1

#         super().put(*args, **kwargs)

#     def get(self, *args, **kwargs):

#         #print("Getting Value from Queue of size {}".format(self._size.value))
#         if self._acquired:
#             self._size.value -= 1
#         else:
#             with self._lock:
#                 self._size.value -= 1

#         try:
#             return super().get(*args, **kwargs)
#         except mp.queues.Empty:
#             self._size.value = 0
#             raise


#     def qsize(self):
#         """ Reliable implementation of multiprocessing.Queue.qsize() """
#         return self._size.value

#     def empty(self):
#         """ Reliable implementation of multiprocessing.Queue.empty() """
#         return not self.qsize()


#     def _locker(self, f):

#         def wrapper(*args, **kwargs):

#             if self._acquired:
#                 return f(*args, **kwargs)

#             else:
#                 self._lock.acquire()
#                 returnValue = f(*args, **kwargs)
#                 self._lock.release()