# REFRIMASTE — Backend API

Sistema de administración de instalación de equipos de refrigeración.
API REST construida con **Django + Django REST Framework + JWT** (SimpleJWT), documentada con **drf-spectacular** (Swagger/OpenAPI).

## Requisitos

- Python 3.12+
- `venv` con dependencias instaladas (ver `requirements.txt`)

## Instalación

```powershell
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2. Configurar variables de entorno
Copy-Item .env.example .env

# 3. Aplicar migraciones
.venv\Scripts\python.exe manage.py migrate

# 4. (Opcional) Cargar datos de prueba
.venv\Scripts\python.exe manage.py seed_data

# 5. Crear superusuario (si no usaste seed_data)
.venv\Scripts\python.exe manage.py createsuperuser

# 6. Ejecutar el servidor
.venv\Scripts\python.exe manage.py runserver
```

## Datos de prueba

`python manage.py seed_data` crea usuarios con contraseña `Refrimaste2026!`:

| Usuario    | Rol          | Nota                          |
|------------|--------------|-------------------------------|
| `admin`    | administrador| Superusuario (acceso a /admin/)|
| `supervisor`| supervisor   |                               |
| `tecnico1` | tecnico      |                               |
| `tecnico2` | tecnico      |                               |
| `almacen`  | almacen      | Gestiona materiales/inventario|
| `cliente1` | cliente      | María López                   |
| `cliente2` | cliente      | Frío Norte S.A.S.             |

`seed_data --flush` vacía la base de datos y la vuelve a poblar.

## Autenticación (JWT)

- `POST /api/auth/login/` → `{ "access": "...", "refresh": "..." }`
- `POST /api/auth/refresh/` → nuevo `access` (y `refresh` si está rotado)
- `POST /api/auth/logout/` → invalida el refresh (lista negra)
- `GET /api/auth/me/` → perfil del usuario autenticado
- `POST /api/auth/register/` → registro público de clientes

Todos los endpoints protegidos requieren el header:

```
Authorization: Bearer <access_token>
```

## Endpoints principales

| Recurso                | Ruta                                  |
|------------------------|---------------------------------------|
| Usuarios / roles       | `/api/usuarios/`, `/api/usuarios/roles/`, `/api/tecnicos/` |
| Clientes / direcciones | `/api/clientes/`, `/api/direcciones/` |
| Solicitudes            | `/api/solicitudes/`                   |
| Equipos                | `/api/tipos-equipo/`, `/api/equipos/` |
| Instalaciones          | `/api/instalaciones/`, `.../agenda/`, `.../proximos/` |
| Órdenes de servicio    | `/api/servicios/`, `.../{id}/materiales/`, `.../{id}/historial/`, `.../pendientes/` |
| Materiales e inventario| `/api/materiales/`, `.../stock_bajo/`, `.../{id}/entrada/`, `/api/movimientos/` |
| Mantenimientos         | `/api/mantenimientos/`, `.../proximos/`, `.../historial/` |
| Cotizaciones           | `/api/cotizaciones/`                  |
| Pagos / facturas       | `/api/pagos/`, `/api/facturas/`       |
| Evidencias             | `/api/evidencias/`                    |
| Evaluaciones           | `/api/evaluaciones/`                  |
| Notificaciones         | `/api/notificaciones/`                |
| Auditoría              | `/api/auditoria/`                     |
| Dashboard / reportes   | `/api/dashboard/...`, `/api/reportes/...` |
| Documentación          | `/api/docs/` (Swagger), `/api/schema/` (OpenAPI) |

## Reglas de negocio implementadas

- **RN-01** Toda instalación debe estar asociada a un cliente.
- **RN-02** Debe asignarse un técnico antes de iniciar (instalación u orden).
- **RN-03** Un técnico no debe tener dos instalaciones en el mismo horario.
- **RN-04** No se finaliza una orden sin diagnóstico, trabajo realizado u observaciones.
- **RN-05** No se finaliza una instalación sin evidencia fotográfica.
- **RN-06** Los materiales descontados del inventario se registran y validan el stock.
- **RN-07** Una orden/instalación cancelada no puede marcarse como finalizada.
- **RN-08** Solo el administrador puede eliminar registros.
- **RN-09** Historial completo de cambios de estado de las órdenes.
- **RN-10** Las evaluaciones solo se permiten sobre servicios finalizados.

## Base de datos

SQLite por defecto (configurable desde `.env`). Para PostgreSQL:

```
DB_ENGINE=postgres
DB_NAME=refrimaste
DB_USER=postgres
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
```

## Configuración del frontend

- **CORS**: por defecto `CORS_ALLOW_ALL_ORIGINS=True`. Para producción, definir
  `CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:4200` (y `CORS_ALLOW_ALL_ORIGINS=False`).
- **JWT**: la expiración del access token se configura con `ACCESS_TOKEN_MINUTES`
  (por defecto 60 minutos).

## Pruebas

El smoke test integral recorre todos los módulos y reglas de negocio:

```powershell
Get-Content scripts\smoke_test.py -Raw | .venv\Scripts\python.exe manage.py shell
```

## Estructura del proyecto

```
backend/
├── manage.py
├── config/                  # settings, urls, wsgi/asgi
├── .env / .env.example
├── requirements.txt
├── scripts/
│   └── smoke_test.py
└── apps/
    ├── core/                # utilidades, permisos, auditoría, seed_data
    ├── accounts/            # usuarios, roles, autenticación JWT
    ├── clientes/
    ├── solicitudes/
    ├── equipos/
    ├── instalaciones/
    ├── servicios/           # órdenes de trabajo, materiales usados, historial
    ├── mantenimientos/
    ├── materiales/          # inventario y movimientos
    ├── cotizaciones/
    ├── pagos/               # pagos y facturas
    ├── notificaciones/
    ├── evaluaciones/
    └── reportes/            # dashboard y reportes
```
