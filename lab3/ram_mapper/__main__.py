import ram_mapper
import logging

# Logger setting for module execution mode
# Line number : ":%(lineno)d"
logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)-6s [%(filename)s] %(message)s',
                    datefmt='%Y%m%d:%H:%M:%S', level=logging.DEBUG)


# Run
ram_mapper.main()
