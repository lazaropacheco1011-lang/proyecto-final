from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Supervisor = apps.get_model('accounts', 'Supervisor')

    existing = set(
        Supervisor.objects.values_list('user_id', flat=True)
    )
    for user in User.objects.filter(role='supervisor').exclude(pk__in=existing):
        Supervisor.objects.get_or_create(
            user=user,
            defaults={'telefono': user.phone},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_supervisor_tecnico_supervisor'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
