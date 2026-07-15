from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RegisterForm
from .models import HealthLog, Plant, WateringLog


def home(request):
    """Root URL: send signed-in users to their dashboard, everyone else to login."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(next_url or "dashboard")
        messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    auth_logout(request)
    messages.info(request, "You've been signed out.")
    return redirect("login")


@login_required
def dashboard_view(request):
    """Dashboard integrates the core Plant/WateringLog/HealthLog feature into
    an at-a-glance reminders view: which plants are overdue, due soon, or have
    never been watered, plus the most recent health status changes."""
    plants = list(request.user.profile.plants.all())

    overdue_plants = [p for p in plants if p.watering_status == Plant.STATUS_OVERDUE]
    due_soon_plants = [p for p in plants if p.watering_status == Plant.STATUS_DUE_SOON]
    never_watered_plants = [p for p in plants if p.watering_status == Plant.STATUS_NEVER]

    recent_health_logs = (
        HealthLog.objects.filter(plant__owner=request.user.profile)
        .select_related("plant")
        .order_by("-created_at")[:5]
    )

    context = {
        "total_plants": len(plants),
        "overdue_plants": overdue_plants,
        "due_soon_plants": due_soon_plants,
        "never_watered_plants": never_watered_plants,
        "needs_attention_count": len(overdue_plants) + len(due_soon_plants),
        "recent_health_logs": recent_health_logs,
    }
    return render(request, "accounts/dashboard.html", context)


@staff_member_required
def admin_dashboard_view(request):
    context = {
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "staff_users": User.objects.filter(is_staff=True).count(),
        "recent_users": User.objects.order_by("-date_joined")[:8],
    }
    return render(request, "accounts/admin_dashboard.html", context)


@staff_member_required
def manage_users_view(request):
    query = request.GET.get("q", "").strip()
    users = User.objects.all().order_by("-date_joined")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    return render(request, "accounts/manage_users.html", {"users": users, "query": query})


@staff_member_required
def edit_user_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        target.first_name = request.POST.get("first_name", "").strip()
        target.last_name = request.POST.get("last_name", "").strip()
        target.email = request.POST.get("email", "").strip()
        target.save()
        messages.success(request, f"Updated {target.username}.")
        return redirect("manage_users")

    return render(request, "accounts/edit_user.html", {"target": target})


@staff_member_required
@require_POST
def toggle_active_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        messages.error(request, "You can't deactivate your own account.")
    else:
        target.is_active = not target.is_active
        target.save()
        messages.success(request, f"{target.username} is now {'active' if target.is_active else 'inactive'}.")
    return redirect("manage_users")


@staff_member_required
@require_POST
def toggle_staff_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        messages.error(request, "You can't change your own staff status.")
    else:
        target.is_staff = not target.is_staff
        target.save()
        messages.success(request, f"{target.username} is now {'staff' if target.is_staff else 'a regular user'}.")
    return redirect("manage_users")


@staff_member_required
@require_POST
def delete_user_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        messages.error(request, "You can't delete your own account.")
    else:
        username = target.username
        target.delete()
        messages.success(request, f"Deleted user {username}.")
    return redirect("manage_users")


@login_required
def plant_list_view(request):
    plants_qs = request.user.profile.plants.all().order_by("-created_at")

    query = request.GET.get("q", "").strip()
    if query:
        plants_qs = plants_qs.filter(
            Q(name__icontains=query) | Q(species__icontains=query) | Q(location__icontains=query)
        )

    status_filter = request.GET.get("status", "").strip()
    valid_statuses = {Plant.STATUS_OVERDUE, Plant.STATUS_DUE_SOON, Plant.STATUS_NEVER, Plant.STATUS_OK}
    plants = list(plants_qs)
    if status_filter in valid_statuses:
        plants = [p for p in plants if p.watering_status == status_filter]

    context = {
        "plants": plants,
        "query": query,
        "status_filter": status_filter,
    }
    return render(request, "accounts/plant_list.html", context)


@login_required
def plant_create_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        species = request.POST.get("species", "").strip()
        location = request.POST.get("location", "").strip()
        watering_interval = request.POST.get("watering_interval", "").strip() or None
        notes = request.POST.get("notes", "").strip()
        photo = request.FILES.get("photo")

        if not name:
            messages.error(request, "Plant name is required.")
        elif watering_interval and (not watering_interval.isdigit() or int(watering_interval) <= 0):
            messages.error(request, "Watering interval must be a positive number of days.")
        elif request.user.profile.plants.filter(name__iexact=name).exists():
            messages.error(request, f'You already have a plant named "{name}". Choose a different name.')
        else:
            try:
                Plant.objects.create(
                    owner=request.user.profile,
                    name=name,
                    species=species or None,
                    location=location or None,
                    watering_interval=watering_interval,
                    notes=notes or None,
                    photo=photo,
                )
            except IntegrityError:
                # Safety net for a race condition where two requests create the
                # same duplicate name at the same time (the unique constraint
                # on the model catches what the check above might miss).
                messages.error(request, f'You already have a plant named "{name}". Choose a different name.')
            else:
                messages.success(request, f"Added {name} to your plants.")
                return redirect("plant_list")

        # Re-render with the submitted values so the user doesn't lose their input.
        return render(
            request,
            "accounts/plant_form.html",
            {
                "plant": None,
                "form_data": {
                    "name": name,
                    "species": species,
                    "location": location,
                    "watering_interval": watering_interval,
                    "notes": notes,
                },
            },
        )

    return render(request, "accounts/plant_form.html", {"plant": None})


@login_required
def plant_edit_view(request, plant_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        watering_interval = request.POST.get("watering_interval", "").strip() or None

        if not name:
            messages.error(request, "Plant name is required.")
        elif watering_interval and (not watering_interval.isdigit() or int(watering_interval) <= 0):
            messages.error(request, "Watering interval must be a positive number of days.")
        elif request.user.profile.plants.filter(name__iexact=name).exclude(pk=plant.pk).exists():
            messages.error(request, f'You already have a plant named "{name}". Choose a different name.')
        else:
            plant.name = name
            plant.species = request.POST.get("species", "").strip() or None
            plant.location = request.POST.get("location", "").strip() or None
            plant.watering_interval = int(watering_interval) if watering_interval else None
            plant.notes = request.POST.get("notes", "").strip() or None

            if request.FILES.get("photo"):
                plant.photo = request.FILES["photo"]

            try:
                plant.save()
            except IntegrityError:
                messages.error(request, f'You already have a plant named "{name}". Choose a different name.')
            else:
                messages.success(request, f"Updated {plant.name}.")
                return redirect("plant_detail", plant_id=plant.plant_id)

    return render(request, "accounts/plant_form.html", {"plant": plant})


@login_required
@require_POST
def plant_delete_view(request, plant_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)
    name = plant.name
    plant.delete()
    messages.success(request, f"Deleted {name}.")
    return redirect("plant_list")


@login_required
def plant_detail_view(request, plant_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)
    context = {
        "plant": plant,
        "watering_logs": plant.watering_logs.order_by("-watered_on"),
        "health_logs": plant.health_logs.order_by("-created_at"),
        "health_choices": HealthLog.STATUS_CHOICES,
    }
    return render(request, "accounts/plant_detail.html", context)


@login_required
@require_POST
def watering_log_add_view(request, plant_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)

    if plant.watered_today():
        messages.error(request, f"{plant.name} has already been logged as watered today.")
        return redirect("plant_detail", plant_id=plant.plant_id)

    note = request.POST.get("note", "").strip()
    WateringLog.objects.create(plant=plant, note=note or None)
    plant.last_watered_on = timezone.now()
    plant.save(update_fields=["last_watered_on"])
    messages.success(request, "Watering logged.")
    return redirect("plant_detail", plant_id=plant.plant_id)


@login_required
@require_POST
def watering_log_delete_view(request, plant_id, log_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)
    log = get_object_or_404(WateringLog, pk=log_id, plant=plant)
    log.delete()
    messages.success(request, "Watering log removed.")
    return redirect("plant_detail", plant_id=plant.plant_id)


@login_required
@require_POST
def health_log_add_view(request, plant_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)
    status = request.POST.get("health_status", "").strip()
    photo = request.FILES.get("photo")
    if status:
        HealthLog.objects.create(plant=plant, health_status=status, photo=photo)
        messages.success(request, "Health status logged.")
    return redirect("plant_detail", plant_id=plant.plant_id)


@login_required
@require_POST
def health_log_delete_view(request, plant_id, log_id):
    plant = get_object_or_404(Plant, pk=plant_id, owner=request.user.profile)
    log = get_object_or_404(HealthLog, pk=log_id, plant=plant)
    log.delete()
    messages.success(request, "Health log removed.")
    return redirect("plant_detail", plant_id=plant.plant_id)


@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        if full_name:
            profile.full_name = full_name
            profile.save(update_fields=["full_name"])
            messages.success(request, "Profile updated.")
            return redirect("profile")
        messages.error(request, "Full name cannot be empty.")
    return render(request, "accounts/profile.html", {"profile": profile})