from django import forms
from .models import CustomUser 
from django.contrib.auth.forms import UserCreationForm, UserChangeForm 
class CustomUserCreationForm(UserCreationForm):

    phone_number = forms.CharField(
        max_length=15, 
        required=False,
        label='رقم الهاتف'
    )
    
    

    class Meta(UserCreationForm.Meta):
       
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email', 'phone_number',)
       
class CustomUserChangeForm(UserChangeForm):
   
    class Meta:
        model = CustomUser
        fields = UserChangeForm.Meta.fields
        
        
        
class CustomUserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
      
        fields = ('first_name', 'last_name', 'phone_number')

    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = "الاسم الأول"
        self.fields['last_name'].label = "اسم العائلة"
        self.fields['phone_number'].label = "رقم الهاتف"
    
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})