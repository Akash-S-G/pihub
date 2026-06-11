from __future__ import annotations


BUILDER_SQLITE_SCHEMA = """
create table if not exists experiment_manifests (
    id text primary key,
    owner_id text,
    title text,
    description text,
    subject text,
    status text,
    manifest_version text,
    current_revision integer,
    content_hash text,
    manifest_hash text,
    created_at text,
    updated_at text
);

create table if not exists experiment_revisions (
    id text primary key,
    manifest_id text,
    revision integer,
    manifest_json text,
    execution_json text,
    revision_hash text,
    created_at text,
    created_by text,
    foreign key (manifest_id) references experiment_manifests(id)
);

create table if not exists experiment_tags (
    id text primary key,
    manifest_id text,
    tag text,
    foreign key (manifest_id) references experiment_manifests(id)
);

create unique index if not exists idx_builder_manifest_revisions_unique
on experiment_revisions(manifest_id, revision);

create index if not exists idx_builder_manifests_owner
on experiment_manifests(owner_id, updated_at desc);

create index if not exists idx_builder_manifests_status
on experiment_manifests(status, updated_at desc);

create index if not exists idx_builder_manifests_content_hash
on experiment_manifests(content_hash);

create index if not exists idx_builder_tags_manifest
on experiment_tags(manifest_id, tag);
"""
