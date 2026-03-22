# Fixture Mundial 2026 — Datos en vivo

Este repositorio contiene los resultados actualizados de los partidos del Mundial 2026.

La app **Fixture Mundial 2026** consulta este archivo para mantener los resultados al día automáticamente.

## Formato

```json
{
  "updated": "2026-06-11T22:00:00Z",
  "results": [
    {"id": 1, "home": 2, "away": 1},
    {"id": 2, "home": 0, "away": 0}
  ]
}
```

- `id`: ID del partido (1-104)
- `home`: goles del equipo local
- `away`: goles del equipo visitante

## Actualización

Los resultados se actualizan manualmente o mediante GitHub Actions durante el torneo (junio-julio 2026).
