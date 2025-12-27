from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from decimal import Decimal
import json
import logging
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.conf import settings
from django.urls import reverse
import urllib.request
import urllib.error

from .forms import RegisterForm, CheckoutForm
from .models import Product, Category, Banner, Order, OrderItem


# --------- AI Chatbot API (Gemini proxy) ---------
logger = logging.getLogger(__name__)


def _build_shop_context(query: str, limit: int = 8) -> str:
    """Build a short context from Product/Category data relevant to the query."""
    try:
        q = Q(name__icontains=query) | Q(description__icontains=query) | Q(specifications__icontains=query)
        products = list(Product.objects.filter(is_active=True).filter(q)[:limit])
        cats = list(Category.objects.filter(Q(name__icontains=query))[:5])
    except Exception:
        products, cats = [], []
    lines = []
    if cats:
        lines.append("Các danh mục khớp:")
        for c in cats:
            lines.append(f"- Danh mục: {c.name}")
    if products:
        lines.append("Sản phẩm liên quan:")
        for p in products:
            price = getattr(p, 'price', None)
            flash = getattr(p, 'flash_sale_price', None)
            price_text = f"{price}đ"
            if flash:
                price_text += f" (Flash Sale: {flash}đ)"
            lines.append(f"- {p.name} | Giá: {price_text} | Tồn kho: {p.stock} | Màu: {', '.join(p.color_list) if p.color_list else 'N/A'}")
            if p.description:
                lines.append(f"  Mô tả: {p.description[:180]}{'...' if len(p.description) > 180 else ''}")
    if not lines:
        lines.append("Không tìm thấy dữ liệu nội bộ phù hợp với truy vấn.")
    return "\n".join(lines)


def _call_gemini(prompt: str) -> str:
    """Call Gemini API via REST using the API key from settings and return the text response."""
    api_key = ""
    if not api_key:
        return "Chưa cấu hình GEMINI_API_KEY trên server. Vui lòng thiết lập biến môi trường GEMINI_API_KEY."
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=" + api_key
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode('utf-8')
            obj = json.loads(body)
            # Extract text safely
            text = (
                obj.get('candidates', [{}])[0]
                .get('content', {})
                .get('parts', [{}])[0]
                .get('text', '')
            )
            return text or "(Không nhận được nội dung từ mô hình)"
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8')
        except Exception:
            err_body = str(e)
        logger.exception("Gemini HTTPError: %s", err_body)
        return f"Lỗi khi gọi Gemini: {e.code}. Chi tiết: {err_body}"
    except Exception as e:
        logger.exception("Gemini error")
        return f"Đã xảy ra lỗi khi gọi Gemini: {e}"


@require_POST
@ensure_csrf_cookie
def chat_api(request):
    """Simple JSON endpoint: {message: str, history?: [{role, content}]} -> {reply}.
    Automatically builds internal shop context and adds instructions to answer accurately.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    message = (data.get('message') or '').strip()
    history = data.get('history') or []
    if not message:
        return HttpResponseBadRequest("Missing 'message'")

    context_text = _build_shop_context(message)

    system_instructions = (
        "Bạn là trợ lý mua sắm cho website. Trả lời ngắn gọn, chính xác, ưu tiên dữ liệu nội bộ "
        "(sản phẩm, giá, tồn kho, flash sale). Nếu không chắc, hãy nói bạn không có thông tin. "
        "Luôn trả lời bằng tiếng Việt."
    )

    # Build a consolidated prompt including brief history
    hist_lines = []
    for turn in history[-6:]:  # last 6 turns for brevity
        role = turn.get('role', 'user')
        content = (turn.get('content') or '').strip()
        if content:
            hist_lines.append(f"[{role}] {content}")
    history_text = "\n".join(hist_lines)

    prompt = (
        f"Hướng dẫn: {system_instructions}\n\n"
        f"Ngữ cảnh nội bộ (có thể trích dẫn trong câu trả lời):\n{context_text}\n\n"
        f"Lịch sử hội thoại (rút gọn):\n{history_text}\n\n"
        f"Câu hỏi hiện tại của khách: {message}\n"
    )

    reply = _call_gemini(prompt)

    return JsonResponse({"reply": reply})


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


def checkout_view(request):
    cart = _get_cart(request.session)
    if not cart:
        messages.info(request, 'Giỏ hàng của bạn đang trống.')
        return redirect('cart_view')

    # Build items and total similar to cart_view
    items = []
    total = Decimal('0')
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
        items.append({
            'product': p,
            'qty': int(qty),
            'unit_price': unit_price,
            'subtotal': subtotal,
        })

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.total_amount = total
            order.status = 'new'
            order.save()
            # Save items
            for it in items:
                OrderItem.objects.create(
                    order=order,
                    product=it['product'],
                    product_name=it['product'].name,
                    quantity=it['qty'],
                    unit_price=it['unit_price'],
                    line_total=it['subtotal'],
                )
            # Clear cart
            _save_cart(request.session, {})
            messages.success(request, f'Đặt hàng thành công! Mã đơn hàng của bạn là #{order.id}.')
            return redirect('home')
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin thanh toán.')
    else:
        initial = {}
        if request.user.is_authenticated:
            initial['customer_name'] = (getattr(request.user, 'get_full_name', lambda: '')() or request.user.username)
        form = CheckoutForm(initial=initial)

    context = {
        'form': form,
        'items': items,
        'total': total,
    }
    return render(request, 'shop/checkout.html', context)


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
