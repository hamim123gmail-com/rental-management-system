from django.forms import ModelForm
from django import forms
from django.contrib.auth.models import User
from .models import Tenant, Owner, Building, Rental, Utility, Payment, Maintenance

class TenantForm(ModelForm):
    username = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Leave blank to use tenant name as username'}),
        help_text="Login username for the tenant (Default: first name)."
    )
    password = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank for default: [lastname]1234'}),
        help_text="Login password for the tenant portal (Default: last name + 1234)."
    )

    class Meta:
        model = Tenant
        fields = ['first_name', 'last_name', 'contact', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        linked_user = getattr(self.instance, 'user', None)
        if self.instance and self.instance.pk and linked_user:
            self.fields['username'].initial = linked_user.username
            self.fields['username'].help_text = "Linked login username for tenant."
            self.fields['password'].help_text = "Leave blank to keep existing password."

    def save(self, commit=True):
        tenant = super().save(commit=False)
        raw_username = self.cleaned_data.get('username')
        pwd = self.cleaned_data.get('password')

        # Compute default credentials: name (first_name) and last_name + 1234
        name_clean = (tenant.first_name or '').strip().lower().replace(' ', '')
        default_username = name_clean or (tenant.email or 'tenant').split('@')[0].lower()

        last_name_clean = (tenant.last_name or '').strip().lower().replace(' ', '')
        default_pwd = f"{last_name_clean}1234" if last_name_clean else "tenant1234"

        # If tenant doesn't have an associated User account, create one
        if not tenant.user:
            uname = (raw_username.strip().lower() if raw_username else default_username)
            base_uname = uname
            counter = 1
            while User.objects.filter(username=uname).exists():
                uname = f"{base_uname}{counter}"
                counter += 1

            login_pwd = pwd.strip() if pwd else default_pwd
            user = User.objects.create_user(
                username=uname,
                email=tenant.email,
                password=login_pwd,
                first_name=tenant.first_name,
                last_name=tenant.last_name,
                is_staff=False,
                is_superuser=False
            )
            tenant.user = user
            tenant._login_password = login_pwd
        else:
            # Sync user details if tenant already has user
            user = tenant.user
            if raw_username and raw_username.strip() != user.username:
                new_uname = raw_username.strip()
                if not User.objects.filter(username=new_uname).exclude(id=user.id).exists():
                    user.username = new_uname
            if pwd:
                user.set_password(pwd.strip())
                tenant._login_password = pwd.strip()
            user.first_name = tenant.first_name
            user.last_name = tenant.last_name
            user.email = tenant.email
            user.save()

        if commit:
            tenant.save()
        return tenant

class TenantCredentialsUpdateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    contact = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone contact'})
    )
    new_password = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep current password'}),
        help_text="Only enter if you wish to change your password (min 6 characters)."
    )
    confirm_password = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )

    def __init__(self, *args, user=None, tenant=None, **kwargs):
        self.user = user
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        if user and not self.is_bound:
            self.fields['username'].initial = user.username
            self.fields['email'].initial = user.email or (tenant.email if tenant else '')
        if tenant and not self.is_bound:
            self.fields['contact'].initial = tenant.contact

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if self.user and User.objects.filter(username=username).exclude(id=self.user.id).exists():
            raise forms.ValidationError("This username is already taken. Please choose another.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        new_pwd = cleaned_data.get('new_password')
        confirm_pwd = cleaned_data.get('confirm_password')
        if new_pwd:
            if new_pwd != confirm_pwd:
                raise forms.ValidationError("New passwords do not match. Please re-enter.")
            if len(new_pwd) < 6:
                raise forms.ValidationError("New password must be at least 6 characters long.")
        return cleaned_data

class OwnerForm(ModelForm):
    class Meta:
        model = Owner
        fields = '__all__'

class BuildingForm(ModelForm):
    class Meta:
        model = Building
        fields = '__all__'

class RentalForm(ModelForm):
    class Meta:
        model = Rental
        fields = ['building', 'type', 'rent_amount', 'tenant', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {
            'tenant': 'Optional: Leave blank to create as a Vacant Rental available for future assignment.',
        }

class AssignTenantForm(forms.Form):
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.all(),
        empty_label="-- Select Tenant --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

class UtilityForm(ModelForm):
    class Meta:
        model = Utility
        fields = '__all__'

class PaymentForm(ModelForm):
    class Meta:
        model = Payment
        fields = '__all__' 
        widgets = {
            'payment_date':forms.DateInput(attrs={'type':'date'}),}   

class MaintenanceForm(ModelForm):
    class Meta:
        model = Maintenance
        fields = ['rental', 'description', 'cost', 'status', 'maintenance_date']
        widgets = {
            'maintenance_date':forms.DateInput(attrs={'type':'date'}),
        }

class TenantMaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your issue in detail (e.g. Water leak in bathroom, AC not cooling, broken door lock)...'
            }),
        }
        labels = {
            'description': 'Issue Description'
        }