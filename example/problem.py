__all__ = ['operations']

from time import sleep


def add(args):
    a, b = args
    sleep(3)
    return a + b

def subtract(args):
    a, b = args
    sleep(3)
    return a - b

def multiply(args):
    a, b = args
    sleep(5)
    return a * b

def divide(args):
    a, b = args
    sleep(7)
    return a / b

operations = add, subtract, multiply, divide
for op in operations:
    op.stateful = 2
    op.batch_size = 5

inputs = range(11)
