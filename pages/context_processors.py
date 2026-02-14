from .models import CartItem

def cart_count(request):
    if request.user.is_authenticated:
        # حساب العدد للمستخدم المسجل
        count = CartItem.objects.filter(user=request.user).count()
    elif request.session.session_key:
        # حساب العدد للزائر (باستخدام مفتاح الجلسة)
        count = CartItem.objects.filter(session_id=request.session.session_key).count()
    else:
        count = 0
    return {'cart_count': count}