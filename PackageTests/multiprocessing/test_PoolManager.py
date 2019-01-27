import unittest
import pytest

import sys
import time
import logging

from better.multiprocessing import PoolManager, SubprocessException

logging.basicConfig(level=logging.DEBUG)

class Test_PoolManager(unittest.TestCase):

    class TestLogger(logging.Logger):

        def handle(self, record):
            if not hasattr(self, "_returned"): self._returned = []
            self._returned.append(record.msg)

    def test_general_behaviour(self):

        with PoolManager(lambda x: x*2) as conn:
            for i in range(100): conn.put(i)
            a = conn.getAll()

        self.assertEqual(set(a), {x*2 for x in range(100)})

    def test_static_arguments(self):

        inputs = range(100)

        def method(value, number):
            return value * number

        with PoolManager(method, static_args=[10]) as manager:
            for i in inputs: manager.put(i)
            a = manager.getAll()

        self.assertEqual(set(a), {x*10 for x in inputs})

    def test_pool_map(self):
        inputs = range(40)
        self.assertEqual(PoolManager(lambda x: x + 10, ordered = True).map(inputs), [x+10 for x in inputs])

    def test_pool_map_without_setting_order(self):
        inputs = range(40)
        self.assertEqual(PoolManager(lambda x: x + 10).map(inputs), [x+10 for x in inputs])

    def test_async_map(self):
        with PoolManager(lambda x: x*2) as pool:
            pool.putAsync(range(40))
            self.assertEqual(set(pool.getAll()), {x*2 for x in range(40)})

    def test_map_fails(self):

        with pytest.raises(ZeroDivisionError):
            with PoolManager(lambda x : x/0) as pool:
                for i in range(10): pool.put(i)
                try:
                    pool.getAll()
                except SubprocessException as e:
                    raise e.raised

    def test_pool_logging(self):

        def sub_process(pid):
            log = logging.getLogger("Subprocess")
            log.info("{}".format(pid))

        log = self.TestLogger("Subprocess", level=logging.INFO)

        with PoolManager(sub_process, logger=log) as conn:
            for i in range(8): conn.put(i)
            conn.getAll()

        self.assertEqual(set(log._returned), {str(x) for x in range(8)})

    def test_pool_logging_hierarchy(self):

        #logging.getLogger().propagate = True

        def sub_processes(pid):
            log = logging.getLogger("test.submodule")
            log.info("{}".format(pid))

        sub = self.TestLogger("test.submodule", level=logging.INFO)
        testlog = self.TestLogger("test", level=logging.INFO)
        notloggedlog = self.TestLogger("information", level=logging.INFO)

        with PoolManager(sub_processes) as pool:

            pool.addLogger(sub)
            pool.addLogger(testlog)
            pool.addLogger(notloggedlog)

            for i in range(8): pool.put(i)
            pool.getAll()

        self.assertEqual(set(testlog._returned), {str(x) for x in range(8)})
        self.assertFalse(hasattr(notloggedlog, "_returned"))

    def test_getall_doesnt_poll_into_oblivion(self):

        def seppuku(*args):
            time.sleep(5)
            sys.exit()

        with PoolManager(seppuku) as conn:
            conn.putAsync([None]*10)

            with pytest.raises(RuntimeError):
                conn.getAll()

    def test_clearTasks_correctly_dequeues(self):

        def do_some_work(value):
            time.sleep(2)
            return value * 2

        with PoolManager(do_some_work, size=4) as conn:
            for i in range(10): conn.put(i)

            conn.clearTasks()

            self.assertEqual(set(conn.getAll()), {0, 2, 4, 6})