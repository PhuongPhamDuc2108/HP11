from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from decimal import Decimal

from .forms import RegisterForm
from .models import Product, Category, Banner


def _effective_price(product: Product):
    try:
        if getattr(product, 'is_in_flash_sale', False) and getattr(product, 'flash_sale_price', None):
            return product.flash_sale_price
    except Exception:
        pass
    return product.price


# --------- Cart helpers (session-based) ---------
CART_SESSION_KEY = 'cart'

def _get_cart(session):
    return session.get(CART_SESSION_KEY, {})

def _save_cart(session, cart):
    session[CART_SESSION_KEY] = cart
    session.modified = True


def home_view(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('cat', '').strip()

    products = []
    categories = []

    try:
        qs = Product.objects.filter(is_active=True)
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        products = list(qs[:48])
        categories = list(Category.objects.all())
        # Build category tiles with thumbnail images (prefer category image, then first product image, else fallback)
        categories_tiles = []
        for cat in categories:
            if getattr(cat, 'image_url', None):
                thumb = cat.image_url
            else:
                first_with_img = Product.objects.filter(is_active=True, category=cat).exclude(image_url="").first()
                if first_with_img and first_with_img.image_url:
                    thumb = first_with_img.image_url
                else:
                    # Fallback placeholder image with category initial
                    initial = (cat.name or "?")[:1].upper()
                    thumb = f"https://via.placeholder.com/100/fff0ec/ee4d2d?text={initial}"
            categories_tiles.append({
                'name': cat.name,
                'slug': cat.slug,
                'image_url': thumb,
            })
        # Get featured banners for carousel
        banners = list(Banner.objects.filter(is_active=True, is_featured=True))
        # Flash sale products
        now = timezone.now()
        flash_qs = Product.objects.filter(
            is_active=True,
            flash_sale_price__isnull=False,
            flash_sale_start__lte=now,
            flash_sale_end__gte=now,
        ).exclude(flash_sale_price=0)
        flash_sale_products = list(flash_qs.order_by('flash_sale_end')[:20])
        flash_sale_ends_at = None
        if flash_sale_products:
            flash_sale_ends_at = min([p.flash_sale_end for p in flash_sale_products if p.flash_sale_end])
    except (OperationalError, ProgrammingError):
        messages.warning(
            request,
            "Cơ sở dữ liệu chưa được khởi tạo. Vui lòng chạy lệnh: python manage.py migrate rồi khởi động lại server."
        )
        categories_tiles = []
        banners = []

    context = {
        'products': products,
        'categories': categories,
        'categories_tiles': categories_tiles,
        'banners': banners,
        'flash_sale_products': flash_sale_products if 'flash_sale_products' in locals() else [],
        'flash_sale_ends_at': flash_sale_ends_at if 'flash_sale_ends_at' in locals() else None,
        'current_query': query,
        'current_category': category_slug,
    }
    return render(request, 'shop/home.html', context)


def product_detail_view(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    # Gợi ý sản phẩm cùng danh mục (nếu có)
    related = Product.objects.filter(is_active=True, category=product.category).exclude(id=product.id)[:8]
    context = {
        'product': product,
        'related_products': related,
    }
    return render(request, 'shop/product_detail.html', context)


def add_to_cart(request, product_id):
    if request.method != 'POST':
        return redirect('product_detail', slug=get_object_or_404(Product, id=product_id).slug)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    try:
        qty = int(request.POST.get('qty', '1'))
    except ValueError:
        qty = 1
    qty = max(1, min(qty, 999))

    # Handle out of stock
    if product.stock is not None and product.stock <= 0:
        messages.error(request, 'Sản phẩm hiện đã hết hàng.')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
        return redirect(next_url)

    cart = _get_cart(request.session)
    key = str(product.id)
    current = int(cart.get(key, 0))
    # Clamp by available stock
    max_allowed = int(product.stock) if product.stock is not None else 999
    new_qty = min(current + qty, max_allowed, 999)
    cart[key] = new_qty
    _save_cart(request.session, cart)
    if new_qty < current + qty:
        messages.warning(request, f'Số lượng đã được giới hạn theo tồn kho (tối đa {max_allowed}).')
    else:
        messages.success(request, f'Đã thêm {qty} sản phẩm vào giỏ hàng.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


def cart_view(request):
    cart = _get_cart(request.session)
    items = []
    total = Decimal('0')
    if cart:
        # Fetch products in one query
        ids = [int(i) for i in cart.keys()]
        products = {p.id: p for p in Product.objects.filter(id__in=ids)}
        for sid, qty in cart.items():
            pid = int(sid)
            p = products.get(pid)
            if not p:
                continue
            unit_price = _effective_price(p) or Decimal('0')
            subtotal = unit_price * int(qty)
            total += subtotal
            is_discounted = bool(getattr(p, 'is_in_flash_sale', False) and getattr(p, 'flash_sale_price', None))
            items.append({
                'product': p,
                'qty': int(qty),
                'unit_price': unit_price,
                'orig_price': p.price,
                'is_discounted': is_discounted,
                'subtotal': subtotal,
            })
    context = {
        'items': items,
        'total': total,
    }
    return render(request, 'shop/cart.html', context)


def update_cart(request, product_id):
    if request.method != 'POST':
        return redirect('cart_view')
    try:
        qty = int(request.POST.get('qty', '1'))
    except ValueError:
        qty = 1
    qty = max(0, min(qty, 999))
    cart = _get_cart(request.session)
    key = str(int(product_id))

    # Validate product and stock
    product = Product.objects.filter(id=product_id, is_active=True).first()
    if not product:
        cart.pop(key, None)
        _save_cart(request.session, cart)
        messages.warning(request, 'Sản phẩm không còn khả dụng và đã được loại khỏi giỏ hàng.')
        return redirect('cart_view')

    if qty <= 0:
        cart.pop(key, None)
        messages.info(request, 'Đã xóa sản phẩm khỏi giỏ hàng.')
    else:
        max_allowed = int(product.stock) if product.stock is not None else 999
        if product.stock is not None and product.stock <= 0:
            cart.pop(key, None)
            messages.error(request, 'Sản phẩm hiện đã hết hàng và đã được xóa khỏi giỏ.')
        else:
            if qty > max_allowed:
                qty = max_allowed
                messages.warning(request, f'Số lượng đã được điều chỉnh theo tồn kho (tối đa {max_allowed}).')
            cart[key] = qty
    _save_cart(request.session, cart)
    return redirect('cart_view')


def remove_from_cart(request, product_id):
    cart = _get_cart(request.session)
    cart.pop(str(int(product_id)), None)
    _save_cart(request.session, cart)
    return redirect('cart_view')


def clear_cart(request):
    _save_cart(request.session, {})
    return redirect('cart_view')


def logout_view(request):
    # Accept both GET and POST to be compatible with Django 5's default POST-only logout
    # and to fix 405 errors when users visit /accounts/logout/ directly.
    if request.method in ('GET', 'POST'):
        auth_logout(request)
        messages.info(request, 'Bạn đã đăng xuất.')
        return redirect('login')
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Đăng ký thành công!')
            return redirect('home')
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin.')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})
