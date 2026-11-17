from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import date
from App.models import Owner, Building, Tenant, Rental, Utility, Payment, Maintenance

class RoleInterfaceAndNotificationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Admin user
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='password123'
        )

        # Create Tenant user
        self.tenant_user = User.objects.create_user(
            username='tenant_test',
            email='tenant@test.com',
            password='password123'
        )

        # Create Owner and Building
        self.owner = Owner.objects.create(
            first_name='John',
            last_name='Landlord',
            contact='1234567890',
            email='landlord@test.com'
        )
        self.building = Building.objects.create(
            address='123 Maple Street Apt 4B',
            status='O',
            owner=self.owner
        )

        # Create Tenant Profile linked to tenant_user
        self.tenant = Tenant.objects.create(
            user=self.tenant_user,
            first_name='Alice',
            last_name='Tenant',
            contact='9876543210',
            email='tenant@test.com'
        )

        # Create Rental lease
        self.rental = Rental.objects.create(
            building=self.building,
            tenant=self.tenant,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            rent_amount=1200.00,
            type='A'
        )

        # Create Utility
        self.utility = Utility.objects.create(
            type='Water & Gas',
            rental=self.rental
        )

        # Create Payment
        self.payment = Payment.objects.create(
            rental=self.rental,
            tenant=self.tenant,
            payment_date=date(2026, 3, 1),
            amount=1200.00,
            status='C',
            late_fee=0.00,
            month='March'
        )

    def test_admin_dashboard_access(self):
        """Admin logging in gets the admin dashboard with statistical blocks and transaction history."""
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('index_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertContains(response, 'Rental Mgt')
        self.assertContains(response, 'Rentals Occupied')
        self.assertContains(response, 'Rentals Vacant')
        self.assertContains(response, 'Total Tenants')
        self.assertContains(response, 'Transaction History')
        self.assertEqual(response.context['occupied_count'], 1)
        self.assertEqual(response.context['vacant_count'], 0)
        self.assertEqual(response.context['tenants_count'], 1)
        self.assertEqual(len(response.context['recent_transactions']), 1)

    def test_tenant_redirect_to_tenant_portal(self):
        """Regular tenant visiting root is redirected to /my-rental/."""
        self.client.login(username='tenant_test', password='password123')
        response = self.client.get(reverse('index_page'))
        self.assertRedirects(response, reverse('tenant_dashboard_page'))

    def test_tenant_portal_content(self):
        """Tenant portal displays only header navbar and rental/payment details."""
        self.client.login(username='tenant_test', password='password123')
        response = self.client.get(reverse('tenant_dashboard_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tenant_dashboard.html')
        # Check specific rental details
        self.assertContains(response, '123 Maple Street Apt 4B')
        self.assertContains(response, 'Ugx 1200.00')
        self.assertContains(response, 'Water &amp; Gas')
        self.assertContains(response, 'John Landlord')
        # Check payment status
        self.assertContains(response, 'March')
        self.assertContains(response, 'Complete')
        # Check pending amount is 0 when all payments are Complete (cleared)
        self.assertEqual(response.context['pending_amount'], 0)
        self.assertContains(response, 'Amount Pending')
        self.assertContains(response, 'Ugx 0')
        self.assertContains(response, 'Cleared')

    def test_tenant_portal_pending_amount_when_unpaid(self):
        """When tenant has unpaid bills or partial payments, pending amount shows rent amount - amount paid."""
        # Tenant pays 700 out of 1200 rent for April (partial payment)
        Payment.objects.create(
            rental=self.rental,
            tenant=self.tenant,
            payment_date=date(2026, 4, 1),
            amount=700.00,
            status='C',
            late_fee=0.00,
            month='April'
        )
        self.client.login(username='tenant_test', password='password123')
        # Filter April
        response = self.client.get(f"{reverse('tenant_dashboard_page')}?month=April")
        self.assertEqual(response.status_code, 200)
        # Rent 1200 - Paid 700 = 500
        self.assertEqual(response.context['pending_amount'], 500.00)
        self.assertEqual(response.context['amount_paid'], 700.00)
        self.assertContains(response, 'Ugx 500.00')

    def test_tenant_maintenance_request_reflects_in_admin_notifications(self):
        """Tenant submits maintenance request and it immediately shows up in admin notifications."""
        # 1. Tenant submits request
        self.client.login(username='tenant_test', password='password123')
        post_response = self.client.post(
            reverse('tenant_request_maintenance_page'),
            {'description': 'The kitchen faucet is dripping heavily.'}
        )
        self.assertEqual(post_response.status_code, 302)

        # Verify maintenance request was created in DB with 'Pending' status
        maintenance = Maintenance.objects.filter(rental=self.rental).first()
        self.assertIsNotNone(maintenance)
        self.assertEqual(maintenance.description, 'The kitchen faucet is dripping heavily.')
        self.assertEqual(maintenance.status, 'Pending')

        # 2. Admin logs in and checks dashboard
        self.client.login(username='admin_test', password='password123')
        admin_response = self.client.get(reverse('index_page'))
        self.assertEqual(admin_response.status_code, 200)

        # Check context processor variables
        self.assertEqual(admin_response.context['admin_notifications_count'], 1)
        # Check that description and tenant name appear in notification dropdown HTML
        self.assertContains(admin_response, 'The kitchen faucet is dripping')
        self.assertContains(admin_response, 'Alice Tenant')

    def test_rental_assignment_automatically_sets_building_occupied(self):
        """When a rental is assigned to a building, building status automatically switches to 'O' (Occupied)."""
        vacant_building = Building.objects.create(
            address='789 Oak Lane',
            status='V',
            owner=self.owner
        )
        self.assertEqual(vacant_building.status, 'V')

        new_rental = Rental.objects.create(
            building=vacant_building,
            tenant=self.tenant,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 12, 31),
            rent_amount=850.00,
            type='H'
        )
        vacant_building.refresh_from_db()
        self.assertEqual(vacant_building.status, 'O')

        # Deleting rental reverts to vacant
        new_rental.delete()
        vacant_building.refresh_from_db()
        self.assertEqual(vacant_building.status, 'V')

    def test_add_popup_modal_and_submission(self):
        """Test that list pages render the popup modal and handle modal form creation."""
        self.client.login(username='admin_test', password='password123')
        # Check modal markup is in the list page
        response = self.client.get(reverse('tenant_list_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="addTenantModal"')
        self.assertContains(response, 'data-bs-target="#addTenantModal"')

        # Post new tenant via list view (simulating modal form submit)
        post_response = self.client.post(reverse('tenant_list_page'), {
            'first_name': 'Bob',
            'last_name': 'Builder',
            'contact': '5551234',
            'email': 'bob@builder.com'
        })
        self.assertRedirects(post_response, reverse('tenant_list_page'))
        bob = Tenant.objects.filter(first_name='Bob', last_name='Builder').first()
        self.assertIsNotNone(bob)
        self.assertIsNotNone(bob.user)
        self.assertEqual(bob.user.username, 'bob')
        self.assertTrue(bob.user.check_password('builder1234'))

    def test_edit_page_saves_and_redirects_to_list_with_success_message(self):
        """Editing an entity saves changes, shows message, and redirects back to the list page."""
        self.client.login(username='admin_test', password='password123')
        edit_response = self.client.post(
            reverse('edit_tenant_page', args=[self.tenant.id]),
            {
                'first_name': 'AliceEdited',
                'last_name': 'Tenant',
                'contact': '9876543210',
                'email': 'tenant@test.com'
            },
            follow=True
        )
        # Should redirect back to list page, not stay on edit page
        self.assertRedirects(edit_response, reverse('tenant_list_page'))
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.first_name, 'AliceEdited')
        # Success message should be in redirected response
        self.assertContains(edit_response, 'Changes saved successfully!')

    def test_statistical_blocks_automatically_update_with_vacant_and_occupied_rentals(self):
        """Dashboard statistical blocks automatically reflect vacant vs occupied changes."""
        self.client.login(username='admin_test', password='password123')

        # Initially: 1 occupied rental, 0 vacant rentals, 1 tenant
        initial_resp = self.client.get(reverse('index_page'))
        self.assertEqual(initial_resp.context['occupied_count'], 1)
        self.assertEqual(initial_resp.context['vacant_count'], 0)
        self.assertEqual(initial_resp.context['tenants_count'], 1)

        # 1. Create a new vacant rental unit (no tenant)
        new_building = Building.objects.create(
            address='456 Pine Ave',
            status='V',
            owner=self.owner
        )
        vacant_rental = Rental.objects.create(
            building=new_building,
            rent_amount=900.00,
            type='A',
            status='V'
        )
        resp_after_vacant = self.client.get(reverse('index_page'))
        # Vacant count automatically updates to 1
        self.assertEqual(resp_after_vacant.context['vacant_count'], 1)
        self.assertEqual(resp_after_vacant.context['occupied_count'], 1)

        # 2. Assign tenant to the vacant rental
        new_tenant = Tenant.objects.create(
            first_name='Charlie',
            last_name='Tenant',
            contact='111222333',
            email='charlie@test.com'
        )
        assign_resp = self.client.post(
            reverse('assign_rental_page', args=[vacant_rental.id]),
            {
                'tenant': new_tenant.id,
                'start_date': '2026-05-01',
                'end_date': '2026-12-31'
            }
        )
        self.assertRedirects(assign_resp, reverse('rental_list_page'))

        # 3. Check dashboard again: occupied automatically +1, vacant automatically -1, tenants +1
        resp_after_assign = self.client.get(reverse('index_page'))
        self.assertEqual(resp_after_assign.context['occupied_count'], 2)
        self.assertEqual(resp_after_assign.context['vacant_count'], 0)
        self.assertEqual(resp_after_assign.context['tenants_count'], 2)

    def test_safe_logout_view(self):
        """Logout safely handles both GET and POST requests and redirects to login without 405 error."""
        self.client.login(username='admin_test', password='password123')
        # Test GET logout
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

        # Test POST logout
        self.client.login(username='admin_test', password='password123')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
