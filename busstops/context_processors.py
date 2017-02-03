from random import getrandbits


def amp(request):
    return {
        'amp': 'amp' in request.GET
    }


def random(_):
    return {
        'random': bool(getrandbits(1))
    }
