from django.db import models
from django.conf import settings 
from django.contrib.auth.models import AbstractUser 
import uuid
# --- 1. نظام المستخدمين (للأدمن فقط) ---
class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    # أضفنا هذه الحقول لكي يتذكرها النظام في الطلبات القادمة
    address = models.TextField(blank=True, null=True) 
    location_link = models.URLField(max_length=500, null=True, blank=True)
    region = models.ForeignKey('Region', on_delete=models.SET_NULL, null=True, blank=True)

    groups = models.ManyToManyField('auth.Group', related_name='pages_custom_user_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='pages_custom_user_permissions', blank=True)
# --- 2. تصنيفات المنتجات ---
class Category(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self): return self.name 

# --- 3. المناطق وأسعار التوصيل ---
class Region(models.Model):
    name = models.CharField(max_length=100) # اسم المنطقة (مثلاً: طرابلس المركز، جنزور، تاجوراء)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2) # سعر التوصيل للمنطقة

    def __str__(self): 
        return f"{self.name} ({self.shipping_price} د.ل)"

# --- 4. المنتجات ---
class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/')
    stock = models.IntegerField(default=0)
    available = models.BooleanField(default=True)
    video_url = models.CharField(max_length=500, null=True, blank=True)
    stock = models.PositiveIntegerField(default=10, verbose_name="الكمية المتاحة")
    
    @property
    def is_available(self):
        return self.stock > 0
    
    def __str__(self): return self.name

# --- 5. سلة التسوق (تدعم الزوار عبر session_id) ---
class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=40, null=True, blank=True) 
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def get_total_price(self): 
        return self.product.price * self.quantity

# --- 6. الفاتورة الرئيسية (تخزن بيانات الزبون كاملة) ---
class OrderGroup(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'في الانتظار'),
        ('PROCESSING', 'قيد التجهيز'),
        ('DELIVERED', 'تم التسليم'),
        ('CANCELLED', 'ملغي')
    )
    # نربطه بالمستخدم فقط إذا كان أدمن أو مسجل، وإلا يترك فارغاً للزوار
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    # بيانات الزبون (المفتاح هنا هو رقم الهاتف للتعرف عليه مستقبلاً)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    address = models.TextField(null=True, blank=True) # وصف المكان
    location_link = models.URLField(max_length=500, null=True, blank=True) # رابط الموقع
    
    # ربط الطلب بالمنطقة لحساب التوصيل
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0) # لتثبيت السعر عند الطلب
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0) # إجمالي المنتجات + التوصيل
    
    payment_method = models.CharField(max_length=50, default='كاش')
    delivery_method = models.CharField(max_length=50, default='توصيل منزلي')
    cancellation_reason = models.TextField(null=True, blank=True, verbose_name="سبب الإلغاء")
    created_at = models.DateTimeField(auto_now_add=True)
    secure_token = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.secure_token:
            self.secure_token = uuid.uuid4().hex[:12] # إنشاء كود عشوائي من 12 حرف
        super().save(*args, **kwargs)
    def __str__(self): 
        return f"Order #{self.id} - {self.first_name} ({self.phone_number})"

# --- 7. تفاصيل المنتجات داخل الطلب ---
# --- 7. تفاصيل المنتجات داخل الطلب ---
class Order(models.Model):
    group = models.ForeignKey(OrderGroup, on_delete=models.CASCADE, related_name="orders")
    # هذا هو السطر الذي ينقصك لكي تظهر الصور
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)