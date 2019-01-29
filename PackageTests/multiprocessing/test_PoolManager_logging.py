import pytest, unittest

import logging
logging.basicConfig()

from better.multiprocessing import PoolManager

class Test_PoolManager_logging(unittest.TestCase):

    class TestLogger(logging.Logger):

        def handle(self, record):
            if not hasattr(self, "_returned"): self._returned = []
            self._returned.append(record.msg)

    def test_logging_basic(self):

        def sub_process(pid):
            log = logging.getLogger("Subprocess")
            log.info("{}".format(pid))

        log = self.TestLogger("Subprocess", level=logging.INFO)

        with PoolManager(sub_process, logger=log) as conn:
            for i in range(8): conn.put(i)
            conn.getAll()

        self.assertEqual(set(log._returned), {str(x) for x in range(8)})

    def test_logging_hierarchy(self):

        def sub_processes(pid):
            log = logging.getLogger("test.submodule")
            log.info("{}".format(pid))

        sub = self.TestLogger("test.submodule", level=logging.INFO)
        testlog = self.TestLogger("test", level=logging.INFO)
        notloggedlog = self.TestLogger("information", level=logging.INFO)

        with PoolManager(sub_processes, logger=[sub, testlog, notloggedlog]) as pool:
            for i in range(8): pool.put(i)
            pool.getAll()

        self.assertEqual(set(testlog._returned), {str(x) for x in range(8)})
        self.assertFalse(hasattr(notloggedlog, "_returned"))

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