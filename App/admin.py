from django.contrib import admin
from .models import Tenant, Owner, Building, Rental, Utility, Payment, Maintenance

# Register your models here.
class TenantAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "user", "contact", "email")
admin.site.register(Tenant, TenantAdmin)

class OwnerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "contact", "email")
admin.site.register(Owner, OwnerAdmin)

class BuildingAdmin(admin.ModelAdmin):
    list_display = ("address", "status", "owner")
admin.site.register(Building, BuildingAdmin)

class RentalAdmin(admin.ModelAdmin):
    list_display = ("building", "tenant", "status", "start_date", "end_date", "rent_amount", "type")
    list_filter = ("status", "type")
admin.site.register(Rental, RentalAdmin)

class UtilityAdmin(admin.ModelAdmin):
    list_display = ("type", "rental")
admin.site.register(Utility, UtilityAdmin)

class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_date", "amount", "rental", "tenant", "status", "late_fee", "month")
admin.site.register(Payment, PaymentAdmin)

class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ("maintenance_date", "description", "rental", "cost", "status", "is_read")
    list_filter = ("status", "maintenance_date")
admin.site.register(Maintenance, MaintenanceAdmin)