from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("admin-dashboard/", views.admin_dashboard_view, name="admin_dashboard"),
    path("manage/users/", views.manage_users_view, name="manage_users"),
    path("manage/users/<int:user_id>/edit/", views.edit_user_view, name="edit_user"),
    path("manage/users/<int:user_id>/toggle-active/", views.toggle_active_view, name="toggle_active"),
    path("manage/users/<int:user_id>/toggle-staff/", views.toggle_staff_view, name="toggle_staff"),
    path("manage/users/<int:user_id>/delete/", views.delete_user_view, name="delete_user"),

    path("profile/", views.profile_view, name="profile"),

    path("plants/", views.plant_list_view, name="plant_list"),
    path("plants/add/", views.plant_create_view, name="plant_create"),
    path("plants/<uuid:plant_id>/", views.plant_detail_view, name="plant_detail"),
    path("plants/<uuid:plant_id>/edit/", views.plant_edit_view, name="plant_edit"),
    path("plants/<uuid:plant_id>/delete/", views.plant_delete_view, name="plant_delete"),

    path("plants/<uuid:plant_id>/watering/add/", views.watering_log_add_view, name="watering_log_add"),
    path("plants/<uuid:plant_id>/watering/<uuid:log_id>/delete/", views.watering_log_delete_view, name="watering_log_delete"),

    path("plants/<uuid:plant_id>/health/add/", views.health_log_add_view, name="health_log_add"),
    path("plants/<uuid:plant_id>/health/<uuid:log_id>/delete/", views.health_log_delete_view, name="health_log_delete"),
]