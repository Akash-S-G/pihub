# PIHUB Backend API Reference

This document lists all the API endpoints available in the backend.


## Ai

- **POST** `/ai/chat` - Ai Chat
- **POST** `/ai/tutor` - Ai Tutor
- **POST** `/ai/tutor/debug` - Ai Tutor Debug
- **POST** `/ai/tutor/evaluate` - Ai Tutor Evaluate
- **GET** `/ai/health` - Ai Health

## Analytics

- **GET** `/analytics/student/{student_id}` - Experiment Student Analytics
- **GET** `/analytics/experiment/{experiment_id}` - Experiment Analytics
- **GET** `/analytics/system` - Experiment System Analytics
- **GET** `/analytics/top-experiments` - Experiment Top Analytics

## Api

- **POST** `/api/voice/query` - Voice Query
- **POST** `/api/voice/tts` - Voice Tts
- **POST** `/api/voice/stt` - Voice Stt
- **GET** `/api/voice/audio/{asset_id:path}` - Voice Audio
- **GET** `/api/voice/metrics` - Voice Metrics
- **GET** `/api/v1/pdf/catalog` - Pdf Catalog
- **GET** `/api/v1/pdf/resolve` - Pdf Resolve
- **GET** `/api/v1/pdf/book/{grade}/{subject}` - Pdf Book
- **GET** `/api/v1/pdf/chapter/{chapter_id}/metadata` - Pdf Chapter Metadata
- **GET** `/api/v1/pdf/chapter/{chapter_id}` - Pdf Chapter
- **GET** `/api/v1/pdf/file/{book_id}` - Pdf File

## Chapters

- **GET** `/chapters/{chapter_id}/experiments` - Chapter Experiments

## Classroom

- **POST** `/classroom/sessions` - Classroom Session Create
- **GET** `/classroom/sessions` - Classroom Sessions
- **POST** `/classroom/sessions/{session_id}/assignments` - Classroom Assignment Create
- **GET** `/classroom/sessions/{session_id}/assignments` - Classroom Assignments
- **POST** `/classroom/assignments/{assignment_id}/submit` - Classroom Assignment Submit
- **GET** `/classroom/assignments/{assignment_id}/submissions` - Classroom Assignment Submissions
- **GET** `/classroom/analytics` - Classroom Session Analytics
- **GET** `/classroom` - Classroom Get
- **POST** `/classroom` - Classroom Post

## Content

- **POST** `/content/upload` - Upload Content

## Debug

- **GET** `/debug/curriculum` - Debug Curriculum
- **GET** `/debug/metadata` - Debug Metadata
- **GET** `/debug/chunks` - Debug Chunks
- **POST** `/debug/retrieval` - Debug Retrieval
- **GET** `/debug/similarity` - Debug Similarity
- **GET** `/debug/pack-preview` - Debug Pack Preview

## Demo

- **GET** `/demo/topics` - Demo Topics
- **GET** `/demo` - Demo Index
- **POST** `/demo/tutor` - Demo Tutor

## Devices

- **GET** `/devices` - Devices Get
- **POST** `/devices` - Devices Post

## Discovery

- **GET** `/discovery` - Discovery
- **GET** `/discovery/beacon` - Discovery Beacon

## Experiment-Metrics

- **GET** `/experiment-metrics` - Experiment Metrics

## Experiment-Runs

- **POST** `/experiment-runs` - Experiment Run Create
- **GET** `/experiment-runs/student/{student_id}` - Experiment Runs Student
- **GET** `/experiment-runs/{run_id}` - Experiment Run Get
- **POST** `/experiment-runs/{run_id}/events` - Experiment Run Event
- **POST** `/experiment-runs/{run_id}/complete` - Experiment Run Complete

## Experiment-Templates

- **GET** `/experiment-templates` - Experiment Templates

## Experiments

- **GET** `/experiments` - Experiments Get
- **GET** `/experiments/catalog` - Experiments Catalog
- **GET** `/experiments/search` - Experiments Search
- **GET** `/experiments/{experiment_id}/download` - Experiment Pack Download
- **GET** `/experiments/{experiment_id}/certification` - Experiment Certification
- **GET** `/experiments/{experiment_id}` - Experiment Get

## Flashcards

- **GET** `/flashcards` - Flashcards

## Glossary

- **GET** `/glossary` - Glossary

## Health

- **GET** `/health` - Health

## Ingest

- **POST** `/ingest/textbook` - Ingest Textbook
- **POST** `/ingest/directory` - Ingest Directory

## Metrics

- **GET** `/metrics/tutor` - Tutor Metrics
- **GET** `/metrics/retrieval` - Retrieval Metrics Endpoint

## Packs

- **GET** `/packs` - Packs Get
- **GET** `/packs/sync` - Packs Sync
- **GET** `/packs/catalog` - Packs Catalog
- **GET** `/packs/coverage` - Packs Coverage
- **GET** `/packs/multilingual/plan` - Packs Multilingual Plan
- **GET** `/packs/recommended` - Packs Recommended
- **POST** `/packs/generate` - Packs Generate
- **GET** `/packs/{pack_id}/manifest` - Pack Manifest
- **GET** `/packs/{pack_id}/download` - Pack Download

## Planner

- **POST** `/planner/lesson` - Planner Lesson

## Progress

- **POST** `/progress` - Progress Post
- **GET** `/progress/{student_id}` - Progress Get

## Quiz-Sessions

- **POST** `/quiz-sessions` - Quiz Session Create
- **GET** `/quiz-sessions/student/{student_id}` - Quiz Sessions Student
- **GET** `/quiz-sessions/{quiz_session_id}` - Quiz Session Get
- **POST** `/quiz-sessions/{quiz_session_id}/answer` - Quiz Session Answer

## Quizzes

- **GET** `/quizzes` - Quizzes

## Rag

- **POST** `/rag/search` - Rag Search
- **GET** `/rag/chapter` - Rag Chapter
- **GET** `/rag/subject` - Rag Subject

## Summaries

- **GET** `/summaries` - Summaries

## Sync

- **GET** `/sync` - Sync Get
- **POST** `/sync` - Sync Post

## Tutor

- **GET** `/tutor/capabilities` - Tutor Capabilities

## Upload

- **POST** `/upload` - Upload Content

## Websocket

- **WS** `/api/voice/stream` - Voice Stream Proxy
- **WS** `/voice/stream` - Voice Stream Proxy