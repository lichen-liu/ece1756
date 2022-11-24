import argparse
import ram_mapper

# Run
parser = argparse.ArgumentParser()
ram_mapper.init(parser)
ram_mapper.run(parser.parse_args())
