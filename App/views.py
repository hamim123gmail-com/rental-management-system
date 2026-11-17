from decimal import Decimal
from django.shortcuts import render, HttpResponseRedirect, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash, logout
from .models import Tenant, Owner, Building, Rental, Utility, Payment, Maintenance
from .forms import TenantForm, TenantCredentialsUpdateForm, OwnerForm, BuildingForm, RentalForm, UtilityForm, PaymentForm, MaintenanceForm, TenantMaintenanceRequestForm, AssignTenantForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required

def get_tenant_for_user(user):
    """Retrieve or link the Tenant record corresponding to a logged-in user.
    Only auto-creates a tenant profile for non-staff users."""
    tenant = getattr(user, 'tenant_profile', None)
    if not tenant:
        if user.email:
            tenant = Tenant.objects.filter(email__iexact=user.email).first()
        if not tenant:
            tenant = Tenant.objects.filter(first_name__iexact=user.username).first()
        if tenant and not tenant.user:
            tenant.user = user
            tenant.save()
    # Only auto-create a tenant profile for non-staff users
    if not tenant and not (user.is_staff or user.is_superuser):
        tenant = Tenant.objects.create(
            user=user,
            first_name=user.first_name or user.username,
            last_name=user.last_name or '',
            email=user.email or f"{user.username}@example.com",
            contact=''
        )
    return tenant

def admin_required(view_func):
    """Ensure only staff/superusers can access management views."""
    @login_required
    def _wrapped_view(req, *args, **kwargs):
        if not (req.user.is_staff or req.user.is_superuser):
            return redirect('tenant_dashboard_page')
        return view_func(req, *args, **kwargs)
    return _wrapped_view

# Index view
@admin_required
def index_view(req):

    # Accurate dynamic rental occupancy counts
    occupied_count = Rental.objects.filter(status='O').count()
    vacant_rentals = Rental.objects.filter(status='V').count()
    unlisted_vacant_buildings = Building.objects.filter(status='V').exclude(
        id__in=Rental.objects.values_list('building_id', flat=True)
    ).count()
    vacant_count = vacant_rentals + unlisted_vacant_buildings

    tenants_count = Tenant.objects.count()
    total_buildings = Building.objects.count()

    # Recent transaction history (latest payments)
    recent_transactions = Payment.objects.select_related('rental__building', 'tenant').order_by('-payment_date', '-id')[:10]
    total_payments_count = Payment.objects.count()

    context = {
        'occupied_count': occupied_count,
        'vacant_count': vacant_count,
        'tenants_count': tenants_count,
        'total_buildings': total_buildings,
        'recent_transactions': recent_transactions,
        'total_payments_count': total_payments_count,
    }
    return render(req, 'index.html', context)

# Tenant Portal Views
@login_required
def tenant_dashboard_view(req):
    tenant = get_tenant_for_user(req.user)
    rental = Rental.objects.filter(tenant=tenant).select_related('building__owner', 'tenant').first()
    utilities = Utility.objects.filter(rental=rental) if rental else []

    all_months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    selected_month = req.GET.get('month', '').strip()
    if rental:
        payments_qs = Payment.objects.filter(rental=rental).order_by('-payment_date')
        if selected_month:
            payments = list(payments_qs.filter(month__iexact=selected_month))
        else:
            payments = list(payments_qs)

        maintenance_list = Maintenance.objects.filter(rental=rental).order_by('-id')
        pending_requests_count = maintenance_list.filter(status='Pending').count()
        rent_amount = rental.rent_amount or Decimal('0.00')

        total_pending = Decimal('0.00')
        total_paid = Decimal('0.00')

        if payments:
            for p in payments:
                if p.status == 'C':
                    p.paid_display = p.amount
                    # Amount pending is rent amount - amount paid (min 0)
                    if p.amount >= rent_amount:
                        p.pending_balance = Decimal('0.00')
                    else:
                        p.pending_balance = rent_amount - p.amount
                else:
                    p.paid_display = Decimal('0.00')
                    p.pending_balance = p.amount if p.amount > 0 else rent_amount

                total_paid += p.paid_display
                total_pending += p.pending_balance

            pending_amount = total_pending
            amount_paid = total_paid
        else:
            amount_paid = Decimal('0.00')
            pending_amount = rent_amount
    else:
        payments = []
        maintenance_list = []
        pending_requests_count = 0
        amount_paid = Decimal('0.00')
        pending_amount = Decimal('0.00')

    context = {
        'tenant': tenant,
        'rental': rental,
        'utilities': utilities,
        'payments': payments,
        'all_months': all_months,
        'selected_month': selected_month,
        'maintenance_list': maintenance_list,
        'pending_requests_count': pending_requests_count,
        'amount_paid': amount_paid,
        'pending_amount': pending_amount,
        'credentials_form': TenantCredentialsUpdateForm(user=req.user, tenant=tenant),
    }
    return render(req, 'tenant_dashboard.html', context)

