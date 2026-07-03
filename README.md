## Qp Supplier Front

Front Supplier

### Migración - Conflictos de custom fields entre apps

Si al migrar aparece el error:

```
pymysql.err.OperationalError: (1292, "Truncated incorrect INTEGER value: 'Non-Inventory'")
```

Es porque el custom field `qp_type` sobre `Item` está definido como `Int` en `tabCustom Field` pero hay datos string en la tabla.

**Solución:** antes de migrar, actualizar el fieldtype a `Data`:

```sql
UPDATE `tabCustom Field` SET fieldtype = 'Data' WHERE name = 'Item-qp_type';
```

Luego ejecutar:

```bash
bench clear-cache && bench migrate
```

Esto ocurre porque Frappe **no actualiza** el `fieldtype` de un custom field existente al leer los archivos `custom/*.json`. Si cambias el fieldtype en el JSON, debes reflejarlo manualmente en la base de datos.

#### License

MIT