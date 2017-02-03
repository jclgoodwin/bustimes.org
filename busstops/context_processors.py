from random import randint


def amp(request):
    return {
        'amp': 'amp' in request.GET
    }


def random(_):
    return {
        'random': not randint(0, 3)
    }
