# RefriMaster — Convecciones y reglas del proyecto

Reglas permanentes de trabajo. Mantener un historial Git limpio y recuperable,
y proteger los datos y archivos existentes del proyecto.

## Sistema de versiones — Semantic Versioning

El proyecto usa **Semantic Versioning**:

- `v1.0.0` → versión inicial/estable.
- `v1.0.1` → corrección pequeña o bugfix (`PATCH`).
- `v1.1.0` → nueva funcionalidad o cambio importante compatible (`MINOR`).
- `v2.0.0` → cambio mayor que modifica significativamente el funcionamiento (`MAJOR`).

Práctica obligatoria:

1. No crear tags automáticamente: el tag se crea SOLO cuando el usuario aprueba
   explícitamente el número de versión.
2. Antes de proponer una versión:
   - Revisar el último tag existente.
   - Revisar los cambios realizados desde ese tag.
   - Confirmar con el usuario qué número de versión corresponde (`PATCH`,
     `MINOR` o `MAJOR`).
3. Después de la aprobación, crear el tag anotado:

   ```bash
   git tag -a vX.Y.Z -m "Versión X.Y.Z"
   git push origin vX.Y.Z
   ```

4. No borrar ni modificar tags existentes.
5. No reescribir el historial de Git.
6. No hacer `git push --force` ni acciones destructivas sin autorización
   explícita del usuario.

Al cerrar una versión, informar al usuario:

- Versión anterior.
- Nueva versión propuesta.
- Cambios contenidos.
- Tipo (`PATCH`, `MINOR` o `MAJOR`).
- Tag que se creará.
- Confirmación de que no se modificaron las fotos existentes.

## Fotos e imágenes — datos protegidos e inmutables

Las fotos existentes del proyecto son **datos protegidos e inmutables**.

Nunca deben:

- reemplazarse;
- sobrescribirse;
- borrarse;
- moverse;
- renombrarse sin autorización;
- perderse durante seeds, migraciones, deploys o cambios de código.

Antes y después de cambios importantes relacionados con Almacén, seeds,
migraciones o deploys, verificar que las fotos existentes continúan intactas.

## Autorización de operaciones sensibles

No realizar migraciones, deploys, cambios destructivos, creación de tags ni
pushes importantes sin autorización explícita del usuario.

Antes de cualquier cambio que pueda afectar datos, versiones, Git o producción:
diagnosticar, explicar qué se va a hacer y esperar la aprobación del usuario.

## Reglas de commit

- Solo hacer commit cuando el usuario lo solicite explícitamente.
- Incluir únicamente los archivos correspondientes al cambio autorizado.
- No incluir cambios pendientes de tareas anteriores no autorizados.
- Mensajes de commit claros y descriptivos, en el estilo usado por el
  repositorio.