def amp(request):
    return {
        'amp': 'amp' in request.GET
    }
