from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Banner

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'image_preview', 'created_at')
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ('name',)
    fields = ('name', 'slug', 'image_url')

    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="height:32px;width:32px;object-fit:cover;border-radius:4px;"/>', obj.image_url)
        return '(no image)'
    image_preview.short_description = 'Ảnh'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'flash_sale_price', 'stock', 'is_active', 'created_at')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'description', 'color_options', 'specifications')
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'slug', 'category', 'price', 'is_active')
        }),
        ('Flash Sale', {
            'fields': ('flash_sale_price', 'flash_sale_start', 'flash_sale_end', 'flash_sale_stock')
        }),
        ('Hình ảnh & Kho', {
            'fields': ('image_url', 'stock')
        }),
        ('Mô tả & Thuộc tính', {
            'fields': ('description', 'color_options', 'specifications')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'image_preview', 'is_featured', 'discount_info', 'is_active', 'order', 'created_at')
    list_filter = ('is_featured', 'is_active')
    search_fields = ('title', 'discount_info')
    fields = ('title', 'image_url', 'link', 'is_featured', 'discount_info', 'is_active', 'order')

    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="height:64px;width:120px;object-fit:cover;border-radius:4px;"/>', obj.image_url)
        return '(no image)'
    image_preview.short_description = 'Ảnh banner'