@login_required
@require_POST
def tenant_update_credentials_view(req):
    """Allow a tenant to update their username, email, contact, and password."""
    tenant = get_tenant_for_user(req.user)
    form = TenantCredentialsUpdateForm(req.POST, user=req.user, tenant=tenant)
    if form.is_valid():
        req.user.username = form.cleaned_data['username']
        req.user.email = form.cleaned_data['email']
        new_pwd = form.cleaned_data.get('new_password')
        if new_pwd:
            req.user.set_password(new_pwd)
        req.user.save()
        if new_pwd:
            # Keeps the session alive after password change
            update_session_auth_hash(req, req.user)
        if tenant:
            tenant.email = form.cleaned_data['email']
            tenant.contact = form.cleaned_data.get('contact', tenant.contact)
            tenant.save()
        messages.success(req, "Your credentials and profile have been updated successfully!")
    else:
        for errors in form.errors.values():
            for err in errors:
                messages.error(req, err)
    return redirect('tenant_dashboard_page')

@login_required
@require_POST
def tenant_request_maintenance_view(req):
    tenant = get_tenant_for_user(req.user)
    rental = Rental.objects.filter(tenant=tenant).first()
    if not rental:
        messages.error(req, "Cannot submit request: No active rental assigned to your account.")
        return redirect('tenant_dashboard_page')

    description = req.POST.get('description', '').strip()
    if description:
        Maintenance.objects.create(
            rental=rental,
            description=description,
            cost=0.00,
            status='Pending',
            is_read=False,
            maintenance_date=timezone.now().date()
        )
        messages.success(req, "Your maintenance request has been submitted to management!")
    else:
        messages.error(req, "Please enter a description for the maintenance issue.")

    return redirect(f"{reverse('tenant_dashboard_page')}#maintenance-section")

# List views with modal form support
# Tenant-list
@admin_required
def tenant_list_view(req):
    if req.method == "POST":
        form = TenantForm(req.POST)
        if form.is_valid():
            tenant = form.save()
            uname = tenant.user.username if tenant.user else '—'
            default_pwd = f"{tenant.last_name.strip().lower()}1234" if tenant.last_name else "tenant1234"
            pwd_shown = getattr(tenant, '_login_password', form.cleaned_data.get('password') or default_pwd)
            messages.success(
                req,
                f"Tenant {tenant} added! Login credentials — Username: '{uname}', Password: '{pwd_shown}'"
            )
            return redirect('tenant_list_page')
    else:
        form = TenantForm()
    tenants = Tenant.objects.all()
    return render(req, 'tenant_list.html', {'tenants': tenants, 'form': form})

# Owner-list
@admin_required
def owner_list_view(req):
    if req.method == "POST":
        form = OwnerForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Owner Added Successfully!")
            return redirect('owner_list_page')
    else:
        form = OwnerForm()
    owners = Owner.objects.all()
    return render(req, 'owner_list.html', {'owners': owners, 'form': form})

