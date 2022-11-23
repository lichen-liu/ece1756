import math
from abc import abstractmethod
from typing import Dict, List, Tuple
from . import utils
from .logical_ram import RamMode
from .physical_arch import ArchProperty, RamArch, RamType, RamShape


class SIVRamArch(RamArch):
    def __init__(self, id: int):
        super().__init__(id)

    @abstractmethod
    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        assert mode in RamMode
        assert mode in self.get_supported_mode()
        return []


class BlockRamArch(SIVRamArch):
    def __init__(self, id: int, max_width_shape: RamShape, ratio_of_LB: Tuple[int, int]):
        super().__init__(id)
        self._max_width_shape = max_width_shape
        self._ratio_of_LB = ratio_of_LB

    def get_ram_type(self) -> RamType:
        return RamType.BLOCK_RAM

    def get_supported_mode(self) -> RamMode:
        return RamMode.ROM | RamMode.SinglePort | RamMode.SimpleDualPort | RamMode.TrueDualPort

    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        super().get_shapes_for_mode(mode)
        max_width = self.get_max_width().width
        mode_max_width = max_width - 1 if mode == RamMode.TrueDualPort else max_width
        return [RamShape.from_size(self.get_size(), w) for w in utils.all_pow2_below(mode_max_width)]

    def get_max_width(self) -> RamShape:
        return self._max_width_shape

    def get_ratio_of_LB(self) -> Tuple[int, int]:
        return self._ratio_of_LB

    def get_area(self) -> int:
        bits = self.get_size()
        max_width = self.get_max_width().width
        return int(round(9000 + 5*bits + 90 * math.sqrt(bits) + 600*2*max_width))


class LUTRamArch(SIVRamArch):
    def __init__(self, id: int, ratio_of_LB: Tuple[int, int]):
        super().__init__(id)
        self._ratio_of_LB = (ratio_of_LB[0]+ratio_of_LB[1], ratio_of_LB[1])

    def get_ram_type(self) -> RamType:
        return RamType.LUTRAM

    def get_supported_mode(self) -> RamMode:
        return RamMode.ROM | RamMode.SinglePort | RamMode.SimpleDualPort

    def get_shapes_for_mode(self, mode: RamMode) -> List[RamShape]:
        super().get_shapes_for_mode(mode)
        return [RamShape(20, 32), RamShape(10, 64)]

    def get_max_width(self) -> RamShape:
        return RamShape(20, 32)

    def get_ratio_of_LB(self) -> Tuple[int, int]:
        return self._ratio_of_LB

    def get_area(self) -> int:
        return 40000


class RegularLogicBlockArch(ArchProperty):
    '''
    For regular (non-LUTRAM) LB
    '''

    def get_area(self) -> int:
        return 35000

    def get_ratio_of_LB(self) -> Tuple[int, int]:
        '''
        ratio of logic block to regular (non-LUTRAM) LB
        '''
        return (2, 1)

    def get_ratio_to_LUT(self) -> Tuple[int, int]:
        '''
        ratio of logic block to lut
        '''
        return (1, 10)

    def __str__(self):
        ratio_to_lut_str = str(self.get_ratio_to_LUT()).replace(' ', '')
        return f'RegularLogicBlock self:LUT{ratio_to_lut_str} {super().__str__()}'


def create_ram_arch_from_str(id: int, checker_str: str) -> SIVRamArch:
    splitted = checker_str.lower().split()
    if RamType.BLOCK_RAM.value.lower() in splitted[0]:
        sz, mw, lb, br = splitted[1:]
        return BlockRamArch(id,
                            RamShape.from_size(int(sz), int(mw)),
                            (int(lb), int(br)))

    if RamType.LUTRAM.value.lower() in splitted[0]:
        lb, lr = splitted[1:]
        return LUTRamArch(id, (int(lb), int(lr)))

    raise Exception('Unrecognized checker_str RamType')


def create_all_ram_arch_from_strs(checker_strs: List[str]) -> Dict[int, SIVRamArch]:
    '''
    id starting from 1
    '''
    return {id+1: create_ram_arch_from_str(id+1, checker_str) for id, checker_str in enumerate(checker_strs)}


def create_all_ram_arch_from_str(raw_checker_str: str) -> Dict[int, SIVRamArch]:
    return create_all_ram_arch_from_strs(list(filter(len, raw_checker_str.split('-'))))


def generate_default_lutram() -> LUTRamArch:
    return create_ram_arch_from_str(1, '-l 1 1')


def generate_default_8k_bram() -> BlockRamArch:
    return create_ram_arch_from_str(2, '-b 8192 32 10 1')


def generate_default_128k_bram() -> BlockRamArch:
    return create_ram_arch_from_str(3, '-b 131072 128 300 1')


def generate_default_ram_arch() -> Dict[int, SIVRamArch]:
    return create_all_ram_arch_from_str(
        '-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1')

# When physical RAMs are combined in parallel to create a wider word, no extra logic is needed.
# When physical RAMs are combined to implement a deeper RAM, extra logic is needed. If we combine R physical RAMs to make a logical RAM that is R times deeper than the maximum depth of the physical RAM, we will need to include extra logic to:
# 1. Decode which RAM we must activate on a write.
#    This requires a single log2(R) : R decoder.
#    This can be built using R LUTs, each of which must have log2(R) inputs.
#    Note also that for the special case of a 1:2 decoder, one of the two (1-input) LUTs is a buffer, so you really only need 1 (not 2) LUTs for that case.
# 2. Multiplexers to select the appropriate read data word from the various physical RAM blocks.
#    A total of W multiplexers of size R : 1 will be required, where W is the width of the logical RAM.
#    A single 4:1 multiplexer can be implemented in a 6-LUT (and uses all 6 inputs). Larger multiplexers can be built by cascading 4:1 multiplexers together in a tree.


def determine_write_decoder_luts(r: int) -> int:
    '''
    r - r physical RAMs in serial
    '''
    assert r > 1
    return 1 if r == 2 else r


def determine_read_mux_luts_per_bit(r: int) -> int:
    '''
    r - r physical RAMs in serial
    '''
    def helper(r: int) -> int:
        n_4mux = int(math.ceil(r / 4.0))
        if n_4mux == 1:
            # no cascade needed, terminates at current level
            return n_4mux
        else:
            # need cascade, go to next level
            return n_4mux + helper(n_4mux)
    assert r > 1
    return helper(r)


def determine_read_mux_luts(r: int, logical_w: int) -> int:
    '''
    r - r physical RAMs in serial
    logical_w - the width of the logical RAM
    '''
    assert logical_w > 0
    return logical_w*determine_read_mux_luts_per_bit(r)


def determine_extra_luts(num_series: int, logical_w: int, ram_mode: RamMode):
    '''
    num_series - r physical RAMs in serial
    logical_w - the width of the logical RAM
    ram_mode - RamMode
    '''
    assert ram_mode in RamMode
    assert num_series <= 16

    if num_series == 1:
        return 0

    write_luts = determine_write_decoder_luts(r=num_series)
    read_luts = determine_read_mux_luts(r=num_series, logical_w=logical_w)
    if ram_mode == RamMode.ROM:
        # r
        return read_luts
    elif ram_mode == RamMode.SinglePort:
        # r/w
        return read_luts + write_luts
    elif ram_mode == RamMode.SimpleDualPort:
        # r + w
        return read_luts + write_luts
    elif ram_mode == RamMode.TrueDualPort:
        # r/w + r/w
        return 2*(read_luts + write_luts)
    else:
        assert False, 'Unsupported RamMode'
