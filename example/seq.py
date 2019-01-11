from collections import deque
from problem import operations, inputs

def batch2(iterator):
    cache = deque(maxlen=2)
    for x in iterator:
        cache.append(x)
        if len(cache) == 2:
            yield tuple(cache)

it = iter(inputs)
for op in operations:
    it = batch2(it)
    it = map(op, it)
for output in it:
    assert int(output) == 1
