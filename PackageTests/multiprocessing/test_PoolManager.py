import unittest
import pytest

import sys
import time
import logging

from better.multiprocessing import PoolManager, SubprocessException

logging.basicConfig(level=logging.DEBUG)

class Test_PoolManager(unittest.TestCase):

    def test_general_behaviour(self):

        with PoolManager(lambda x: x*2) as conn:
            for i in range(100): conn.put(i)
            a = conn.getall()

        self.assertEqual(set(a), {x*2 for x in range(100)})

    def test_static_arguments(self):

        inputs = range(100)

        def method(value, number):
            return value * number

        with PoolManager(method, static_args=[10]) as manager:
            for i in inputs: manager.put(i)
            a = manager.getall()

        self.assertEqual(set(a), {x*10 for x in inputs})

    def test_pool_map(self):
        inputs = range(40)
        self.assertEqual(PoolManager(lambda x: x + 10, ordered = True).map(inputs), [x+10 for x in inputs])

    def test_pool_map_without_setting_order(self):
        inputs = range(40)
        self.assertEqual(PoolManager(lambda x: x + 10).map(inputs), [x+10 for x in inputs])

    def test_async_map(self):
        with PoolManager(lambda x: x*2) as pool:
            pool.put_async(range(40))
            self.assertEqual(set(pool.getall()), {x*2 for x in range(40)})

    def test_map_fails(self):

        with pytest.raises(ZeroDivisionError):
            with PoolManager(lambda x : x/0) as pool:
                for i in range(10): pool.put(i)
                try:
                    pool.getall()
                except SubprocessException as e:
                    raise e.raised

    def test_pool_logging(self):

        def sub_process(pid):
            log = logging.getLogger("Subprocess")
            log.info("{}".format(pid))

        class TestLogger(logging.Logger):

            def handle(self, record):
                if not hasattr(self, "_returned"): self._returned = []
                self._returned.append(record.msg)


        log = TestLogger("Subprocess", level=logging.INFO)

        with PoolManager(sub_process, logger=log) as conn:
            for i in range(8): conn.put(i)
            conn.getall()

        self.assertEqual(set(log._returned), {str(x) for x in range(8)})

    def test_getall_doesnt_poll_into_oblivion(self):

        def seppuku(*args):
            time.sleep(5)
            sys.exit()

        with PoolManager(seppuku) as conn:
            conn.put_async([None]*10)

            with pytest.raises(RuntimeError):
                conn.getall()

    def test_clearTasks_correctly_dequeues(self):

        def do_some_work(value):
            time.sleep(2)
            return value * 2

        with PoolManager(do_some_work, processes=4) as conn:
            for i in range(10): conn.put(i)

            conn.clearTasks()

            self.assertEqual(set(conn.getall()), {0, 2, 4, 6})