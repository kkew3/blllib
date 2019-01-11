"""
Batched parallel pipelining utilities. A pipeline here is defined as a
sequence of pickleable callable objects (e.g. not containing generator, a
notable type of objects that's not pickleable). Each callable object at each
time is fed with an input and should returns an output, which in turn serves
as the input to the next callable object. ``None`` will be discarded before
feeding into any callable object.

To make convenient process management, the callable object is optionally
expected two instance or static attributes:

    - ``stateful``: whether the operation is stateless, conditionally
      stateless, or absolutely stateful; and if conditionally stateless, how
      many states is expected. This attribute is default to ``True``
      (absolutely stateful, no parallelism)
    - ``batch_size``: how many inputs or input batches should be submitted
      at once. Note that this attribute is expected even if the underlying
      callable object is absolutely stateful, since each stateful callable is
      run in a separate process so as to achieve better efficiency. This
      attribute is default to 1 (blocked at every input or input batch, no
      parallelism)
    - ``run_in_master``: if defined, whatever its value, it makes the
      callable object run in master process, in which case ``batch_size``
      will get ignored

Example usage::

    .. code-block::

        operations = add, subtract, multiply, divide
        inputs = ...  # an iterable
        with Pipeline(operations) as pipeline:
            for output in pipeline.apply(inputs):
                print(output)

Note that ``pending_outputs`` is lazy. It yields output only if asked for.
Despite having multiple operations, the stream won't be blocked at the first
operation. At the end of the ``with`` block, all process pools are closed.
"""
import collections
import multiprocessing
import queue
import typing
from typing import Union, Tuple, Sequence, Iterable, Callable
import pdb

__all__ = ['Pipeline', 'SequentialPipeline']

S = typing.TypeVar('S')
T = typing.TypeVar('T')


def statefulness(f: Callable) -> Union[bool, int]:
    """
    See if a callable object is stateful, so as to enable multiprocessing
    preloading videos. Whether it's stateful is determined by the value of the
    instance or static variable ``stateful`` of its type, which is
    default to ``True`` if no such variable exist. The variable may be set to
    ``True``, ``False``, ``None`` (a synonym of ``False``), or a positive
    integer. If ``stateful`` is explicitly set to a positive integer (so not
    of boolean type or ``None``), it means the object is stateful but
    expects a fixed batch of inputs each time (despite that when ``stateful``
    is 1 it's essentially stateless; however, the input format will differ
    from assigning ``False`` to ``stateful``). This provides possibility of
    concurrent processing of batches of inputs.

    :param f: the callable object to test against
    :return: ``False`` if it's not stateful; ``True`` if it's stateful
             without requiring preorganized batch of inputs; and a positive
             integer if it's conditionally stateless given the batched inputs
    :raise ValueError: if ``stateful`` is not one of: ``None``, ``True``,
           ``False``, 1, 2, 3, etc. (positive integers)
    """
    s = getattr(f, 'stateful', True)
    if s is None:
        s = False
    elif s is True or s is False:
        pass
    elif isinstance(s, int):
        # ``isinstance(True, int)`` and ``isinstance(False, int)`` also return
        # ``True``. However, we have already considered these two cases.
        if s < 1:
            raise ValueError('Expected batch size at least 1 if explicity '
                             'stated, but got {}'.format(s))
    else:
        raise ValueError('Illegal stateful value: {}'.format(s))
    return s


def feeding_batch_size(f: Callable) -> int:
    return max(1, int(getattr(f, 'batch_size', 1)))


def group_into_batches(batch_size: int,
                       inputs: Iterable[T]) -> Iterable[Sequence[T]]:
    """
    Group inputs into fixed-size batched inputs.

    :param batch_size: the batch size, which must be a positive integer
    :param inputs: an iterable of inputs
    :return: an iterable of batched inputs

    >>> list(group_into_batches(1, range(5)))
    [(0,), (1,), (2,), (3,), (4,)]
    >>> list(group_into_batches(2, range(5)))
    [(0, 1), (1, 2), (2, 3), (3, 4)]
    >>> list(group_into_batches(5, range(5)))
    [(0, 1, 2, 3, 4)]
    >>> list(group_into_batches(6, range(5)))
    []
    """
    if batch_size < 1:
        raise ValueError('Expected positive batch size, but got {}'
                         .format(batch_size))
    cache = collections.deque(maxlen=batch_size)
    for x in inputs:
        cache.append(x)
        if len(cache) == cache.maxlen:
            yield tuple(cache)


def requires_batch(stateful: Union[bool, int]) -> bool:
    """
    Merely a shortcut function for clarity.
    """
    return stateful is not True and stateful is not False


def conditionally_stateless(stateful: Union[bool, int]) -> bool:
    """
    Merely a shortcut function for clarity.
    """
    return stateful is not True