# Building-list
@admin_required
def building_list_view(req):
    if req.method == "POST":
        form = BuildingForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Building Added Successfully!")
            return redirect('building_list_page')
    else:
        form = BuildingForm()
    buildings = Building.objects.all()
    return render(req, 'building_list.html', {'buildings': buildings, 'form': form})

# Rental-list
@admin_required
def rental_list_view(req):
    if req.method == "POST":
        form = RentalForm(req.POST)
        if form.is_valid():
            rental = form.save()
            if rental.tenant:
                messages.success(req, f"Rental created and assigned to {rental.tenant} (Occupied)!")
            else:
                messages.success(req, f"Vacant rental created successfully for {rental.building.address}! Ready for tenant assignment.")
            return redirect('rental_list_page')
    else:
        form = RentalForm()

    status_filter = req.GET.get('status', '').strip().upper()
    rentals = Rental.objects.select_related('building', 'tenant').all()
    if status_filter in ['V', 'O']:
        rentals = rentals.filter(status=status_filter)

    assign_form = AssignTenantForm()
    vacant_count = Rental.objects.filter(status='V').count()
    occupied_count = Rental.objects.filter(status='O').count()

    context = {
        'rentals': rentals,
        'form': form,
        'assign_form': assign_form,
        'status_filter': status_filter,
        'vacant_count': vacant_count,
        'occupied_count': occupied_count,
    }
    return render(req, "rental_list.html", context)

# Assign Tenant to Vacant Rental
@admin_required
def assign_tenant_to_rental_view(req, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)
    if req.method == "POST":
        assign_form = AssignTenantForm(req.POST)
        if assign_form.is_valid():
            rental.tenant = assign_form.cleaned_data['tenant']
            rental.start_date = assign_form.cleaned_data['start_date']
            rental.end_date = assign_form.cleaned_data['end_date']
            rental.status = 'O'
            rental.save()
            messages.success(req, f"Tenant {rental.tenant} successfully assigned to {rental.building.address}!")
            return redirect('rental_list_page')
        else:
            messages.error(req, "Invalid assignment form data. Please check fields.")
    return redirect('rental_list_page')

# Utility-list
@admin_required
def utility_list_view(req):
    if req.method == "POST":
        form = UtilityForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Utility Added Successfully!")
            return redirect('utility_list_page')
    else:
        form = UtilityForm()
    utilities = Utility.objects.all()
    return render(req, 'utility_list.html', {'utilities': utilities, 'form': form})

# Payment-list
@admin_required
def payment_list_view(req):
    if req.method == "POST":
        form = PaymentForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Payment Added Successfully!")
            return redirect('payment_list_page')
    else:
        form = PaymentForm()
    payments = Payment.objects.select_related('rental', 'tenant').all()
    return render(req, 'payment_list.html', {'payments': payments, 'form': form})

# Maintenance-list
@admin_required
def maintenance_list_view(req):
    if req.method == "POST":
        form = MaintenanceForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Maintenance Added Successfully!")
            return redirect('maintenance_list_page')
    else:
        form = MaintenanceForm()
    maintenances = Maintenance.objects.select_related('rental').all()
    return render(req, 'maintenance_list.html', {'maintenances': maintenances, 'form': form})

# Add views (redirect to list with open_modal=1 or handle POST from modal)
@admin_required
def add_tenant_view(req):
    if req.method == "POST":
        form = TenantForm(req.POST)
        if form.is_valid():
            tenant = form.save()
            uname = tenant.user.username if tenant.user else '—'
            default_pwd = f"{tenant.last_name.strip().lower()}1234" if tenant.last_name else "tenant1234"
            pwd_shown = getattr(tenant, '_login_password', form.cleaned_data.get('password') or default_pwd)
            messages.success(
                req,
                f"Tenant {tenant} added! Login credentials — Username: '{uname}', Password: '{pwd_shown}'"
            )
        return redirect('tenant_list_page')
    return redirect(f"{reverse('tenant_list_page')}?open_modal=1")

