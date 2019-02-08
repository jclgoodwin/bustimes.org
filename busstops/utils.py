def format_gbp(string):
    amount = float(string)
    if amount < 1:
        return '{}p'.format(int(amount * 100))
    return '£{:.2f}'.format(amount)
