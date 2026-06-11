create table if not exists experiment_manifests (
    id text primary key,
    title text not null,
    description text not null,
    subject text not null,
    grade integer not null,
    chapter text,
    topic text,
    difficulty text not null,
    supported_modes text not null,
    required_sensors text not null,
    estimated_duration_minutes integer,
    tags text not null,
    created_at text not null,
    updated_at text not null
);

create table if not exists experiment_templates (
    id text primary key,
    title text not null,
    category text not null,
    manifest_id text not null,
    manifest_snapshot text not null,
    created_at text,
    updated_at text,
    foreign key (manifest_id) references experiment_manifests(id)
);

create table if not exists experiment_runs (
    run_id text primary key,
    experiment_id text not null,
    student_id text not null,
    execution_mode text not null,
    status text not null,
    started_at text,
    completed_at text,
    duration_ms integer,
    created_at text,
    updated_at text
);

create table if not exists experiment_run_events (
    event_id text primary key,
    run_id text not null,
    event_type text not null,
    timestamp text not null,
    payload_json text,
    foreign key (run_id) references experiment_runs(run_id)
);

create table if not exists experiment_results (
    result_id text primary key,
    run_id text not null,
    completion_percentage real,
    score real,
    observations_json text,
    measurements_json text,
    notes text,
    created_at text,
    foreign key (run_id) references experiment_runs(run_id)
);

create index if not exists idx_experiment_runs_student
on experiment_runs(student_id, created_at desc);

create index if not exists idx_experiment_runs_experiment
on experiment_runs(experiment_id, status);

create index if not exists idx_experiment_run_events_run
on experiment_run_events(run_id, timestamp);

create index if not exists idx_experiment_results_run
on experiment_results(run_id);
