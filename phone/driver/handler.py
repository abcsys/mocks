import digi
from digi import on


@on.mount
def h(model):
    ...


if __name__ == '__main__':
    digi.run()

