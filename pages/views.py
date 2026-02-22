import json
import urllib.parse
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count, Sum
from django.contrib.auth import logout
from django.http import JsonResponse

# استيراد كافة الموديلات المطلوبة
from .models import Product, Category, CartItem, Order, OrderGroup, CustomUser, Region, Visit

# --- 1. إدارة الحساب والجلسة ---

def logout_view(request):
    """تسجيل الخروج وتنظيف الجلسة"""
    logout(request)
    for key in ['saved_phone', 'saved_f_name', 'saved_location', 'saved_address', 'saved_token']:
        request.session.pop(key, None)
    request.session.modified = True
    return redirect('home')

def account_page(request):
    """صفحة حساب الزبون أو لوحة تحكم سريعة"""
    if request.user.is_authenticated and request.user.is_staff:
        return render(request, 'account.html', {'is_admin': True})
    
    phone = request.session.get('saved_phone')
    if not phone: 
        return redirect('shop')
        
    orders = OrderGroup.objects.filter(phone_number=phone).order_by('-created_at')
    context = {
        'is_admin': False, 
        'customer_name': request.session.get('saved_f_name', 'زبوننا'), 
        'order_groups': orders
    }
    return render(request, 'account.html', context)

# --- 2. الصفحات العامة ---

def home(request):
    # حساب الزيارة مرة واحدة فقط لكل متصفح/جلسة
    if not request.session.get('has_visited'):
        Visit.objects.create(ip_address=request.META.get('REMOTE_ADDR'))
        request.session['has_visited'] = True
    
    return render(request, 'index.html')

def about_page(request):
    return render(request, 'about.html')

def terms_view(request):
    return render(request, 'terms.html')

def shop_page(request):
    products = Product.objects.filter(available=True)
    categories = Category.objects.all()
    
    # الفلترة حسب الفئة والبحث
    cat = request.GET.get('category')
    if cat: products = products.filter(category_id=cat)
    
    q = request.GET.get('q')
    if q: products = products.filter(name__icontains=q)
    
    return render(request, 'shop.html', {'products': products, 'categories': categories})

# --- 3. نظام السلة الذكي ---

def get_cart_items(request):
    """جلب عناصر السلة للمستخدم المسجل أو الزائر برقم الجلسة"""
    if request.user.is_authenticated:
        return CartItem.objects.filter(user=request.user)
    if not request.session.session_key:
        request.session.create()
    return CartItem.objects.filter(session_id=request.session.session_key)

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    else:
        if not request.session.session_key: request.session.create()
        item, created = CartItem.objects.get_or_create(session_id=request.session.session_key, product=product)
    
    if not created:
        item.quantity += 1
        item.save()
    messages.success(request, f"تمت إضافة {product.name} للسلة")
    return redirect('shop')

