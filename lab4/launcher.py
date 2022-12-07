from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import logging
from multiprocessing import Pool
import os
import pathlib
import re
import statistics
import subprocess
from timeit import default_timer
from pathlib import Path
from typing import ClassVar, Iterable, List, NamedTuple, Optional, Pattern, Sequence


def prepare_suite_dir(suite_name: str) -> Path:
    # creating a new directory
    p_path = Path('vpr_results')
    p_path.mkdir(exist_ok=True)

    suite_idx = len([f for f in p_path.iterdir() if f.is_dir()])
    time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    suite_path = p_path.joinpath(
        f'suite_{suite_idx}_{suite_name}_{time_str}')
    suite_path.mkdir(exist_ok=False)

    logging.warning(f'Created suite directory: {suite_path}')
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

    def run(self, cwd: Path) -> bool:
        run_cmdline_list = self.to_cmdline()
        logging.debug(' '.join(run_cmdline_list))
        try:
            subprocess.check_call(
                args=run_cmdline_list,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            return False
        return True


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
    seed: Optional[int] = None
    circuit: Optional[str] = None

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
        assert len(qors) > 0
        for qor in qors:
            assert qor.is_route_successful()

        circuit = qors[0].circuit
        if not all(map(lambda qor: qor.circuit == circuit, qors)):
            circuit = None

        seed = qors[0].seed
        if not all(map(lambda qor: qor.seed == seed, qors)):
            seed = None

        return cls(
            circuit=circuit,
            seed=seed,
            minimum_channel_width=geomean_int(
                map(lambda qor: qor.minimum_channel_width, qors)),
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

    def present_data(self) -> str:
        return f'min_ch_w={self.minimum_channel_width} 1.3x_rt_area_per_tile={self.routing_area_per_tile} 1.3x_rt_cp_delay={self.critical_path_delay} 1.3x_delay_area={self.routing_area_per_tile*self.critical_path_delay}'


def parse_circuit_qor(log_dir: Path, circuit: str, seed: int, minimum_channel_width: Optional[int] = None) -> CircuitQoR:
    log_path = log_dir.joinpath('vpr_stdout.log')
    qor = CircuitQoR(seed=seed, circuit=circuit,
                     minimum_channel_width=minimum_channel_width)

    with open(log_path) as f:
        for line in f:
            qor.parse_line(line)

    # If minimum_channel_width is not pre-assigned, it must be parsed
    if minimum_channel_width is None:
        assert qor.minimum_channel_width is not None
    return qor


def run_vpr_circuit_of_seed(run_path: Path, circuit_name: str, seed: int, circuit_path: str) -> Optional[CircuitQoR]:
    msg_header = f'[{circuit_name}/seed={seed}]'
    logging.info(f'Running VPR for {msg_header}')

    # Run to find the minimum channel width
    logging.info(f'{msg_header}  1. Run to find minimum channel width')
    tmp_path = prepare_tmp_dir(run_path=run_path, name=f'seed{seed}_step0')
    if not VPRRunParam(blif_file=circuit_path, seed=seed).run(cwd=tmp_path):
        return None
    qor = parse_circuit_qor(
        log_dir=tmp_path, minimum_channel_width=None, circuit=circuit_name, seed=seed)
    if not qor.is_route_successful():
        return None
    qor_min_ch_width = qor.minimum_channel_width
    logging.info(
        f'{msg_header}        Min channel width: {qor_min_ch_width}')

    # Rerun with 1.3x minimum channel width
    route_channel_width = qor_min_ch_width * 1.3
    # Round to nearest even number
    route_channel_width = round(route_channel_width/2)*2
    logging.info(
        f'{msg_header}  2. Run 1.3x minimum channel width ({route_channel_width})')
    tmp_path = prepare_tmp_dir(run_path=run_path, name=f'seed{seed}_step1')
    if not VPRRunParam(blif_file=circuit_path, seed=seed,
                       route_chan_width=route_channel_width).run(cwd=tmp_path):
        return None
    qor = parse_circuit_qor(
        log_dir=tmp_path, circuit=circuit_name, seed=seed, minimum_channel_width=qor_min_ch_width)
    if not qor.is_route_successful():
        return None
    logging.info(f'{msg_header}       Run QoR: {qor}')
    return qor


def run_vpr_circuit_across_seeds(run_path: Path, circuit_name: str, num_seeds: int, circuit_path: str) -> List[CircuitQoR]:
    qors = list()
    seed = 0
    max_attempts = num_seeds*5
    while len(qors) < num_seeds:
        qor = run_vpr_circuit_of_seed(
            run_path=run_path, circuit_name=circuit_name, seed=seed, circuit_path=circuit_path)
        if qor is not None:
            assert qor.is_route_successful()
            qors.append(qor)
        elif seed >= max_attempts:
            logging.error(
                f'[{circuit_name}] Failed to compile for {num_seeds} times with {max_attempts} attempts ({len(qors)} passed), aborting')
            return []
        seed += 1
    logging.warning(
        f'[{circuit_name}] {num_seeds} seeds ({seed} attempts) done')
    return qors


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


def init_logger(args):
    def verbosity_to_logging_level(verbose_count: int) -> int:
        if verbose_count == 0:
            return logging.WARNING
        elif verbose_count == 1:
            return logging.INFO
        else:
            return logging.DEBUG

    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-7s [%(filename)s] %(message)s',  datefmt='%m%d:%H:%M:%S', level=verbosity_to_logging_level(args.verbose))


def main(args):
    init_logger(args)
    logging.warning(f'{args}')
    with elapsed_timer() as elapsed:
        runner(args)
    logging.warning(f'Total elapsed {elapsed():.3f} seconds')


def init(parser):
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Raise logging verbosity, default is Warning+')
    parser.add_argument(
        '--seeds',
        type=int,
        default=5,
        help='Specify the number of seeds to run, default to 5'
    )
    parser.add_argument(
        '--name',
        type=str,
        required=True,
        help='Experiment name'
    )


def runner(args):
    suite_path = prepare_suite_dir(suite_name=args.name)

    # Collect all circuits
    circuit_folder = Path('./a4_benchmarks')
    circuit_paths = [x for x in circuit_folder.iterdir() if not x.is_dir()]

    # Prepare for run
    circuit_run_args = list()
    for circuit_path in circuit_paths:
        circuit_name = Path(circuit_path).with_suffix('').name
        run_path = prepare_run_dir(
            suite_path=suite_path, run_name=circuit_name)
        circuit_run_args.append(
            (run_path, circuit_name, args.seeds, circuit_path))
    logging.info(
        f'Collected {len(circuit_run_args)} circuits from {circuit_folder}')
    for circuit_run_arg in circuit_run_args:
        logging.info(f'  Arg: {circuit_run_arg}')

    # Run in parallel
    with Pool(initializer=init_logger, initargs=(args,)) as p:
        circuits_qors = p.starmap(func=run_vpr_circuit_across_seeds,
                                  iterable=circuit_run_args)

    logging.info('--------------------------')
    logging.info('Circuit Seed QoR:')
    for circuit_qors in circuits_qors:
        for circuit_qor in circuit_qors:
            logging.info(f'  {circuit_qor}')
    logging.info('')

    logging.warning('++++++++++++++++++++++++++')
    circuits_geomean_qor = [CircuitQoR.from_geomean(
        circuit_qors) for circuit_qors in circuits_qors if len(circuit_qors) > 0]
    logging.warning(
        f'Circuit Geomean QoR (from {len(circuits_geomean_qor)} successful circuits with {args.seeds} seeds):')
    for circuit_geomean_qor in circuits_geomean_qor:
        logging.warning(f'  {circuit_geomean_qor}')
    logging.warning('')

    logging.warning('**************************')
    final_qor = CircuitQoR.from_geomean(circuits_geomean_qor)
    logging.warning(
        f'Final QoR (from {len(circuits_geomean_qor)} successful circuits with {args.seeds} seeds):')
    logging.warning(f'  {final_qor}')
    logging.warning(f'  {final_qor.present_data()}')
    logging.warning('')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    init(parser)
    main(parser.parse_args())
