from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import pathlib
import re
import statistics
import subprocess
from timeit import default_timer
from pathlib import Path
from typing import ClassVar, Iterable, NamedTuple, Optional, Pattern, Sequence


def prepare_suite_dir(suite_name: str) -> Path:
    # creating a new directory
    p_path = Path('vpr_results')
    p_path.mkdir(exist_ok=True)

    suite_idx = len([f for f in p_path.iterdir() if f.is_dir()])
    time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    suite_path = p_path.joinpath(
        f'suite_{suite_idx}_{suite_name}_{time_str}')
    suite_path.mkdir(exist_ok=False)

    logging.info(f'Created suite directory: {suite_path}')
    return suite_path


def prepare_run_dir(suite_path: Path, run_name: str) -> Path:
    run_path = suite_path.joinpath(
        'run_' + str(len([f for f in suite_path.iterdir() if f.is_dir()])) + '_' + run_name)
    run_path.mkdir(exist_ok=False)

    logging.debug(f'Created run directory: {run_path}')
    return run_path


def prepare_tmp_dir(run_path: Path, name: str) -> Path:
    tmp_path = run_path.joinpath('tmp_' + name)

    tmp_path.mkdir(exist_ok=False)

    logging.debug(f'Created tmp directory: {tmp_path}')
    return tmp_path


def get_script_path() -> Path:
    return pathlib.Path(__file__).parent.resolve()


class VPRRunParam(NamedTuple):
    blif_file: str
    seed: int
    arch_config_file: str = './k6_N10_40nm.xml'
    route_chan_width: Optional[int] = None

    def to_cmdline(self) -> str:
        current_script_path = get_script_path()

        def to_abs_path(target_path: str) -> str:
            if not Path(target_path).is_absolute():
                return os.path.join(current_script_path, target_path)
            else:
                return target_path

        vpr_path = to_abs_path('./vtr-verilog-to-routing-8.0.0/build/vpr/vpr')
        arch_config_path = to_abs_path(self.arch_config_file)
        blif_path = to_abs_path(self.blif_file)
        cmdline_list = [
            vpr_path,
            arch_config_path,
            blif_path,
            '--seed', str(self.seed)
        ]
        if self.route_chan_width is not None:
            cmdline_list += ['--route_chan_width', str(self.route_chan_width)]
        return cmdline_list

    def run(self, cwd: Path):
        run_cmdline_list = self.to_cmdline()
        logging.debug(' '.join(run_cmdline_list))
        subprocess.check_call(
            args=run_cmdline_list,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)


def geomean_int(in_list: Iterable[int]) -> float:
    factor = 10000000.0
    in_list_scaled_down = map(
        lambda area: float(area)/factor, in_list)
    geomean_scaled_down = statistics.geometric_mean(in_list_scaled_down)
    geomean = geomean_scaled_down * factor
    return geomean


def geomean_float(in_list: Iterable[float]) -> float:
    factor = 1000000.0
    in_list_scaled_down = map(
        lambda area: float(area)/factor, in_list)
    geomean_scaled_down = statistics.geometric_mean(in_list_scaled_down)
    geomean = geomean_scaled_down * factor

    return geomean


@dataclass
class CircuitQoR:
    minimum_channel_width: Optional[int] = None

    channel_width: Optional[int] = None
    routing_area_total: Optional[float] = None
    routing_area_per_tile: Optional[float] = None
    critical_path_delay: Optional[float] = None
    fmax: Optional[float] = None

    # Class variables
    minimum_channel_width_regex: ClassVar[Pattern] = re.compile(
        r'Best routing used a channel width factor of (\d+)')
    circuit_routing_channel_width_regex: ClassVar[Pattern] = re.compile(
        r'Circuit successfully routed with a channel width factor of (\d+)')

    numeric_pattern: ClassVar[str] = r'[-+]?(?:(?:\d*\.\d+)|(?:\d+\.?))(?:[Ee][+-]?\d+)?'

    routing_area_regex: ClassVar[
        Pattern] = re.compile(f'\s*Total routing area: ({numeric_pattern}), per logic tile: ({numeric_pattern})')
    timing_regex: ClassVar[Pattern] = re.compile(
        f'\s*Final critical path: ({numeric_pattern}) ns, Fmax: ({numeric_pattern}) MHz')

    @classmethod
    def from_geomean(cls, qors: Sequence[CircuitQoR]) -> CircuitQoR:
        return cls(
            channel_width=geomean_int(
                map(lambda qor: qor.channel_width, qors)),
            routing_area_total=geomean_float(
                map(lambda qor: qor.routing_area_total, qors)),
            routing_area_per_tile=geomean_float(
                map(lambda qor: qor.routing_area_per_tile, qors)),
            critical_path_delay=geomean_float(
                map(lambda qor: qor.critical_path_delay, qors)),
            fmax=geomean_float(
                map(lambda qor: qor.fmax, qors))
        )

    def parse_line(self, line: str) -> bool:
        if r := self.minimum_channel_width_regex.match(line):
            self.minimum_channel_width = int(r.group(1))
        elif r := self.circuit_routing_channel_width_regex.match(line):
            self.channel_width = int(r.group(1))
        elif r := self.routing_area_regex.match(line):
            self.routing_area_total = float(r.group(1))
            self.routing_area_per_tile = float(r.group(2))
        elif r := self.timing_regex.match(line):
            self.critical_path_delay = float(r.group(1))
            self.fmax = float(r.group(2))
        return True

    def is_route_successful(self) -> bool:
        return ((self.channel_width is not None) and
                (self.routing_area_total is not None) and
                (self.routing_area_per_tile is not None) and
                (self.critical_path_delay is not None) and
                (self.fmax is not None))


