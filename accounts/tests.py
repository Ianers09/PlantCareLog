from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import HealthLog, Plant, WateringLog


class Workflow1_FullPlantLifecycleTests(TestCase):
    """Workflow 1 (happy path): register -> log in -> add a plant -> log
    watering -> log a health status -> see it reflected on the dashboard
    and plant list. Exercises every core + supporting feature together."""

    def setUp(self):
        self.client.post(
            reverse("register"),
            {
                "username": "maria",
                "email": "maria@example.com",
                "password1": "GreenThumb!2026",
                "password2": "GreenThumb!2026",
            },
        )

    def test_register_creates_profile(self):
        user = User.objects.get(username="maria")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(user.profile.email, "maria@example.com")

    def test_add_plant_appears_in_list_and_detail(self):
        response = self.client.post(
            reverse("plant_create"),
            {"name": "Monstera", "species": "Monstera deliciosa", "watering_interval": "7"},
        )
        self.assertRedirects(response, reverse("plant_list"))
        plant = Plant.objects.get(name="Monstera")
        self.assertEqual(plant.owner.user.username, "maria")

        list_response = self.client.get(reverse("plant_list"))
        self.assertContains(list_response, "Monstera")

        detail_response = self.client.get(reverse("plant_detail", args=[plant.plant_id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Never watered")

    def test_logging_watering_and_health_updates_dashboard(self):
        self.client.post(reverse("plant_create"), {"name": "Basil", "watering_interval": "3"})
        plant = Plant.objects.get(name="Basil")

        water_response = self.client.post(reverse("watering_log_add", args=[plant.plant_id]), {"note": "Morning water"})
        self.assertRedirects(water_response, reverse("plant_detail", args=[plant.plant_id]))
        self.assertEqual(WateringLog.objects.filter(plant=plant).count(), 1)

        health_response = self.client.post(
            reverse("health_log_add", args=[plant.plant_id]), {"health_status": HealthLog.HEALTHY}
        )
        self.assertRedirects(health_response, reverse("plant_detail", args=[plant.plant_id]))
        self.assertEqual(HealthLog.objects.filter(plant=plant).count(), 1)

        plant.refresh_from_db()
        self.assertEqual(plant.watering_status, Plant.STATUS_OK)

        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_response, "Basil")
        self.assertContains(dashboard_response, "Healthy")


class Workflow2_UnauthorizedAccessTests(TestCase):
    """Workflow 2: one user must never be able to view, edit, delete, or log
    watering/health entries against another user's plant, even by guessing
    or reusing a direct URL."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="OwnerPass!2026")
        self.intruder = User.objects.create_user(username="intruder", password="IntruderPass!2026")
        self.plant = Plant.objects.create(owner=self.owner.profile, name="Owner's Fern")

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse("plant_detail", args=[self.plant.plant_id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_other_user_cannot_view_plant_detail(self):
        self.client.login(username="intruder", password="IntruderPass!2026")
        response = self.client.get(reverse("plant_detail", args=[self.plant.plant_id]))
        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_edit_plant(self):
        self.client.login(username="intruder", password="IntruderPass!2026")
        response = self.client.post(
            reverse("plant_edit", args=[self.plant.plant_id]), {"name": "Hijacked name"}
        )
        self.assertEqual(response.status_code, 404)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.name, "Owner's Fern")

    def test_other_user_cannot_delete_plant(self):
        self.client.login(username="intruder", password="IntruderPass!2026")
        response = self.client.post(reverse("plant_delete", args=[self.plant.plant_id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Plant.objects.filter(pk=self.plant.plant_id).exists())

    def test_other_user_cannot_log_watering_for_plant_they_do_not_own(self):
        self.client.login(username="intruder", password="IntruderPass!2026")
        response = self.client.post(reverse("watering_log_add", args=[self.plant.plant_id]), {"note": "sneaky"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(WateringLog.objects.filter(plant=self.plant).count(), 0)

    def test_non_staff_user_cannot_reach_admin_dashboard(self):
        self.client.login(username="intruder", password="IntruderPass!2026")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)


class Workflow3_ValidationAndDuplicateRecordTests(TestCase):
    """Workflow 3: validation scenarios, including the required duplicate-
    record case (a user cannot have two plants with the same name) and a
    duplicate watering log for the same day."""

    def setUp(self):
        self.user = User.objects.create_user(username="kit", password="KitPass!2026")
        self.client.login(username="kit", password="KitPass!2026")

    def test_duplicate_plant_name_for_same_owner_is_rejected(self):
        first = self.client.post(reverse("plant_create"), {"name": "Snake Plant"})
        self.assertRedirects(first, reverse("plant_list"))
        self.assertEqual(Plant.objects.filter(name__iexact="Snake Plant").count(), 1)

        second = self.client.post(reverse("plant_create"), {"name": "snake plant"})
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, "already have a plant named")
        self.assertEqual(Plant.objects.filter(name__iexact="Snake Plant").count(), 1)

    def test_renaming_plant_to_an_existing_name_is_rejected(self):
        self.client.post(reverse("plant_create"), {"name": "Aloe"})
        self.client.post(reverse("plant_create"), {"name": "Cactus"})
        cactus = Plant.objects.get(name="Cactus")

        response = self.client.post(reverse("plant_edit", args=[cactus.plant_id]), {"name": "Aloe"})
        self.assertContains(response, "already have a plant named")
        cactus.refresh_from_db()
        self.assertEqual(cactus.name, "Cactus")

    def test_plant_name_is_required(self):
        response = self.client.post(reverse("plant_create"), {"name": "  "})
        self.assertContains(response, "Plant name is required")
        self.assertFalse(Plant.objects.filter(owner=self.user.profile).exists())

    def test_negative_watering_interval_is_rejected(self):
        response = self.client.post(reverse("plant_create"), {"name": "Fig", "watering_interval": "-3"})
        self.assertContains(response, "positive number of days")
        self.assertFalse(Plant.objects.filter(name="Fig").exists())

    def test_duplicate_watering_log_same_day_is_rejected(self):
        self.client.post(reverse("plant_create"), {"name": "Pothos"})
        plant = Plant.objects.get(name="Pothos")

        first = self.client.post(reverse("watering_log_add", args=[plant.plant_id]), {"note": "First"})
        self.assertRedirects(first, reverse("plant_detail", args=[plant.plant_id]))

        second = self.client.post(reverse("watering_log_add", args=[plant.plant_id]), {"note": "Second"})
        self.assertRedirects(second, reverse("plant_detail", args=[plant.plant_id]))

        self.assertEqual(WateringLog.objects.filter(plant=plant).count(), 1)
