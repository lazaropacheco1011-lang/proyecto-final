from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Tecnico, User


@receiver(post_save, sender=User)
def crear_perfil_tecnico(sender, instance, created, **kwargs):
    """Crea automáticamente el perfil de técnico cuando el rol lo requiere."""
    if instance.role == User.Roles.TECNICO:
        Tecnico.objects.get_or_create(
            user=instance,
            defaults={'telefono': instance.phone},
        )
