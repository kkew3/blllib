from problem import operations, inputs
from blllib import Pipeline


with Pipeline(operations) as pipeline:
    for output in pipeline.apply(inputs):
        assert int(output) == 1
