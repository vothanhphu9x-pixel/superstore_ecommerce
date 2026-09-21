"""Chạy bên trong `odoo-bin shell`; biến `env` do Odoo cung cấp."""

import superstore_data_generator as generator


class LocalOdooAPI:
    """Adapter nhỏ để repair dùng cùng interface với XML-RPC generator."""

    def create(self, model, values):
        records = env[model].create(values)
        return records.ids if isinstance(values, list) else records.id

    def write(self, model, ids, values):
        return env[model].browse(ids).write(values)


api = LocalOdooAPI()
pg = generator.PG()
try:
    context = generator.load_context(pg, api)
    result = generator.p2c_repair_mart_source_data(api, pg, context)
    env.cr.commit()
    print(result)
except Exception:
    env.cr.rollback()
    pg.rollback()
    raise
finally:
    pg.close()
