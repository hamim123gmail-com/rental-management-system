from .models import Maintenance, Tenant

def admin_notifications_processor(request):
    if not request.user.is_authenticated:
        return {}
    
    is_admin = request.user.is_staff or request.user.is_superuser
    context = {
        'is_admin': is_admin,
    }

    if is_admin:
        # Fetch pending maintenance requests
        pending_requests = Maintenance.objects.filter(status='Pending').select_related(
            'rental__tenant', 'rental__building'
        ).order_by('-id')
        
        context['admin_notifications'] = pending_requests[:10]
        context['admin_notifications_count'] = pending_requests.count()
    else:
        # If tenant, provide their tenant profile and rental info if helpful
        tenant = getattr(request.user, 'tenant_profile', None)
        if not tenant:
            tenant = Tenant.objects.filter(email__iexact=request.user.email).first()
        context['tenant_profile'] = tenant
        
    return context

