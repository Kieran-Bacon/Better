import unittest

import time

from better.multiprocessing import PoolManager

class Test_PoolManager(unittest.TestCase):

    def test_daemon_False(self):
        """ Show that despite the fact that the with statement has concluded. That the subprocesses continue to work on
        the tasks given """

        def delay(length):
            start = time.time()
            while time.time() - start < length:
                continue

        with PoolManager(delay, size=4, daemon=False) as pool:
            for _ in range(4): pool.put(10)

            time.sleep(5)

if __name__ == "__main__":
    unittest.main()