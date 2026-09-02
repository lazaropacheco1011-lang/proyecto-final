from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.accounts.storage import SupabaseStorage


class User(AbstractUser):
    """Usuario del sistema con rol (RF-01, RF-03, RNF-03)."""

    class Roles(models.TextChoices):
        ADMINISTRADOR = 'administrador', 'Administrador'
        SUPERVISOR = 'supervisor', 'Supervisor'
        TECNICO = 'tecnico', 'Técnico'
        ALMACEN = 'almacen', 'Almacén'
        CLIENTE = 'cliente', 'Cliente'

    email = models.EmailField('correo electrónico', unique=True)
    role = models.CharField(
        'rol',
        max_length=20,
        choices=Roles.choices,
        default=Roles.CLIENTE,
    )
    phone = models.CharField('teléfono', max_length=20, blank=True)
    photo = models.ImageField(
        'foto de perfil',
        upload_to='fotos_perfil/',
        storage=SupabaseStorage(),
        blank=True,
        null=True,
    )

    @property
    def is_administrador(self):
        return self.role == self.Roles.ADMINISTRADOR

    @property
    def is_tecnico(self):
        return self.role == self.Roles.TECNICO

    @property
    def is_cliente(self):
        return self.role == self.Roles.CLIENTE

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-date_joined']

    def __str__(self):
        return self.username

    def role_display(self):
        return self.get_role_display()


class Supervisor(models.Model):
    """Perfil extendido del supervisor — vincula supervisor con sus técnicos."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil_supervisor',
        verbose_name='usuario',
    )
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Supervisor'
        verbose_name_plural = 'Supervisores'
        ordering = ['user__first_name']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} (Supervisor)'


class Tecnico(models.Model):
    """Perfil extendido del técnico (RF-09)."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil_tecnico',
        verbose_name='usuario',
    )
    supervisor = models.ForeignKey(
        Supervisor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tecnicos',
        verbose_name='supervisor',
    )
    especialidad = models.CharField('especialidad', max_length=150, blank=True)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    direccion = models.CharField('dirección', max_length=255, blank=True)
    disponible = models.BooleanField('disponible', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Técnico'
        verbose_name_plural = 'Técnicos'
        ordering = ['user__first_name']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.user.role})'


class PasswordResetToken(models.Model):
    """Token de un solo uso para restablecer la contraseña (recuperación).

    Solo se guarda el hash (SHA-256) del token: la BD nunca contiene el
    enlace de recuperación en claro.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tokens_recuperacion',
        verbose_name='usuario',
    )
    token_hash = models.CharField('hash del token', max_length=64, db_index=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    expires_at = models.DateTimeField('expira el')
    used_at = models.DateTimeField('usado el', null=True, blank=True)

    class Meta:
        verbose_name = 'Token de recuperación'
        verbose_name_plural = 'Tokens de recuperación'
        ordering = ['-created_at']

    def __str__(self):
        return f'Token de {self.user} (expira {self.expires_at:%Y-%m-%d %H:%M})'

    @property
    def expirado(self):
        return self.expires_at <= timezone.now()

    @property
    def usado(self):
        return self.used_at is not None

    def es_valido(self):
        """Válido si no fue usado y no ha expirado."""
        return not self.usado and not self.expirado
