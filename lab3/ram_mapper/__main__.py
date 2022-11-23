import argparse
import ram_mapper

# Logger setting for module execution mode
ram_mapper.init_logger()

# Run
parser = argparse.ArgumentParser()
ram_mapper.init(parser)
ram_mapper.run(parser.parse_args())
