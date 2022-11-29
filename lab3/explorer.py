import argparse
import logging
import ram_mapper
from pathlib import Path


def run_ram_mapper(output_dir: Path, arch_str: str) -> float:
    parser = argparse.ArgumentParser()
    ram_mapper.init(parser)
    output_path = output_dir.joinpath('output.txt')
    fpga_area_geomean = ram_mapper.main(parser.parse_args(
        ['--lb=logic_block_count.txt', '--lr=logical_rams.txt', f'--out={output_path}', f'--arch={arch_str}', '--quiet']))
    return fpga_area_geomean


def prepare_suite_dir() -> Path:
    # creating a new directory
    p_path = Path('exploration_results')
    p_path.mkdir(exist_ok=True)

    suite_path = p_path.joinpath(
        'run_' + str(len([f for f in p_path.iterdir() if f.is_dir()])))
    suite_path.mkdir(exist_ok=False)

    logging.info(f'Created suite directory: {suite_path}')
    return suite_path


def prepare_run_dir(suite_path: Path, run_name: str) -> Path:
    run_path = suite_path.joinpath(run_name)
    run_path.mkdir(exist_ok=False)
    logging.info(f'Created run directory: {run_path}')
    return run_path


def main():
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-7s [%(filename)s] %(message)s',  datefmt='%m%d:%H:%M:%S', level=logging.INFO)
    suite_path = prepare_suite_dir()

    run_name = 'default_arch'
    arch_str = '-l 1 1 -b 8192 32 10 1 -b 131072 128 300 1'
    run_path = prepare_run_dir(suite_path=suite_path, run_name=run_name)
    fpga_area_geomean = run_ram_mapper(output_dir=run_path, arch_str=arch_str)
    logging.warning(f'{run_name} FPGA AREA: {fpga_area_geomean:.6E}')


if __name__ == '__main__':
    main()
