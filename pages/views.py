import json
import uuid
import urllib.parse
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count, Sum
from django.contrib.auth import logout
from django.http import JsonResponse
from .models import OrderGroup, Order, CustomUser
# استيراد الموديلات
from .models import Product, Category, CartItem, Order, OrderGroup, CustomUser, Region

# --- 1. دوال الحساب والجلسة ---

def logout_view(request):
    """تسجيل الخروج ومسح بيانات الجلسة نهائياً"""
    logout(request)
    keys_to_clear = ['saved_phone', 'saved_f_name', 'saved_location', 'saved_address', 'saved_token']
    for key in keys_to_clear:
        if key in request.session:
            del request.session[key]
    request.session.modified = True
    return redirect('home')

# --- 2. الصفحات العامة ---

def home(request):
    return render(request, 'index.html')

def about_page(request):
    return render(request, 'about.html')

def terms_view(request):
    return render(request, 'terms.html')

def shop_page(request):
    products = Product.objects.filter(available=True)
    categories = Category.objects.all()
    cat = request.GET.get('category')
    if cat:
        products = products.filter(category_id=cat)
    q = request.GET.get('q')
    if q:
        products = products.filter(name__icontains=q)
    return render(request, 'shop.html', {'products': products, 'categories': categories})

# --- 3. نظام السلة ---

def get_cart_items(request):
    if request.user.is_authenticated:
        return CartItem.objects.filter(user=request.user)
    if not request.session.session_key:
        request.session.create()
    return CartItem.objects.filter(session_id=request.session.session_key)

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    items = get_cart_items(request)
    if request.user.is_authenticated:
        item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    else:
        item, created = CartItem.objects.get_or_create(session_id=request.session.session_key, product=product)
    if not created:
        item.quantity += 1
        item.save()
    messages.success(request, f"تمت إضافة {product.name} للسلة")
    return redirect('shop')

def update_cart(request, item_id):
    if request.method == 'POST':
        items = get_cart_items(request)
        cart_item = get_object_or_404(items, id=item_id)
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    return redirect('cart')

def remove_from_cart(request, item_id):
    items = get_cart_items(request)
    cart_item = get_object_or_404(items, id=item_id)
    cart_item.delete()
    messages.info(request, "تم حذف المنتج من السلة.")
    return redirect('cart')

def cart_page(request):
    items = get_cart_items(request)
    regions = Region.objects.all()
    total = sum(item.get_total_price for item in items)
    saved_data = {
        'f_name': request.session.get('saved_f_name', ''),
        'l_name': request.session.get('saved_l_name', ''),
        'phone': request.session.get('saved_phone', ''),
        'address': request.session.get('saved_address', ''),
        'location_link': request.session.get('saved_location', ''),
    }
    return render(request, 'cart.html', {'cart_items': items, 'total': total, 'saved_data': saved_data, 'regions': regions})

# --- 4. معالجة الطلبات ---

