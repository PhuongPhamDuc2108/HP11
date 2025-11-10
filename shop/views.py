from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .forms import RegisterForm
from .models import Product, Category, Banner


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