def parse_circuit_qor(log_dir: Path, require_minimum_channel_width: bool = False) -> CircuitQoR:
    log_path = log_dir.joinpath('vpr_stdout.log')
    qor = CircuitQoR()

    with open(log_path) as f:
        for line in f:
            qor.parse_line(line)

    if require_minimum_channel_width:
        assert qor.minimum_channel_width is not None
    return qor


def run_vpr_circuit_of_seed(run_path: Path, circuit_name: str, seed: int, circuit_path: str) -> Optional[CircuitQoR]:
    logging.info(f'Running VPR for [{circuit_name}/seed={seed}]')

    # Run to find the minimum channel width
    logging.info(f'  - Run to find minimum channel width')
    tmp_path = prepare_tmp_dir(run_path=run_path, name=f'seed{seed}_step0')
    VPRRunParam(blif_file=circuit_path, seed=seed).run(cwd=tmp_path)
    qor = parse_circuit_qor(
        log_dir=tmp_path, require_minimum_channel_width=True)
    if not qor.is_route_successful():
        return None
    logging.info(f'    Min channel width={qor.minimum_channel_width}')

    # Rerun with 1.3x minimum channel width
    route_channel_width = qor.minimum_channel_width * 1.3
    # Round to nearest even number
    route_channel_width = round(route_channel_width/2)*2
    logging.info(
        f'  - Run 1.3x minimum channel width ({route_channel_width})')
    tmp_path = prepare_tmp_dir(run_path=run_path, name=f'seed{seed}_step1')
    VPRRunParam(blif_file=circuit_path, seed=seed,
                route_chan_width=route_channel_width).run(cwd=tmp_path)
    qor = parse_circuit_qor(log_dir=tmp_path)
    if not qor.is_route_successful():
        return None
    logging.info(f'    {qor}')
    return qor


def run_vpr_circuit_across_seeds(run_path: Path, circuit_name: str, num_seeds: int, circuit_path: str) -> CircuitQoR:
    qors = list()
    seed = 0
    while len(qors) < num_seeds:
        qor = run_vpr_circuit_of_seed(
            run_path=run_path, circuit_name=circuit_name, seed=seed, circuit_path=circuit_path)
        if qor is not None:
            assert qor.is_route_successful()
            qors.append(qor)
        seed += 1
    logging.info(f'{num_seeds} seeds done for [{circuit_name}]')
    qor = CircuitQoR.from_geomean(qors)
    logging.info(f'  {qor}')
    return qor


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


def main(args):
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-7s [%(filename)s] %(message)s',  datefmt='%m%d:%H:%M:%S', level=logging.INFO)
    with elapsed_timer() as elapsed:
        runner(args)
    logging.warning(f'Total elapsed {elapsed():.3f} seconds')


def init(parser):
    pass


def runner(args):
    suite_path = prepare_suite_dir(suite_name='test')

    circuit_path = './a4_benchmarks/frisc.blif'
    circuit_name = Path(circuit_path).with_suffix('').name
    run_path = prepare_run_dir(suite_path=suite_path, run_name=circuit_name)
    qor = run_vpr_circuit_across_seeds(
        run_path=run_path,
        circuit_name=circuit_name,
        num_seeds=5,
        circuit_path=circuit_path)
    assert qor is not None and qor.is_route_successful()

    # # Run checker and print area
    # logging.warning('==========BEST==========')
    # area, max_width, ratio, run_path = sorted_results[0]
    # arch_str = compose_bram_arch_str(
    #     bram_size=bram_size, max_width=max_width, ratio=ratio)
    # if use_lutram:
    #     arch_str = '-l 1 1 ' + arch_str
    # mapping_file_path = run_path.joinpath('mapping.txt')
    # checker_command = ['./checker', arch_str, '-t',
    #                    'logical_rams.txt', 'logic_block_count.txt', f'{mapping_file_path}']
    # checker_command_str = ' '.join(checker_command)
    # logging.warning(f'{checker_command_str}')
    # out_str = subprocess.check_output(checker_command_str, shell=True)
    # for line in out_str.splitlines():
    #     logging.warning(line.decode("utf-8"))
    # logging.warning('========================')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    init(parser)
    main(parser.parse_args())
