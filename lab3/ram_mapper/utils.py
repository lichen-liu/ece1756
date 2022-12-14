from __future__ import annotations
from operator import add, sub
from timeit import default_timer
from contextlib import contextmanager
from collections import OrderedDict
from . import logger
import math
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple, Type, TypeVar


def proccess_initializer(args):
    # Logger setting for module execution mode
    logger.init_logger(logger.verbosity_to_logging_level(
        args.verbose, args.quiet))


@contextmanager
def elapsed_timer():
    '''
    https://stackoverflow.com/a/30024601
    '''
    start = default_timer()
    def elapser(): return default_timer() - start
    yield lambda: elapser()
    end = default_timer()
    def elapser(): return end-start


def list_grow(l: List[int], size: int) -> List[int]:
    to_grow = size - len(l)
    if to_grow > 0:
        l.extend([0] * to_grow)
    return l


def list_set(l: List[int], idx: int, val: int) -> List[int]:
    list_grow(l=l, size=idx+1)
    l[idx] = val
    return l


def list_get(l: List[int], idx: int) -> int:
    list_grow(l=l, size=idx+1)
    return l[idx]


def list_add(l1: List[int], l2: List[int]) -> List[int]:
    size = max(len(l1), len(l2))
    list_grow(l=l1, size=size)
    list_grow(l=l2, size=size)
    return list(map(add, l1, l2))


def list_sub(l1: List[int], l2: List[int]) -> List[int]:
    size = max(len(l1), len(l2))
    list_grow(l=l1, size=size)
    list_grow(l=l2, size=size)
    return list(map(sub, l1, l2))


def list_items(l: list[int]) -> Iterator[Tuple[int, int]]:
    return filter(lambda kv: kv[1] != 0, enumerate(l))


def is_pow2(n: int) -> bool:
    return (n & (n-1) == 0) and n != 0


def highest_pow2_below(n: int) -> int:
    '''
    Inclusive
    '''
    p = int(math.log(n, 2))
    return int(pow(2, p))


def all_pow2_below(x: int) -> List[int]:
    '''
    Descending order, inclusive
    '''
    def all_pow2_below_helper(a: int, l: List[int]) -> List[int]:
        if a >= 1:
            a = highest_pow2_below(a)
            l.append(a)
            if a > 1:
                return all_pow2_below_helper(a - 1, l)
        return l
    return all_pow2_below_helper(x, [])


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


T = TypeVar("T")


def make_sorted_1d_dict(dict_1d: Dict[int, T]) -> OrderedDict[int, T]:
    return OrderedDict(sorted(dict_1d.items()))


def make_sorted_2d_dict(dict_2d: Dict[int, Dict[int, T]]) -> OrderedDict[int, OrderedDict[int, T]]:
    return make_sorted_1d_dict({id_2d: make_sorted_1d_dict(dict_1d) for id_2d, dict_1d in dict_2d.items()})


def sorted_dict_items(d: Dict[int, T]) -> Iterator[Tuple[int, T]]:
    return sorted(d.items())


class Result(NamedTuple):
    '''
    (valid=True, None) or (valid=False, reason)
    '''
    valid: bool
    reason: Optional[str]

    def __bool__(self) -> bool:
        return self.valid

    @classmethod
    def good(cls: Type[Result]) -> Result:
        return cls(valid=True, reason=None)

    @classmethod
    def bad(cls: Type[Result], reason: str) -> Result:
        return cls(valid=False, reason=reason)

    @classmethod
    def expect(cls: Type[Result], condition: bool, reason: str) -> Result:
        '''
        Example - Early-exit if fails the check

        if not (r := Result.expect(1+1 != 2, '1+1 must be 2')):
            return r
        '''
        if condition:
            return cls.good()
        else:
            return cls.bad(reason)
