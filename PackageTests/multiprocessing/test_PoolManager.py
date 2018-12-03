import unittest, pytest

from better.multiprocessing import PoolManager

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
                pool.getall()