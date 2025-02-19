#!/usr/bin/env python

"""Wrapper script for testing the performance of simple AI systems.

bm_ai.py runs the following little solvers:
    - N-Queens

This used to contain an alphametics solver, but that was found to be bound
primarily by eval() performance.
"""

# Wanted by the alphametics solver.
from __future__ import division, print_function

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import optparse
import re
import string
import time
import sys

if sys.version_info[1] < 3:
    range = xrange

# Local imports
import util



# Pure-Python implementation of itertools.permutations().
def permutations(iterable, r=None):
    """permutations(range(3), 2) --> (0,1) (0,2) (1,0) (1,2) (2,0) (2,1)"""
    pool = tuple(iterable)
    n = len(pool)
    if r is None:
        r = n
    indices = list(range(n))
    cycles = list(range(n-r+1, n+1)[::-1])
    yield tuple(pool[i] for i in indices[:r])
    while n:
        for i in reversed(range(r)):
            cycles[i] -= 1
            if cycles[i] == 0:
                indices[i:] = indices[i+1:] + indices[i:i+1]
                cycles[i] = n - i
            else:
                j = cycles[i]
                indices[i], indices[-j] = indices[-j], indices[i]
                yield tuple(pool[i] for i in indices[:r])
                break
        else:
            return


# From http://code.activestate.com/recipes/576647/
def n_queens(queen_count):
    """N-Queens solver.

    Args:
        queen_count: the number of queens to solve for. This is also the
            board size.

    Yields:
        Solutions to the problem. Each yielded value is looks like
        (3, 8, 2, 1, 4, ..., 6) where each number is the column position for the
        queen, and the index into the tuple indicates the row.
    """
    cols = range(queen_count)
    for vec in permutations(cols):
        if (queen_count == len(set(vec[i]+i for i in cols))
                        == len(set(vec[i]-i for i in cols))):
            yield vec


def test_n_queens(iterations):
    # Warm-up runs.
    list(n_queens(8))
    list(n_queens(8))

    times = []
    for _ in range(iterations):
        t0 = time.time()
        list(n_queens(8))
        t1 = time.time()
        times.append(t1 - t0)
    return times


if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description=("Test the performance of simple AI solvers."))
    util.add_standard_options_to(parser)
    options, args = parser.parse_args()

    util.run_benchmark(options, options.num_runs, test_n_queens)
