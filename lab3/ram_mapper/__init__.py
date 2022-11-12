from . import logical_ram


def main():
    hello()


def hello():
    lr = logical_ram.LogicalRam.from_str('0	0	SimpleDualPort	45	12')
    print('hello')
    print(lr)