def run_in_master(f: Callable) -> bool:
    return hasattr(f, 'run_in_master')


class Sentinel(object): pass


sentinel = Sentinel()


def is_sentinel(x):
    return isinstance(x, Sentinel)


def process_stateless(pool: multiprocessing.Pool,
                      f: Callable[[S], T],
                      batch_size: int,
                      iterable: Iterable[S]) -> Iterable[T]:
    it = iter(iterable)
    future_results = collections.deque()
    while True:
        try:
            while len(future_results) < batch_size:
                x = next(it)
                future_results.append(pool.apply_async(f, args=(x,)))
        except StopIteration:
            while len(future_results):
                yield future_results.popleft().get()
            break
        finally:
            if len(future_results):
                yield future_results.popleft().get()


def process_stateful_master(inq: multiprocessing.Queue,
                            outq: multiprocessing.Queue,
                            iterable: Iterable) -> Iterable:
    """
    :param inq: input queue to the worker process
    :param outq: output queue from the worker process
    :param iterable: the input stream
    :return: the output stream
    """
    it = iter(iterable)
    qcount = 0
    while True:
        try:
            while True:
                x = next(it)
                try:
                    inq.put_nowait(x)
                except queue.Full:
                    break
                else:
                    qcount += 1
        except StopIteration:
            inq.put(sentinel)
            while True:
                y = outq.get()
                if is_sentinel(y):
                    break
                else:
                    yield y
                    qcount -= 1
            break
        finally:
            if qcount:
                yield outq.get()
                qcount -= 1


def process_stateful(inq: multiprocessing.Queue,
                     outq: multiprocessing.Queue,
                     f: Callable) -> None:
    while True:
        x = inq.get()
        if is_sentinel(x):
            outq.put(x)
            break
        y = f(x)
        outq.put(y)


SubpBundleType = Tuple[multiprocessing.Queue,
                       multiprocessing.Queue,
                       multiprocessing.Process]


class Pipeline(object):
    def __init__(self, callables: Sequence[Callable], n_cpu: int = None):
        ss = list(map(statefulness, callables))
        master_count = sum(map(run_in_master, callables))
        stateful_count = sum(((not conditionally_stateless(s)
                               and not run_in_master(f))
                              for s, f in zip(ss, callables)))
        if n_cpu:
            pool_n_cpu = max(1, n_cpu - stateful_count)
        else:
            total = multiprocessing.cpu_count()
            pool_n_cpu = max(1, total - stateful_count - 1)
        self.n_cpu = pool_n_cpu
        """Number of processes in the multiprocessing.Pool"""

        self.callables = callables
        self.ss = ss
        self.pool = None  # type: typing.Optional[multiprocessing.Pool]
        self.subps = []  # type: typing.List[SubpBundleType]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.pool:
            self.pool.close()
        for inq, outq, subp in self.subps:
            # noinspection PyBroadException
            inq.put(sentinel)
            while True:
                y = outq.get()
                if is_sentinel(y):
                    break
            subp.join()
        if self.pool:
            self.pool.join()

    def apply(self, iterable: Iterable):
        setattr(self, 'iterable', iter(iterable))
        return self

    def __iter__(self):
        """
        Build computation graph only.
        """
        self.pool = multiprocessing.Pool(self.n_cpu)
        it = getattr(self, 'iterable')
        delattr(self, 'iterable')

        for s, f in zip(self.ss, self.callables):
            batch_size = feeding_batch_size(f)
            if run_in_master(f):
                if requires_batch(s):
                    it = group_into_batches(s, it)
                it = map(f, it)
            elif not conditionally_stateless(s):
                inq = multiprocessing.Queue(maxsize=batch_size)
                outq = multiprocessing.Queue()
                subp = multiprocessing.Process(target=process_stateful,
                                               name=repr(f),
                                               args=(inq, outq, f))
                subp.daemon = True
                self.subps.append((inq, outq, subp))
                subp.start()
                it = process_stateful_master(inq, outq, it)
            else:
                if requires_batch(s):
                    it = group_into_batches(s, it)
                it = process_stateless(self.pool, f, batch_size, it)
        return it


class SequentialPipeline(object):
    def __init__(self, callables: Sequence[Callable], **kwargs):
        self.callables = callables
        self.ss = list(map(statefulness, callables))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def close(self):
        pass

    def apply(self, iterable: Iterable):
        setattr(self, 'iterable', iter(iterable))
        return self

    def __iter__(self):
        it = getattr(self, 'iterable')
        delattr(self, 'iterable')

        for s, f in zip(self.ss, self.callables):
            if requires_batch(s):
                it = group_into_batches(s, it)
            it = map(f, it)
        return it
