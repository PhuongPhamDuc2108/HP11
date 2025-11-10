from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image_url = models.URLField(blank=True, help_text='URL ảnh đại diện cho danh mục (tùy chọn)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = 'Danh mục'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    image_url = models.URLField(blank=True, help_text='Dán URL ảnh sản phẩm (có thể lấy từ internet)')
    stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    color_options = models.CharField(max_length=200, blank=True, help_text='Danh sách màu sắc (ngăn cách bởi dấu phẩy, ví dụ: Đỏ, Xanh, Đen)')
    specifications = models.TextField(blank=True, help_text='Các thông số kỹ thuật (mỗi dòng một mục, hoặc dán dạng văn bản)')
    # Flash sale fields
    flash_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Giá Flash Sale (để trống nếu không tham gia)')
    flash_sale_start = models.DateTimeField(null=True, blank=True, help_text='Thời gian bắt đầu Flash Sale')
    flash_sale_end = models.DateTimeField(null=True, blank=True, help_text='Thời gian kết thúc Flash Sale')
    flash_sale_stock = models.PositiveIntegerField(default=0, help_text='Số lượng dành cho Flash Sale (0 = không giới hạn riêng)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def color_list(self):
        """Return a cleaned list of colors from color_options (comma separated)."""
        if not self.color_options:
            return []
        return [s.strip() for s in self.color_options.split(',') if s.strip()]

    @property
    def is_in_flash_sale(self):
        from django.utils import timezone
        if not self.flash_sale_price or not self.flash_sale_start or not self.flash_sale_end:
            return False
        now = timezone.now()
        if not (self.flash_sale_start <= now <= self.flash_sale_end):
            return False
        # If flash_sale_stock > 0, require there is stock
        if self.flash_sale_stock and self.flash_sale_stock > 0:
            return self.stock > 0
        # flash_sale_stock == 0 (default) means no separate limit
        return True

    @property
    def flash_discount_percent(self):
        try:
            if self.flash_sale_price and self.price and self.price > 0:
                return max(0, int(round((1 - float(self.flash_sale_price) / float(self.price)) * 100)))
        except Exception:
            return 0
        return 0

    def __str__(self):
        return self.name

class Banner(models.Model):
    title = models.CharField(max_length=200, help_text='Tiêu đề banner')
    image_url = models.URLField(help_text='URL ảnh banner')
    link = models.URLField(blank=True, help_text='Link khi click vào banner (tùy chọn)')
    is_featured = models.BooleanField(default=False, help_text='Banner nổi bật (hiển thị trên carousel)')
    discount_info = models.CharField(max_length=100, blank=True, help_text='Thông tin giảm giá (ví dụ: Giảm 50%)')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Thứ tự hiển thị')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banner'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title
