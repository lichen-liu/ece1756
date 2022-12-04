import argparse
from contextlib import contextmanager
from datetime import datetime
import logging
import os
import pathlib
import subprocess
from timeit import default_timer
from pathlib import Path
from typing import NamedTuple, Optional


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

    logging.info(f'Created run directory: {run_path}')
    return run_path


def get_script_path() -> Path:
    return pathlib.Path(__file__).parent.resolve()


class VPRRunParam(NamedTuple):
    arch_config_file: str = './k6_N10_40nm.xml'
    seed: int = 1
    blif_file: str = './a4_benchmarks/frisc.blif'
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


def parse_circuit_qor(run_path: Path):
    pass


def run_vpr_circuit(suite_path: Path, circuit_path=None):
    circuit_name = circuit_path

    # Find the minimum channel width
    run_path = prepare_run_dir(suite_path=suite_path, run_name='frisc')
    run_cmdline_list = VPRRunParam(route_chan_width=96).to_cmdline()
    logging.info(' '.join(run_cmdline_list))
    subprocess.check_call(
        args=run_cmdline_list,
        cwd=run_path)
    parse_circuit_qor(run_path=run_path)


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
    run_vpr_circuit(suite_path=suite_path, circuit_path=None)

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
