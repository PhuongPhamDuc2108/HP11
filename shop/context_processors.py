from decimal import Decimal

CART_SESSION_KEY = 'cart'


def cart_summary(request):
    session = getattr(request, 'session', None)
    cart = {}
    if session:
        cart = session.get(CART_SESSION_KEY, {})
    count = 0
    try:
        for qty in cart.values():
            count += int(qty)
    except Exception:
        count = 0
    return {
        'cart_count': count,
    }