def place_order(request):
    if request.method == 'POST':
        f_name = request.POST.get('f_name')
        l_name = request.POST.get('l_name')
        phone = request.POST.get('phone_number')
        address = request.POST.get('location_url', '')
        region_id = request.POST.get('region_id')
        delivery_method = request.POST.get('delivery_method') 

        if not phone or not f_name:
            return JsonResponse({'success': False, 'message': 'يرجى ملء الاسم ورقم الهاتف'})

        cart_items = get_cart_items(request)
        if not cart_items.exists():
            return JsonResponse({'success': False, 'message': 'السلة فارغة'})

        subtotal = sum(item.get_total_price for item in cart_items)
        shipping_cost = 0
        region_obj = Region.objects.filter(id=region_id).first() if region_id else None
        if region_obj:
            shipping_cost = region_obj.shipping_price

        order_group = OrderGroup.objects.create(
            first_name=f_name, last_name=l_name, phone_number=phone,
            address=address, region=region_obj, shipping_cost=shipping_cost,
            total=subtotal + shipping_cost, status='PENDING'
        )

        for item in cart_items:
            Order.objects.create(
                group=order_group, product=item.product, product_name=item.product.name,
                price=item.product.price, quantity=item.quantity, total=item.get_total_price
            )

        cart_items.delete()

        # بناء الرابط السحري الكامل
        token = order_group.secure_token
        magic_link = request.build_absolute_uri(f"/myorder/?phone={phone}&token={token}&order_id={order_group.id}")

        # بناء رسالة الواتساب
        msg = f"✅ *تأكيد طلب جديد رقم #{order_group.id}*\n\n"
        msg += f"👤 *الاسم:* {f_name} {l_name}\n"
        msg += f"📞 *الهاتف:* {phone}\n"
        msg += f"🚚 *طريقة الاستلام:* {'توصيل للموقع' if delivery_method == 'delivery' else 'استلام من المتجر'}\n"
        if region_obj and delivery_method == 'delivery': msg += f"📍 *المنطقة:* {region_obj.name}\n"
        msg += f"💰 *الإجمالي:* {order_group.total} د.ل\n\n"
        msg += f"🔗 *رابط تتبع الطلب:* {magic_link}"

        store_phone = "218942950095" 
        whatsapp_url = f"https://wa.me/{store_phone}?text={urllib.parse.quote(msg)}"
        
        # حفظ البيانات في الجلسة
        request.session['saved_phone'] = phone
        request.session['saved_token'] = token
        request.session['saved_f_name'] = f_name
        request.session['whatsapp_url'] = whatsapp_url

        return JsonResponse({'success': True, 'order_id': order_group.id, 'whatsapp_url': whatsapp_url, 'order_url': magic_link})

    return JsonResponse({'success': False, 'message': 'طلب غير صالح'})

# --- 5. صفحات تتبع طلبات الزبون (النسخة الذكية) ---

def myorder_page(request):
    """عرض تتبع الطلب مع ميزة التوجيه التلقائي للرابط الكامل"""
    # 1. محاولة الحصول من الرابط (URL)
    phone_url = request.GET.get('phone')
    token_url = request.GET.get('token')
    order_id_url = request.GET.get('order_id')

    # 2. الحصول من الجلسة (Session)
    phone_session = request.session.get('saved_phone')
    token_session = request.session.get('saved_token')

    # --- ميزة التوجيه التلقائي (Fix URL) ---
    # إذا دخل برابط قصير /myorder/ وعنده جلسة، نحوله للرابط الطويل فوراً
    if not phone_url and phone_session and token_session:
        # نجلب ID آخر طلب لهذا الشخص
        last_order = OrderGroup.objects.filter(phone_number=phone_session, secure_token=token_session).order_by('-created_at').first()
        if last_order:
            full_url = f"/myorder/?phone={phone_session}&token={token_session}&order_id={last_order.id}"
            return redirect(full_url)

    # التحقق النهائي من وجود البيانات
    phone = phone_url or phone_session
    token = token_url or token_session

    if not (phone and token):
        return redirect('home')

    # جلب الطلب المحدد
    if order_id_url:
        order_group = OrderGroup.objects.filter(id=order_id_url, phone_number=phone, secure_token=token).first()
    else:
        order_group = OrderGroup.objects.filter(phone_number=phone, secure_token=token).order_by('-created_at').first()
    
    if not order_group:
        messages.error(request, "الطلب غير موجود.")
        return redirect('home')
    
    whatsapp_url = request.session.pop('whatsapp_url', None)

    return render(request, 'myorder.html', {'group': order_group, 'whatsapp_url': whatsapp_url})

def account_page(request):
    if request.user.is_authenticated and request.user.is_staff:
        return render(request, 'account.html', {'is_admin': True})
    phone = request.session.get('saved_phone')
    if not phone: return redirect('shop')
    orders = OrderGroup.objects.filter(phone_number=phone).order_by('-created_at')
    return render(request, 'account.html', {'is_admin': False, 'customer_name': request.session.get('saved_f_name', 'زبوننا'), 'order_groups': orders})

def edit_order_delivery(request, order_id):
    order = get_object_or_404(OrderGroup, id=order_id)
    if order.status == 'PENDING' and request.method == 'POST':
        order.phone_number = request.POST.get('new_phone_number')
        order.address = request.POST.get('new_location_link')
        order.save()
        request.session['saved_phone'] = order.phone_number
        messages.success(request, "تم تحديث البيانات.")
    # العودة للرابط الطويل لضمان عدم ضياعه
    return redirect(f"/myorder/?phone={order.phone_number}&token={order.secure_token}&order_id={order.id}")

