import unittest

import time

from better.multiprocessing import PoolManager

class Test_PoolManager(unittest.TestCase):

    def test_Termination(self):
        """ Show that despite the fact that the with statement has concluded. That the subprocesses continue to work on
        the tasks given """

        def delay(length):
            start = time.time()
            while time.time() - start < length:
                continue

        with PoolManager(delay, processes=4) as pool:
            for _ in range(4): pool.put(10)

            time.sleep(5)

if __name__ == "__main__":
    unittest.main()