import unittest
import random
import types

from better import threading

class Test_ThreadingFor(unittest.TestCase):

    def setUp(self):

        def threading_loop(item): return item * 2

        self.function = threading_loop
        self.inputs = [1,2,3,4,5]
        self.outputs = [2,4,6,8,10]

    def test_threadingfor(self):

        result = threading.tfor(self.function, self.inputs)

        self.assertEqual(set(result), set(self.outputs))

    def test_threadingfor_maintain_order(self):

        result = threading.tfor(self.function, self.inputs, ordered=True)

        self.assertEqual(result, self.outputs)

    def test_threading_for_decorator(self):

        @threading.dtfor()
        def multiple(item):
            return item*10

        example = multiple([12,14,15,13,17,15])

        self.assertEqual(set(example), {x*10 for x in [12,14,15,13,17,15]})

    def test_threading_for_order_decorator(self):

        @threading.dtfor(ordered=True)
        def orderedMultiple(item):
            return item*10

        example = orderedMultiple([12,14,15,13,17,15])

        self.assertEqual(example, [x*10 for x in [12,14,15,13,17,15]])

    def test_threading_for_yields_decorator(self):
        @threading.dtfor(yields=True)
        def yields(item):
            return item*10

        generator = yields(self.inputs)

        self.assertIsInstance(generator, types.GeneratorType)

        outputs = {x*10 for x in self.inputs}
        for item in generator: self.assertIn(item, outputs)

    def test_threading_for_yields_order_decorator(self):
        @threading.dtfor(yields=True, ordered=True)
        def yields(item):
            return item*10

        for result, expected in zip(yields(self.inputs), self.inputs):
            self.assertEqual(result, expected*10)

    def test_class_threading(self):

        class Example:

            @staticmethod
            @threading.dtfor(ordered=True)
            def worker(item):
                return item*2

        e = Example()

        self.assertEqual([2,4,6,8,10], e.worker([1,2,3,4,5]))