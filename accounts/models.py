import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Profile(models.Model):
    owner_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profiles"

    def __str__(self):
        return self.full_name


class Plant(models.Model):
    plant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="plants", db_column="owner_id")
    name = models.CharField(max_length=255)
    species = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    watering_interval = models.IntegerField(blank=True, null=True, help_text="Days between watering")
    last_watered_on = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to="plant_photos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Status labels used across the dashboard, plant list filters, and templates.
    STATUS_NEVER = "never"
    STATUS_OVERDUE = "overdue"
    STATUS_DUE_SOON = "due_soon"
    STATUS_OK = "ok"

    class Meta:
        db_table = "plants"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "owner",
                name="unique_plant_name_per_owner",
                violation_error_message="You already have a plant with this name.",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def watering_status(self):
        """Classify this plant's watering status as never / overdue / due_soon / ok.

        Used to power the dashboard reminders widget and the plant list filter,
        so the watering schedule set on the core Plant feature drives every
        supporting feature instead of being duplicated logic.
        """
        if not self.last_watered_on:
            return self.STATUS_NEVER
        if not self.watering_interval:
            return self.STATUS_OK

        due_on = self.last_watered_on + timedelta(days=self.watering_interval)
        days_left = (due_on.date() - timezone.localdate()).days

        if days_left < 0:
            return self.STATUS_OVERDUE
        if days_left == 0:
            return self.STATUS_DUE_SOON
        return self.STATUS_OK

    @property
    def latest_health_status(self):
        latest = self.health_logs.order_by("-created_at").first()
        return latest.health_status if latest else None

    def watered_today(self):
        return self.watering_logs.filter(watered_on__date=timezone.localdate()).exists()


class WateringLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="watering_logs", db_column="plant_id")
    watered_on = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "watering_logs"

    def __str__(self):
        return f"{self.plant.name} watered on {self.watered_on:%Y-%m-%d}"


class HealthLog(models.Model):
    HEALTHY = "Healthy"
    WILTING = "Wilting"
    RECOVERING = "Recovering"
    STATUS_CHOICES = [
        (HEALTHY, "Healthy"),
        (WILTING, "Wilting"),
        (RECOVERING, "Recovering"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="health_logs", db_column="plant_id")
    health_status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    photo = models.ImageField(upload_to="health_photos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "health_logs"

    def __str__(self):
        return f"{self.plant.name} - {self.health_status}"


@receiver(post_save, sender=User)
def sync_profile(sender, instance, created, **kwargs):
    full_name = f"{instance.first_name} {instance.last_name}".strip() or instance.username
    email = instance.email or f"{instance.username}@placeholder.local"
    if created:
        Profile.objects.create(user=instance, full_name=full_name, username=instance.username, email=email)
    else:
        Profile.objects.filter(user=instance).update(full_name=full_name, username=instance.username, email=email)