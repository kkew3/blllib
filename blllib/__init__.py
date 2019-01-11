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

from blllib.blllib import Pipeline
