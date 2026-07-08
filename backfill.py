from django.contrib.auth.models import User
from accounts.models import Profile

for u in User.objects.all():
    full_name = f"{u.first_name} {u.last_name}".strip() or u.username
    Profile.objects.get_or_create(
        user=u,
        defaults={
            "full_name": full_name,
            "username": u.username,
            "email": u.email or f"{u.username}@placeholder.local",
        },
    )
    print(f"OK: {u.username}")