def cancel_order(request, group_id):
    order_group = get_object_or_404(OrderGroup, id=group_id)

    if request.method == 'POST':
        if order_group.status == 'PENDING':

            reason = request.POST.get('cancellation_reason')
            if not reason:
                reason = "لم يتم ذكر سبب"

            order_group.status = 'CANCELLED'

            # نحمي الموقع من الخطأ لو الحقل مش موجود
            if hasattr(order_group, 'cancellation_reason'):
                order_group.cancellation_reason = reason

            order_group.save()

            messages.success(request, "تم إلغاء الطلب بنجاح.")
        else:
            messages.warning(request, "لا يمكن إلغاء هذا الطلب.")

    return redirect(f"/myorder/?phone={order_group.phone_number}&token={order_group.secure_token}&order_id={order_group.id}")

# --- 6. لوحة الإدارة ---

@staff_member_required
def admin_orders_view(request):
    orders = OrderGroup.objects.all().order_by('-created_at')
    return render(request, "admin_orders.html", {'orders': orders})

@staff_member_required
def order_detail_view(request, order_id):
    order_group = get_object_or_404(OrderGroup.objects.prefetch_related('orders'), id=order_id)
    return render(request, "order_details_modal.html", {'group': order_group})

@staff_member_required
def admin_change_order_status(request, group_id, new_status):
    order_group = get_object_or_404(OrderGroup, id=group_id)
    if request.method == 'POST':
        order_group.status = new_status
        reason = request.POST.get('cancellation_reason')
        if new_status == 'CANCELLED' and reason and hasattr(order_group, 'cancellation_reason'):
            order_group.cancellation_reason = reason
        order_group.save()
        messages.success(request, "تم تحديث الحالة.")
    return redirect('admin_orders')

@staff_member_required
def statistics_view(request):
    # 1. إحصائيات المبيعات والطلبات
    revenue = OrderGroup.objects.filter(status='DELIVERED').aggregate(Sum('total'))['total__sum'] or 0
    orders_count = OrderGroup.objects.count()
    
    # 2. حساب عدد الزيارات (باستخدام Session البسيط)
    # ملاحظة: هذا يحسب الزيارات النشطة حالياً في النظام
    visits_count = request.session.get('total_visits', 100) # استبدل الـ 100 بمتغير حقيقي إذا كان لديك موديل للزيارات

    # 3. حالات الطلب والبيانات للرسم البياني
    status_counts_raw = OrderGroup.objects.values('status').annotate(total=Count('id'))
    s_map = {'PENDING': 'انتظار', 'PROCESSING': 'تجهيز', 'DELIVERED': 'تم التسليم', 'CANCELLED': 'ملغي'}
    
    # تأكد أن الترتيب هنا يتوافق مع ترتيب الألوان في الجافاسكريبت
    chart_data = {
        'انتظار': OrderGroup.objects.filter(status='PENDING').count(),
        'تجهيز': OrderGroup.objects.filter(status='PROCESSING').count(),
        'تم التسليم': OrderGroup.objects.filter(status='DELIVERED').count(),
        'ملغي': OrderGroup.objects.filter(status='CANCELLED').count(),
    }

    # 4. أفضل 10 منتجات مبيعاً
    top_products = Order.objects.values('product_name').annotate(total_sales=Count('id')).order_by('-total_sales')[:10]
    product_names = [p['product_name'] for p in top_products]
    product_sales = [p['total_sales'] for p in top_products]

    # 5. سجل الطلبات الملغاة (الجدول المفقود)
    cancelled_orders = OrderGroup.objects.filter(status='CANCELLED').order_by('-created_at')[:5]

    return render(request, "statistics.html", {
        'total_revenue': revenue,
        'total_orders': orders_count,
        'visits_count': visits_count, # عدد الزوار
        'cancelled_orders': cancelled_orders,
        'status_counts': json.dumps(chart_data, ensure_ascii=False),
        'product_names_for_chart': json.dumps(product_names, ensure_ascii=False),
        'product_sales_for_chart': json.dumps(product_sales),
    })