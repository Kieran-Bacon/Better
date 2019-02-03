import pytest, unittest

import logging
import time

from better.multiprocessing import PoolProcess, PoolManager

class Test_PoolManager_logging(unittest.TestCase):

    class TestLogger(logging.Logger):

        def handle(self, record):
            if not hasattr(self, "_returned"): self._returned = []
            self._returned.append(record.msg)

    class TestHandler(logging.Handler):

        def __init__(self):
            logging.Handler.__init__(self)

        def emit(self, record):
            if not hasattr(self, "_returned"): self._returned = []
            self._returned.append(record.msg)

    def test_logging_basic(self):

        def sub_process(pid):
            log = logging.getLogger("Subprocess")
            log.setLevel(logging.DEBUG)
            log.info("{}".format(pid))

        log = self.TestLogger("Subprocess", level=logging.INFO)

        with PoolManager(sub_process, logger=log) as conn:
            for i in range(8): conn.put(i)
            conn.getAll()

        self.assertEqual(set(log._returned), {str(x) for x in range(8)})

    def test_logging_basis_process(self):

        class LoggingProcess(PoolProcess):

            def __init__(self):
                self.log = logging.getLogger("Subprocess")
                self.log.setLevel(logging.DEBUG)

            def run(self, pid):
                self.log.info("{}".format(pid))

        log = self.TestLogger("Subprocess", level=logging.INFO)

        with PoolManager(LoggingProcess, logger=log) as pool:
            for i in range(8): pool.put(i)
            pool.getAll()

        self.assertEqual(set(log._returned), {str(x) for x in range(8)})

    def test_logging_hierarchy(self):

        def sub_processes(pid):
            log = logging.getLogger("test.submodule")
            log.setLevel(logging.DEBUG)
            log.info("{}".format(pid))


        higher = logging.getLogger("test")
        higher.setLevel(logging.DEBUG)
        higherHandle = self.TestHandler()
        higher.addHandler(higherHandle)

        with PoolManager(sub_processes, logger=higher) as pool:
            for i in range(8): pool.put(i)
            pool.getAll()

        self.assertEqual(set(higherHandle._returned), {str(x) for x in range(8)})

    def test_logging_init(self):

        logger = logging.getLogger("init_test")
        logger2 = logging.getLogger("init_test2")

        # Test with init
        with PoolManager(lambda x: x, logger=logger) as pool:
            pass

        with PoolManager(lambda x: x, logger=[logger, logger2]) as pool:
            pass

        pool = PoolManager(lambda x: x)
        pool.addLogger(logger)
        pool.addLogger(logger2)
        pool.start()
        pool.close()

    def test_logging_raises_error(self):

        # Test incorrect definition of a single thing
        with pytest.raises(TypeError):
            with PoolManager(lambda x: x, logger=0.1) as pool:
                pass

        with pytest.raises(TypeError):
            with PoolManager(lambda x: x, logger=[1,2]) as pool:
                pass

        log = logging.getLogger("test5")

        pool = PoolManager(lambda x: x)
        pool.start()

        with pytest.raises(RuntimeError):
            pool.addLogger(log)

        pool.close()