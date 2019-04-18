# better.threading.tfor

`tfor` is a function to allow the various iterations of a for loop to be conducted in a thread rather than a being executed in the main process. The idea is that work that requires IO operations with multiple files/sources can be conducted in a more efficient manner.

> NOTE: Although this attempts to be more "efficient", threading typically doesn't provide any speed up. This is due to the global interpreter lock so operations that occur in threads are still run serially. IO operations are the exception as they aren't bound by this lock, therefore, they can be speed up by this method. Its likely best to test whether it actually gives any meaningful improvement in your use case. Personally, I like the idea of this but I don't think (at least in its current state) that is it as applicable as I'd like.

## Setting up in a threading loop

Unfortunately, although this is a nice interface (supposedly... according to me...) its obviously not better than the syntax of a typical python for. It does however save you from having to write a considerable amount of threading bloat to get similar behaviour.

```python
# Traditionally
output = []
for item in tasks:
    with open(item, "r") as handler:
        output.append(do_work())

# Threading for
def for_content(item):
    with open(item, "r") as handler:
        return do_work()
output = threading.tfor(for_content, tasks)

# The tfor decorator
@threading.dtfor()
def any_function(item):
    return do_work()
output = any_function(tasks)
```

The decorator can be useful for threading the methods of a class, providing a beautiful way to incorporate threads without having to tackle the problem directly.

```python
class MyExample:

    @staticmethod
    @threading.dtfor(thread_count=4, ordered=True)
    def loadConfigs(item):
        return do_work(item)

e = MyExample()
e.loadConfigs(iterable)
```

## Reference Manual

### tfor(function, iterable, *, thread_count, ordered, yields)

- `function: callable` The function to act as the threads main method. Performs the computation normally performed in the for loop.
- `iterable: iterable` The source inputs to be processed by the function.

----

- `thread_count: int = os.cpu_count()` The number of threads that are going to be started to work on the iterable.
- `ordered: bool = False` Determine whether the return value should be returned in the order they were added in.
- `yields: bool = False` Convert the method into a generator and yield responses rather than returning outright. Saves from unnecessary memory usage.

### Decorator - dtfor(**kwargs)

The key worded arguments are passed through to the tfor function.