def update_cart(request, item_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(get_cart_items(request), id=item_id)
        qty = int(request.POST.get('quantity', 1))
        if qty > 0:
            cart_item.quantity = qty
            cart_item.save()
        else:
            cart_item.delete()
    return redirect('cart')

def remove_from_cart(request, item_id):
    if request.method == 'POST':
        CartItem.objects.filter(id=item_id).delete()
        messages.success(request, "تم حذف المنتج")
    return redirect('cart')

def cart_page(request):
    # 1. جلب عناصر السلة
    items = get_cart_items(request)
    
    # 2. جلب المناطق (مهم جداً لنافذة التوصيل)
    regions = Region.objects.all()
    
    # 3. حساب الإجمالي
    total = sum(item.get_total_price for item in items)
    
    # 4. البيانات المحفوظة من جلسة سابقة (للتعبئة التلقائية)
    saved_data = {
        'f_name': request.session.get('saved_f_name', ''),
        'l_name': request.session.get('saved_l_name', ''),
        'phone': request.session.get('saved_phone', ''),
    }

    # 5. جلب 3 منتجات عشوائية (ميزة "قد تعجبك")
    suggested_products = Product.objects.filter(available=True).order_by('?')[:3]

    # 6. إرسال كل شيء للقالب
    return render(request, 'cart.html', {
        'cart_items': items, 
        'total': total, 
        'saved_data': saved_data, 
        'regions': regions,
        'suggested_products': suggested_products 
    })
    

# --- 4. معالجة الطلبات والحسابات المالية ---
def place_order(request):
    if request.method == 'POST':
        # 1. استقبال البيانات الأساسية
        f_name = request.POST.get('f_name')
        l_name = request.POST.get('l_name')
        phone = request.POST.get('phone_number')
        address = request.POST.get('location_url', '') # الوصف أو الرابط
        region_id = request.POST.get('region_id')
        delivery_method = request.POST.get('delivery_method')
        pay_method = request.POST.get('payment_method')
        
        # 2. جلب العناصر المختارة من السلة
        selected_items_str = request.POST.get('selected_items', '')
        selected_items_ids = [i for i in selected_items_str.split(',') if i]
        
        selected_items = get_cart_items(request).filter(id__in=selected_items_ids)

        if not selected_items.exists():
            return JsonResponse({'success': False, 'message': 'السلة فارغة أو لم يتم اختيار منتجات'})

        if not phone or not f_name:
            return JsonResponse({'success': False, 'message': 'يرجى ملء الاسم ورقم الهاتف'})

        # 3. الحسابات المالية (صافي المنتجات + التوصيل)
        subtotal = sum(item.get_total_price for item in selected_items)
        shipping_cost = 0
        region_obj = Region.objects.filter(id=region_id).first() if region_id else None
        
        if region_obj and delivery_method == 'delivery':
            shipping_cost = region_obj.shipping_price
        else:
            # إذا كان استلام من المحل، نفرغ العنوان والمنطقة لضمان نظافة البيانات
            address = ""
            region_obj = None

        # 4. إنشاء مجموعة الطلب (OrderGroup)
        order_group = OrderGroup.objects.create(
            first_name=f_name, 
            last_name=l_name, 
            phone_number=phone,
            address=address, 
            region=region_obj, 
            shipping_cost=shipping_cost,
            total=Decimal(subtotal) + Decimal(shipping_cost), 
            payment_method=pay_method,
            status='PENDING'
        )

        # 5. نقل المنتجات من السلة إلى تفاصيل الطلب
        for item in selected_items:
            Order.objects.create(
                group=order_group, 
                product=item.product, 
                product_name=item.product.name,
                price=item.product.price, 
                quantity=item.quantity, 
                total=item.get_total_price
            )
        
        # 6. حذف العناصر التي تم طلبها من السلة
        selected_items.delete()

        # 7. تجهيز روابط التتبع
        token = order_group.secure_token
        magic_link = request.build_absolute_uri(f"/myorder/?phone={phone}&token={token}&order_id={order_group.id}")
        
        # 8. بناء رسالة الواتساب الديناميكية
        delivery_text = "توصيل للموقع 🚚" if delivery_method == 'delivery' else "من المحل 🏪"
        
        msg = (
            f"📦 *تأكيد طلب جديد رقم #{order_group.id}*\n\n"
            f"👤 *الاسم:* {f_name} {l_name}\n"
            f"📞 *الهاتف:* {phone}\n"
            f"🚚 *طريقة الاستلام:* {delivery_text}\n"
        )

        # إضافة المنطقة والعنوان فقط إذا كان الخيار "توصيل"
        if delivery_method == 'delivery':
            reg_name = order_group.region.name if order_group.region else "غير محدد"
            msg += f"📍 *المنطقة:* {reg_name}\n"
            msg += f"🏠 *العنوان:* {address}\n"

        # إضافة الإجمالي والرابط في نهاية الرسالة
        msg += (
            f"\n💰 *الإجمالي:* {int(order_group.total)} د.ل\n"
            f"🔗 *رابط تتبع الطلب:* {magic_link}"
        )
        
        # تشفير الرسالة للرابط
        whatsapp_url = f"https://wa.me/218942950095?text={urllib.parse.quote(msg)}"

        # 9. حفظ البيانات في الجلسة لسهولة التعرف على الزبون
        request.session.update({
            'saved_phone': phone, 
            'saved_token': token, 
            'saved_f_name': f_name
        })

        return JsonResponse({
            'success': True, 
            'order_id': order_group.id, 
            'whatsapp_url': whatsapp_url, 
            'order_url': magic_link
        })

    return JsonResponse({'success': False, 'message': 'طلب غير صالح'})

def myorder_page(request):
    """صفحة تتبع الطلب - تم إصلاح خطأ subtotal عبر إرسال items_total"""
    phone = request.GET.get('phone') or request.session.get('saved_phone')
    token = request.GET.get('token') or request.session.get('saved_token')
    order_id = request.GET.get('order_id')

    if not (phone and token): return redirect('home')

    order_group = OrderGroup.objects.filter(phone_number=phone, secure_token=token)
    group = order_group.filter(id=order_id).first() if order_id else order_group.order_by('-created_at').first()
    
    if not group: return redirect('home')
    
    return render(request, 'myorder.html', {
        'group': group, 
        'items_total': group.total - group.shipping_cost, # حل مشكلة VariableDoesNotExist
        'regions': Region.objects.all()
    })

# --- 5. تعديل وإلغاء الطلب من قبل الزبون ---

def edit_order_delivery(request, order_id):
    if request.method == 'POST':
        group = get_object_or_404(OrderGroup, id=order_id)
        if group.status != 'PENDING': return redirect('home')

        # إعادة الحساب بناءً على التعديل الجديد
        items_subtotal = group.orders.aggregate(Sum('total'))['total__sum'] or 0
        delivery_method = request.POST.get('delivery_method')
        region_id = request.POST.get('region_id')

        if delivery_method == 'delivery' and region_id:
            region = get_object_or_404(Region, id=region_id)
            group.region, group.shipping_cost = region, region.shipping_price
            group.address = request.POST.get('location_url')
            group.total = Decimal(items_subtotal) + Decimal(region.shipping_price)
        else:
            group.region, group.shipping_cost, group.address = None, 0, ""
            group.total = items_subtotal

        group.phone_number = request.POST.get('phone_number')
        group.save()
        messages.success(request, "تم تحديث البيانات بنجاح")
        return redirect(f"/myorder/?phone={group.phone_number}&token={group.secure_token}&order_id={group.id}")

def cancel_order(request, group_id):
    group = get_object_or_404(OrderGroup, id=group_id)
    if request.method == 'POST' and group.status == 'PENDING':
        group.status = 'CANCELLED'
        
        # استلام السبب المكتوب من الزبون
        reason = request.POST.get('cancellation_reason', '').strip()
        if reason:
            group.cancellation_reason = f"الزبون: {reason}"
        else:
            group.cancellation_reason = "الزبون: لم يذكر سبب"
            
        group.save()
        messages.success(request, "تم إلغاء الطلب.")
    return redirect(f"/myorder/?phone={group.phone_number}&token={group.secure_token}&order_id={group.id}")

@staff_member_required
def admin_change_order_status(request, group_id, new_status):
    group = get_object_or_404(OrderGroup, id=group_id)
    if request.method == 'POST':
        group.status = new_status
        
        if new_status == 'CANCELLED':
            # استلام السبب المكتوب من الإدارة
            reason = request.POST.get('cancellation_reason', '').strip()
            if reason:
                group.cancellation_reason = f"الإدارة: {reason}"
            else:
                group.cancellation_reason = "الإدارة: لم يذكر سبب"
                
        group.save()
        messages.success(request, f"تم تغيير الحالة إلى {group.get_status_display()}")
    return redirect('admin_orders')

@staff_member_required
def order_detail_view(request, order_id):
    group = get_object_or_404(OrderGroup.objects.prefetch_related('orders'), id=order_id)
    return render(request, "order_details_modal.html", {'group': group})

@staff_member_required
def admin_change_order_status(request, group_id, new_status):
    group = get_object_or_404(OrderGroup, id=group_id)
    if request.method == 'POST':
        group.status = new_status
        # السطر الجديد: إذا اخترت "ملغي" من الإدارة، سجل السبب
        if new_status == 'CANCELLED':
            group.cancellation_reason = 'إلغاء من قبل الإدارة'
        
        group.save()
        messages.success(request, f"تم تغيير الحالة إلى {group.get_status_display()}")
    return redirect('admin_orders')

@staff_member_required
def statistics_view(request):
    revenue = OrderGroup.objects.filter(status='DELIVERED').aggregate(Sum('total'))['total__sum'] or 0
    top_products = Order.objects.values('product_name').annotate(total_sales=Sum('quantity')).order_by('-total_sales')[:5]
    
    # 1. تجهيز بيانات المنتجات للرسم البياني
    p_names = [p['product_name'] for p in top_products]
    p_sales = [p['total_sales'] for p in top_products]

    # 2. تجهيز بيانات الطلبات الملغاة (العدد الكلي وآخر 5 طلبات)
    total_cancelled = OrderGroup.objects.filter(status='CANCELLED').count()
    cancelled_orders = OrderGroup.objects.filter(status='CANCELLED').order_by('-created_at')[:5]
    
    status_counts = {
        'انتظار': OrderGroup.objects.filter(status='PENDING').count(),
        'تجهيز': OrderGroup.objects.filter(status='PROCESSING').count(),
        'تم التسليم': OrderGroup.objects.filter(status='DELIVERED').count(),
        'ملغي': total_cancelled,
    }
    
    context = {
        'total_revenue': revenue,
        'total_orders': OrderGroup.objects.count(),
        'visits_count': Visit.objects.count(),
        
        # تحويل البيانات إلى JSON لتعمل الرسوم البيانية بدون أخطاء
        'status_counts': json.dumps(status_counts),
        'product_names_for_chart': json.dumps(p_names),
        'product_sales_for_chart': json.dumps(p_sales),
        
        # إرسال بيانات الطلبات الملغاة للجدول
        'total_cancelled_all': total_cancelled,
        'cancelled_orders': cancelled_orders,
        'top_products': top_products
    }
    return render(request, 'statistics.html', context)