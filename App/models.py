from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

# Create your models here.
class Owner(models.Model):
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    contact = models.CharField(max_length=20)
    email = models.EmailField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Building(models.Model):
    STATUS_OPTIONS = [
        ('O','Occupied'),
        ('V','Vacant')
    ]
    address = models.CharField(max_length=100)
    status = models.CharField(max_length=2, choices=STATUS_OPTIONS)
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.address}({self.get_status_display()})"

class Tenant(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tenant_profile')
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    contact = models.CharField(max_length=20)
    email = models.EmailField(max_length=255)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Rental(models.Model):
    STATUS_CHOICES = [
        ('V', 'Vacant'),
        ('O', 'Occupied'),
    ]
    TYPE_OPTIONS = [
        ('H','House'),
        ('A','Apartment')
    ]
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=2, choices=TYPE_OPTIONS)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='V')

    def __str__(self):
        if self.tenant:
            return f"{self.building.address} - {self.tenant} ({self.get_status_display()})"
        return f"{self.building.address} (Vacant)"

    def save(self, *args, **kwargs):
        # Automatically keep rental and building occupancy status in sync
        if self.tenant:
            self.status = 'O'
            if self.building and self.building.status != 'O':
                self.building.status = 'O'
                self.building.save(update_fields=['status'])
        else:
            self.status = 'V'
            if self.building and not Rental.objects.filter(building=self.building, status='O').exclude(id=self.id).exists():
                self.building.status = 'V'
                self.building.save(update_fields=['status'])
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        building = self.building
        super().delete(*args, **kwargs)
        # If no active occupied rentals remain on this building, change status back to Vacant
        if building and not Rental.objects.filter(building=building, status='O').exists():
            building.status = 'V'
            building.save(update_fields=['status'])



class Utility(models.Model):
    type = models.CharField(max_length=20, null=False)
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.type} {self.rental}"
    

class Payment(models.Model):
    MONTH_CHOICES = [
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
    ]
    STATUS_OPTIONS = [
        ('C','Complete'),
        ('P','Pending')
    ]
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    status = models.CharField(max_length=2, choices=STATUS_OPTIONS)
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    month = models.CharField(max_length=15, choices=MONTH_CHOICES)

    def __str__(self):
        return f"{self.id}-Ugx {self.amount}({self.tenant})"


class Maintenance(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
    ]
    maintenance_date = models.DateField(default=date.today)
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.rental} - {self.description[:25]} ({self.status})"
