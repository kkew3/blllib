# Batched Parallel Pipeline lib

`blllib` is a brief library module that defines a lazy-evaluated, multiprocessing pipeline `Pipeline`.
A `Pipeline` is defined as a sequence of callable objects.

For example,

```python
from blllib import Pipeline
operations = ...   # a sequence of callables
inputs = ...       # an iterable of inputs
with Pipeline(operations) as pipeline:
    for output in pipeline.apply(inputs):
        print(output)
```

The `pipeline.apply` can be called *only once*.

**Installation**:

```
pip install blllib
```


## Statefulness of callable objects

For each callable object, it may be

- **stateful**: must be run sequentially
- **conditionally stateless**: can be run in parallel if the inputs have been organized in batch
- **stateless**: can be run in parallel

For example, an accumulator, as defined below, is stateful.
The second-order difference operator, as defined below, is conditionally stateless providing a batch of three (comparing `Difference2_stateful` and `Difference2_stateless`).
The function that negates its input (i.e. converting `1` to `-1`) is stateless.

```python
class Accumulator(object):
    def __init__(self):
        self.acc = 0
    def __call__(self, x):
        self.acc += x
        return self.acc

class Difference2_stateful(object):
    def __init__(self):
        self.cache = collections.deque(maxlen=3)
    def __call__(self, x):
        self.cache.append(x)
        if len(self.cache) == 3:
            return self.cache[-1] - self.cahce[0]

class Difference2_stateless(object):
    """Expecting batched inputs"""
    def __call__(self, batch):
        x, _, z = batch
        return z - x
```

## Callable object types

To run in parallel, a callable object must be pickleable.
A notable example of a callable that's not pickleable is shown below:

```python
def g():
    yield from range(10)

class Function(object):
    def __init__(self):
        self.nums = g()
    def __call__(self, *args, **kwargs):
        pass

import pickle
pickle.dumps(Function())
# Traceback (most recent call last):
#   File "<stdin>", line 1, in <module>
# TypeError: can't pickle generator objects
```

To assist scheduling of the processes, `Pipeline` expects optionally one global metric when instantiation and two callable-specific metrics when parsing each callable object.

The global metric:

- `n_cpu`: The number of cores in total to be allocated to all non-stateful callables.
Default to `max(1, N-K)` where `N` is the total number of CPU cores available as returned by `multiprocessing.cpu_count()` and `K` the number of non-stateful callables.

The callable-specific metrics:

- `stateful`: If `True`, the callable is stateful, and should be of type `Callable[[S], T]`, mapping `Iterable[S]` to `Iterable[T]`.
If `False`, the callable is stateless, and should be of type `Callable[[S], T]`, mapping `Iterable[S]` to `Iterable[T]`.
If a positive integer, the callable is conditionally stateless, and should be of type `Callable[[Sequence[S]], T]`, mapping batched `Iterable[S]` to `Iterable[T]`.
Otherwise, error will be raised at `Pipeline` instantiation.
This metric is default to `True` if not found.
- `batch_size`: The number of inputs or batches of inputs fed at once.
For each stateful callable, at most `batch_size` number of inputs are fed to the callable (in a separate process).
Later inputs have to wait for the production of the output induced by the earliest input.
For each non-stateful callable, at most `batch_size` number of inputs are fed to the pool.
Likewise, later inputs have to wait for the production of the output induced by the earliest input.
When `batch_size = 1`, the underlying process/pool will essentially run jobs sequentially.
This metric is default to `1` if not found.

The callable-specific metrics can be specified as either the instance variable or the class variable.
For example:

```python
# specify as instance variables
def add(args):
    x, y = args
    return x + y

add.stateful = 2
add.batch_size = 10

# specify as instance variables
class Add(object):
    def __init__(self):
        self.stateful = 2
        self.batch_size = 10
    def __call__(self, args):
        x, y = args
        return x + y

# specify as class variables
class Add2(object):
    stateful = 2
    batch_size = 10
    def __call__(self, args):
        x, y = args
        return x + y
```
