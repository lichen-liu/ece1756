from . import logical_ram


def main():
    hello()


def hello():
    lr = logical_ram.LogicalRam(
        circuit_id=0, ram_id=0, mode='hi', depth=24, width=32)
    print('hello')
    print(lr)