@admin_required
def add_owner_view(req):
    if req.method == "POST":
        form = OwnerForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Owner Added Successfully!")
        return redirect('owner_list_page')
    return redirect(f"{reverse('owner_list_page')}?open_modal=1")

@admin_required
def add_building_view(req):
    if req.method == "POST":
        form = BuildingForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Building Added Successfully!")
        return redirect('building_list_page')
    return redirect(f"{reverse('building_list_page')}?open_modal=1")

@admin_required
def add_rental_view(req):
    if req.method == "POST":
        form = RentalForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Rental Added Successfully!")
        return redirect('rental_list_page')
    return redirect(f"{reverse('rental_list_page')}?open_modal=1")

@admin_required
def add_utility_view(req):
    if req.method == "POST":
        form = UtilityForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Utility Added Successfully!")
        return redirect('utility_list_page')
    return redirect(f"{reverse('utility_list_page')}?open_modal=1")

@admin_required
def add_payment_view(req):
    if req.method == "POST":
        form = PaymentForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Payment Added Successfully!")
        return redirect('payment_list_page')
    return redirect(f"{reverse('payment_list_page')}?open_modal=1")

@admin_required
def add_maintenance_view(req):
    if req.method == "POST":
        form = MaintenanceForm(req.POST)
        if form.is_valid():
            form.save()
            messages.success(req, "Maintenance Added Successfully!")
        return redirect('maintenance_list_page')
    return redirect(f"{reverse('maintenance_list_page')}?open_modal=1")


