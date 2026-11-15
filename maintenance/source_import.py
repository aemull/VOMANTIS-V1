"""Read the supplied MySQL dump as data, never execute it against SQLite."""
import hashlib
import re
from collections import Counter
from pathlib import Path
import sqlparse
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from .models import SourceArchive, SourceRecord


def split_values(text):
    parts, start, depth, quote, index = [], 0, 0, None, 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == '\\':
                index += 2
                continue
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    index += 2
                    continue
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
        index += 1
    if quote or depth:
        raise ValueError('SQL tidak seimbang; impor dibatalkan.')
    parts.append(text[start:].strip())
    return parts


def literal(value):
    if value.upper() == 'NULL':
        return None
    if value.startswith("'") and value.endswith("'"):
        text = value[1:-1].replace("''", "'")
        return re.sub(r'\\(.)', lambda m: {'n': '\n', 'r': '\r', 't': '\t', '0': '\0'}.get(m[1], m[1]), text)
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    if re.fullmatch(r'-?\d+\.\d+', value):
        return value  # Preserve decimal precision in JSON; ORM converts for the destination.
    raise ValueError(f'Literal SQL tidak didukung: {value[:80]}')


def parse_source(raw):
    cleaned = sqlparse.format(raw.decode('utf-8-sig'), strip_comments=True)
    schema, rows = {}, []
    for statement in sqlparse.split(cleaned):
        statement = statement.strip().rstrip(';').strip()
        create = re.match(r'CREATE TABLE\s+`?(\w+)`?\s*\(', statement, re.I)
        insert = re.match(r'INSERT INTO\s+`?(\w+)`?\s*(?:\((.*?)\))?\s+VALUES\s*(.*)', statement, re.I | re.S)
        if create:
            definitions = split_values(statement[create.end():statement.rfind(')')])
            columns = []
            for definition in definitions:
                name = definition.split()[0].strip('`')
                if name.upper() not in ['UNIQUE', 'KEY', 'CONSTRAINT', 'PRIMARY', 'INDEX', 'CHECK', 'FOREIGN']:
                    columns.append(name)
            schema[create[1]] = columns
        elif insert:
            table = insert[1]
            columns = [c.strip().strip('`') for c in insert[2].split(',')] if insert[2] else schema[table]
            for group in split_values(insert[3]):
                if not group.startswith('(') or not group.endswith(')'):
                    raise ValueError('Bentuk VALUES tidak didukung.')
                values = [literal(v) for v in split_values(group[1:-1])]
                if len(values) != len(columns):
                    raise ValueError(f'Jumlah kolom tidak cocok pada {table}.')
                rows.append((table, dict(zip(columns, values))))
        elif statement and not re.match(r'(CREATE DATABASE|USE)\b', statement, re.I):
            raise ValueError(f'Pernyataan tidak didukung, tidak ada data yang dilewati: {statement[:80]}')
    return schema, rows


def source_models(schema):
    models = {model._meta.db_table: model for model in apps.get_app_config('maintenance').get_models()}
    for table, columns in schema.items():
        if table not in models:
            raise ValueError(f'Tabel belum dipetakan: {table}')
        fields = {field.column for field in models[table]._meta.fields}
        if set(columns) - fields:
            raise ValueError(f'Kolom belum dipetakan: {table}: {set(columns) - fields}')
    return models


@transaction.atomic
def import_source(path):
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    schema, rows = parse_source(raw)
    models = source_models(schema)
    archive = SourceArchive.objects.filter(sha256=digest).first()
    if archive:
        return archive, False
    counts = {table: 0 for table in schema}
    archive = SourceArchive.objects.create(filename=path.name, sha256=digest, content=raw)
    for table, payload in rows:
        model = models[table]
        fields = {field.column: field for field in model._meta.fields}
        converted = {}
        for column, value in payload.items():
            field = fields[column]
            if field.generated:
                if value is not None:
                    raise ValueError('Nilai kolom turunan eksplisit belum didukung; file tetap tidak diubah.')
                continue
            value = field.target_field.to_python(value) if field.is_relation else field.to_python(value)
            if field.get_internal_type() == 'DateTimeField' and value and timezone.is_naive(value):
                value = timezone.make_aware(value)
            converted[field.attname] = value
        pk_name = model._meta.pk.attname
        existing = model.objects.filter(pk=converted[pk_name]).first() if pk_name in converted else None
        if existing:
            if any(getattr(existing, key) != value for key, value in converted.items()):
                raise ValueError(f'Konflik data {table} PK {existing.pk}; tidak ada data yang ditimpa.')
            obj = existing
        else:
            obj = model.objects.create(**converted)
        counts[table] += 1
        SourceRecord.objects.create(archive=archive, table_name=table, ordinal=counts[table], payload=payload, object_pk=str(obj.pk))
    archive.summary = {'tables': schema, 'counts': counts, 'total_rows': len(rows)}
    archive.save(update_fields=['summary'])
    return archive, True


def verify_archive(archive):
    raw = bytes(archive.content)
    if hashlib.sha256(raw).hexdigest() != archive.sha256:
        raise ValueError('Checksum arsip tidak cocok.')
    schema, rows = parse_source(raw)
    models = source_models(schema)
    counts = Counter()
    for table, payload in rows:
        counts[table] += 1
        record = archive.records.get(table_name=table, ordinal=counts[table])
        if record.payload != payload or not models[table].objects.filter(pk=record.object_pk).exists():
            raise ValueError(f'Data sumber hilang / berubah: {table} baris {counts[table]}')
    if archive.records.count() != len(rows):
        raise ValueError('Jumlah snapshot sumber tidak cocok.')
    return len(schema), len(rows)
