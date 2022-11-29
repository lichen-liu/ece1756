import argparse
from contextlib import contextmanager
import logging
import subprocess
from timeit import default_timer
import ram_mapper
from pathlib import Path


def run_ram_mapper(output_dir: Path, arch_str: str) -> float:
    parser = argparse.ArgumentParser()
    ram_mapper.init(parser)
    output_path = output_dir.joinpath('output.txt')
    fpga_area_geomean = ram_mapper.main(parser.parse_args(
        ['--lb=logic_block_count.txt', '--lr=logical_rams.txt', f'--out={output_path}', f'--arch={arch_str}']))
    return fpga_area_geomean


def prepare_suite_dir(suite_name: str) -> Path:
    # creating a new directory
    p_path = Path('exploration_results')
    p_path.mkdir(exist_ok=True)

    suite_path = p_path.joinpath(
        'suite_' + str(len([f for f in p_path.iterdir() if f.is_dir()])) + '_' + suite_name)
    suite_path.mkdir(exist_ok=False)

    logging.debug(f'Created suite directory: {suite_path}')
    return suite_path


def prepare_run_dir(suite_path: Path, run_name: str) -> Path:
    run_path = suite_path.joinpath(
        'run_' + str(len([f for f in suite_path.iterdir() if f.is_dir()])) + '_' + run_name)
    run_path.mkdir(exist_ok=False)

    logging.debug(f'Created run directory: {run_path}')
    return run_path


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


def main():
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-7s [%(filename)s] %(message)s',  datefmt='%m%d:%H:%M:%S', level=logging.INFO)
    with elapsed_timer() as elapsed:
        run()
    logging.warning(f'Total elapsed {elapsed():.3f} seconds')


def compose_bram_arch_str(bram_size: int, max_width: int, ratio: int) -> str:
    return f'-b {bram_size} {max_width} {ratio} 1'


def run():
    bram_size = 1024

    suite_path = prepare_suite_dir(suite_name='B' + str(bram_size))

    # run_name = 'default_arch'
    # arch_str = '-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1'

    max_width_candidates = [8, 32, 128, 256, 1024]
    ratio_candidates = [1, 2, 10, 50, 200]
    candidate_idx = 0
    num_candidates = len(max_width_candidates) * len(ratio_candidates)

    results = list()
    for max_width in max_width_candidates:
        for ratio in ratio_candidates:
            run_name = f'B{bram_size}_W{max_width}_R{ratio}'
            arch_str = compose_bram_arch_str(
                bram_size=bram_size, max_width=max_width, ratio=ratio)
            logging.warning(
                f'{candidate_idx}/{num_candidates} [{run_name}] Running: {arch_str}')
            run_path = prepare_run_dir(
                suite_path=suite_path, run_name=run_name)
            fpga_area_geomean = run_ram_mapper(
                output_dir=run_path, arch_str=arch_str)
            logging.warning(
                f'    {candidate_idx}/{num_candidates} [{run_name}] Done: FPGA AREA: {fpga_area_geomean:.6E}')
            results.append((fpga_area_geomean, max_width, ratio, run_path))
            candidate_idx += 1

    logging.warning('------------------------')
    logging.warning('All done, results for bram_size {bram_size}')
    logging.warning('[idx]\tarea\tmax_width\tratio')
    sorted_results = sorted(results)
    for idx, result in enumerate(sorted_results):
        area, max_width, ratio, _ = result
        logging.warning(f'[{idx}]\t{area:6E}\t{max_width}\t{ratio}')

    # Run checker and print area
    logging.warning('==========BEST==========')
    area, max_width, ratio, run_path = sorted_results[0]
    arch_str = compose_bram_arch_str(
        bram_size=bram_size, max_width=max_width, ratio=ratio)
    mapping_file_path = run_path.joinpath('output.txt')
    checker_command = ['./checker', arch_str, '-t',
                       'logical_rams.txt', 'logic_block_count.txt', f'{mapping_file_path}']
    out_str = subprocess.check_output(checker_command)
    for line in out_str.splitlines():
        logging.warning(line)
    logging.warning('========================')


if __name__ == '__main__':
    main()