# Edit view (Update)
#Tenant-Edit
@admin_required
def edit_tenant_view(req, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    message = None
    if req.method == "POST":
        tenant_form = TenantForm(req.POST, instance=tenant)
        if tenant_form.is_valid():
            tenant_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('tenant_list_page')
        else:
            message = "Form has Invalid data"
    else:
        tenant_form = TenantForm(instance=tenant)

    context = {'form': tenant_form, 'tenant': tenant, 'msg': message}
    return render(req, "edit_tenant.html", context)

#Owner-Edit
@admin_required
def edit_owner_view(req, owner_id):
    owner = get_object_or_404(Owner, id=owner_id)
    message = None
    if req.method == "POST":
        owner_form = OwnerForm(req.POST, instance=owner)
        if owner_form.is_valid():
            owner_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('owner_list_page')
        else:
            message = "Form has Invalid data"
    else:
        owner_form = OwnerForm(instance=owner)

    context = {'form': owner_form, 'owner': owner, 'msg': message}
    return render(req, "edit_owner.html", context)

#Building-Edit
@admin_required
def edit_building_view(req, building_id):
    building = get_object_or_404(Building, id=building_id)
    message = None
    if req.method == "POST":
        building_form = BuildingForm(req.POST, instance=building)
        if building_form.is_valid():
            building_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('building_list_page')
        else:
            message = "Form has Invalid data"
    else:
        building_form = BuildingForm(instance=building)

    context = {'form': building_form, 'building': building, 'msg': message}
    return render(req, "edit_building.html", context)

#Rental-Edit
@admin_required
def edit_rental_view(req, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)
    message = None
    if req.method == "POST":
        rental_form = RentalForm(req.POST, instance=rental)
        if rental_form.is_valid():
            rental_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('rental_list_page')
        else:
            message = "Form has Invalid data"
    else:
        rental_form = RentalForm(instance=rental)

    context = {'form': rental_form, 'rental': rental, 'msg': message}
    return render(req, "edit_rental.html", context)

#Utility-Edit
@admin_required
def edit_utility_view(req, utility_id):
    utility = get_object_or_404(Utility, id=utility_id)
    message = None
    if req.method == "POST":
        utility_form = UtilityForm(req.POST, instance=utility)
        if utility_form.is_valid():
            utility_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('utility_list_page')
        else:
            message = "Form has Invalid data"
    else:
        utility_form = UtilityForm(instance=utility)

    context = {'form': utility_form, 'utility': utility, 'msg': message}
    return render(req, "edit_utility.html", context)

#Payment-Edit
@admin_required
def edit_payment_view(req, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    message = None
    if req.method == "POST":
        payment_form = PaymentForm(req.POST, instance=payment)
        if payment_form.is_valid():
            payment_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('payment_list_page')
        else:
            message = "Form has Invalid data"
    else:
        payment_form = PaymentForm(instance=payment)

    context = {'form': payment_form, 'payment': payment, 'msg': message}
    return render(req, "edit_payment.html", context)

#Maintenance-Edit
@admin_required
def edit_maintenance_view(req, maintenance_id):
    maintenance = get_object_or_404(Maintenance, id=maintenance_id)
    message = None
    if req.method == "POST":
        maintenance_form = MaintenanceForm(req.POST, instance=maintenance)
        if maintenance_form.is_valid():
            maintenance_form.save()
            messages.success(req, "Changes saved successfully!")
            return redirect('maintenance_list_page')
        else:
            message = "Form has Invalid data"
    else:
        maintenance_form = MaintenanceForm(instance=maintenance)

    context = {'form': maintenance_form, 'maintenance': maintenance, 'msg': message}
    return render(req, "edit_maintenance.html", context)

#Delete views — all require POST to prevent CSRF/accidental deletion via GET links
@admin_required
@require_POST
def delete_tenant_view(req, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    linked_user = tenant.user
    tenant.delete()
    if linked_user:
        linked_user.delete()
    messages.success(req, "Tenant and linked user account deleted successfully.")
    return redirect('tenant_list_page')

@admin_required
@require_POST
def delete_owner_view(req, owner_id):
    owner = get_object_or_404(Owner, id=owner_id)
    owner.delete()
    messages.success(req, "Owner deleted successfully.")
    return redirect('owner_list_page')

@admin_required
@require_POST
def delete_building_view(req, building_id):
    building = get_object_or_404(Building, id=building_id)
    building.delete()
    messages.success(req, "Building deleted successfully.")
    return redirect('building_list_page')

@admin_required
@require_POST
def delete_rental_view(req, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)
    rental.delete()
    messages.success(req, "Rental deleted successfully.")
    return redirect('rental_list_page')

@admin_required
@require_POST
def delete_utility_view(req, utility_id):
    utility = get_object_or_404(Utility, id=utility_id)
    utility.delete()
    messages.success(req, "Utility deleted successfully.")
    return redirect('utility_list_page')

@admin_required
@require_POST
def delete_payment_view(req, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.delete()
    messages.success(req, "Payment deleted successfully.")
    return redirect('payment_list_page')

@admin_required
@require_POST
def delete_maintenance_view(req, maintenance_id):
    maintenance = get_object_or_404(Maintenance, id=maintenance_id)
    maintenance.delete()
    messages.success(req, "Maintenance record deleted successfully.")
    return redirect('maintenance_list_page')

# Sign up view
def sign_up_view(req):
    if req.method == "POST":
        sign_up_form = UserCreationForm(req.POST)
        if sign_up_form.is_valid():
            user = sign_up_form.save()
            # Automatically establish tenant profile for self-registered users
            Tenant.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': user.first_name or user.username,
                    'last_name': user.last_name or '',
                    'email': user.email or f"{user.username}@example.com",
                    'contact': ''
                }
            )
            return HttpResponseRedirect('/accounts/login/')
    else:
        sign_up_form = UserCreationForm()
    
    context = {'form': sign_up_form}
    return render(req, "registration/sign_up.html", context)

# Logout view (handles both GET and POST safely without 405 Method Not Allowed)
def logout_view(req):
    logout(req)
    messages.success(req, "You have been logged out successfully.")
    return redirect('login')
