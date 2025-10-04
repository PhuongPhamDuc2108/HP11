# Dự án Django: Marketplace lấy cảm hứng từ Shopee

Lưu ý: Đây là dự án demo học tập, không sao chép giao diện, logo hoặc tài sản trí tuệ của Shopee. Giao diện chỉ lấy cảm hứng và được xây dựng bằng Bootstrap.

## Tính năng đã có
- Trang chủ hiển thị danh sách sản phẩm (lưới card), tìm kiếm theo tên/mô tả, lọc theo danh mục.
- Đăng ký, đăng nhập, đăng xuất người dùng (sử dụng Django Auth).
- Khu vực Admin để thêm/sửa/xóa danh mục và sản phẩm.
- Template HTML + CSS + Bootstrap.

## Yêu cầu hệ thống
- Python 3.10+
- Pip

## Cài đặt và chạy
1. Tạo venv (khuyến nghị):
   - Windows PowerShell: `python -m venv .venv && .venv\Scripts\Activate.ps1`
2. Cài đặt phụ thuộc:
   - `pip install -r requirements.txt`
3. Tạo cấu trúc DB và tài khoản admin:
   - `python manage.py migrate`
   - `python manage.py createsuperuser`
4. Chạy server:
   - `python manage.py runserver`
5. Mở trình duyệt:
   - Trang chủ: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

## Quản trị sản phẩm
- Vào trang Admin, tạo vài Danh mục, sau đó thêm Sản phẩm (có thể dùng trường `image_url` để dán URL ảnh sản phẩm minh họa).

## Cấu trúc chính
- manage.py
- ecommerce/
  - settings.py, urls.py, asgi.py, wsgi.py
- shop/
  - models.py (Category, Product)
  - admin.py (đăng ký models vào Admin)
  - views.py (home, register)
  - urls.py (route trang chủ)
  - forms.py (RegisterForm)
- templates/
  - base.html (navbar, search, auth links)
  - shop/home.html (lưới sản phẩm)
  - registration/login.html, registration/register.html
- static/css/styles.css (một số tùy chỉnh màu sắc, card, v.v.)

## Ghi chú
- Dự án dùng SQLite mặc định (db.sqlite3). Không cần cấu hình thêm khi chạy local.
- Mặc định các nút màu cam/đỏ lấy cảm hứng từ màu sắc thương mại điện tử phổ biến, không dùng logo hoặc nội dung bản quyền.


## Khắc phục sự cố
- Lỗi: OperationalError: no such table: shop_category khi mở trang chủ.
  - Nguyên nhân: Chưa chạy migrate để tạo bảng cơ sở dữ liệu.
  - Cách khắc phục:
    1) python manage.py migrate
    2) (Tuỳ chọn) python manage.py createsuperuser
    3) Khởi động lại server: python manage.py runserver
