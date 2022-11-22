from __future__ import annotations
from collections import OrderedDict
import logging
import math
from typing import Dict, List, NamedTuple, Optional, Type, TypeVar


def init_logger(level=logging.DEBUG):
    # Line number : ":%(lineno)d"
    # TODO: set default to logging.INFO
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)-6s [%(filename)s] %(message)s',
                        datefmt='%Y%m%d:%H:%M:%S', level=level)


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


T = TypeVar("T")


def make_sorted_1d_dict(dict_1d: Dict[int, T]) -> OrderedDict[int, T]:
    return OrderedDict(sorted(dict_1d.items()))


def make_sorted_2d_dict(dict_2d: Dict[int, Dict[int, T]]) -> OrderedDict[int, OrderedDict[int, T]]:
    return make_sorted_1d_dict({id_2d: make_sorted_1d_dict(dict_1d) for id_2d, dict_1d in dict_2d.items()})


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
