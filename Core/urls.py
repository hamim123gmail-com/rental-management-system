from django.contrib import admin
from django.urls import path, include
from App.views import (
    index_view, tenant_dashboard_view, tenant_request_maintenance_view, tenant_update_credentials_view,
    tenant_list_view, add_tenant_view, edit_tenant_view, delete_tenant_view,
    owner_list_view, add_owner_view, edit_owner_view, delete_owner_view,
    building_list_view, add_building_view, edit_building_view, delete_building_view,
    rental_list_view, add_rental_view, edit_rental_view, delete_rental_view, assign_tenant_to_rental_view,
    utility_list_view, add_utility_view, edit_utility_view, delete_utility_view,
    payment_list_view, add_payment_view, edit_payment_view, delete_payment_view,
    maintenance_list_view, add_maintenance_view, edit_maintenance_view, delete_maintenance_view,
    sign_up_view, logout_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index_view, name='index_page'),

    # Safe Logout (handles both GET and POST to prevent 405 Method Not Allowed)
    path('accounts/logout/', logout_view, name='logout'),
    path('logout/', logout_view, name='logout_direct'),

    # Tenant Portal (Tenant-only view)
    path('my-rental/', tenant_dashboard_view, name='tenant_dashboard_page'),
    path('request-maintenance/', tenant_request_maintenance_view, name='tenant_request_maintenance_page'),
    path('tenant-update-credentials/', tenant_update_credentials_view, name='tenant_update_credentials_page'),

    #Tenant
    path('tenant/', tenant_list_view, name='tenant_list_page'),
    path('add_tenant/', add_tenant_view, name='add_tenant_page'),
    path('edit_tenant/<int:tenant_id>/', edit_tenant_view, name='edit_tenant_page'),
    path('delete_tenant/<int:tenant_id>/', delete_tenant_view, name="delete_tenant_page"),

    #Owner
    path('owner/', owner_list_view, name='owner_list_page'),
    path('add_owner/', add_owner_view, name='add_owner_page'),
    path('edit_owner/<int:owner_id>/', edit_owner_view, name='edit_owner_page'),
    path('delete_owner/<int:owner_id>/', delete_owner_view, name="delete_owner_page"),

    #Building
    path('building/', building_list_view, name='building_list_page'),
    path('add_building/', add_building_view, name='add_building_page'),
    path('edit_building/<int:building_id>/', edit_building_view, name='edit_building_page'),
    path('delete_building/<int:building_id>/', delete_building_view, name="delete_building_page"),

    #Rental
    path('rental/', rental_list_view, name='rental_list_page'),
    path('add_rental/', add_rental_view, name='add_rental_page'),
    path('edit_rental/<int:rental_id>/', edit_rental_view, name='edit_rental_page'),
    path('delete_rental/<int:rental_id>/', delete_rental_view, name="delete_rental_page"),
    path('assign_rental/<int:rental_id>/', assign_tenant_to_rental_view, name="assign_rental_page"),

    #Utility
    path('utility/', utility_list_view, name='utility_list_page'),
    path('add_utility/', add_utility_view, name='add_utility_page'),
    path('edit_utility/<int:utility_id>/', edit_utility_view, name='edit_utility_page'),
    path('delete_utility/<int:utility_id>/', delete_utility_view, name="delete_utility_page"),

    #Payment
    path('payment/', payment_list_view, name='payment_list_page'),
    path('add_payment/', add_payment_view, name='add_payment_page'),
    path('edit_payment/<int:payment_id>/', edit_payment_view, name='edit_payment_page'),
    path('delete_payment/<int:payment_id>/', delete_payment_view, name="delete_payment_page"),

    #Maintenance
    path('maintenance/', maintenance_list_view, name='maintenance_list_page'),
    path('add_maintenance/', add_maintenance_view, name='add_maintenance_page'),
    path('edit_maintenance/<int:maintenance_id>/', edit_maintenance_view, name='edit_maintenance_page'),
    path('delete_maintenance/<int:maintenance_id>/', delete_maintenance_view, name="delete_maintenance_page"),

    # Authentication
    path('sign_up/', sign_up_view, name='sign_up_page'),
    path('accounts/', include('django.contrib.auth.urls')),

]

