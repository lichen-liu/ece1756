from __future__ import annotations
import logging
import math
from typing import List, NamedTuple, Optional, Type


def init_logger(level=logging.DEBUG):
    # Line number : ":%(lineno)d"
    # TODO: set default to logging.INFO
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)-6s [%(filename)s] %(message)s',
                        datefmt='%Y%m%d:%H:%M:%S', level=level)


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
    def satisfies(cls: Type[Result], condition: bool, reason: str) -> Result:
        '''
        Example - Early-exit if fails the check

        if not (r := Result.satisfies(1+1 != 2, '1+1 must be 2')):
            return r
        '''
        if condition:
            return cls.good()
        else:
            return cls.bad(reason)
