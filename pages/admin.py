from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Category, Product, CartItem, OrderGroup, Order, Region

# 1. إعداد كلاس مخصص لإدارة CustomUser في لوحة الإدارة
class CustomUserAdmin(UserAdmin):
    # تعيين حقول العرض (لتظهر في قائمة المستخدمين)
    list_display = ('email', 'username', 'first_name', 'last_name', 'phone_number', 'is_staff')
    
    # حقول البحث
    search_fields = ('email', 'username', 'phone_number')

    # إضافة حقل رقم الهاتف إلى صفحة التعديل
    fieldsets = UserAdmin.fieldsets + (
        ('معلومات الاتصال المخصصة', {'fields': ('phone_number',)}),
    )
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'shipping_price') # يظهر الاسم والسعر في الجدول
    search_fields = ('name',) # يضيف خانة بحث عن المنطقة

admin.site.register(Region, RegionAdmin)

# 2. تسجيل نموذج المستخدم المخصص
admin.site.register(CustomUser, CustomUserAdmin) 


# 3. تسجيل بقية النماذج لظهورها في لوحة الإدارة (مرة واحدة فقط)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(CartItem)
admin.site.register(OrderGroup)
admin.site.register(Order)