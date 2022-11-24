import argparse
import ram_mapper

# Run
parser = argparse.ArgumentParser()
ram_mapper.init(parser)
ram_mapper.main(parser.parse_args())
