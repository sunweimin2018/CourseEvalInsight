# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CourseEvalInsight — a course evaluation analytics platform for multi-Excel data analysis and report generation. Backend is Django 6.0, frontend is Vue 3 + TypeScript + Vite. The full product spec is at `docs/design/多Excel数据动态生成数据分析报告系统-PRD需求文档（Vue3+Django、适配Claude Code开发）.md`.

Status: project scaffolded, no commits yet, no app logic implemented.

## Repository Layout

```
course_eval/          # Django 6.0 backend (Python >= 3.12)
  course_eval/        # Project package (settings, urls, wsgi)
    apps/
      course/         # Course data app (scaffolded, empty)
      evaluate/       # Evaluation data app (scaffolded, empty)
      report/         # Reporting/analytics app (scaffolded, empty)
frontend/             # Vue 3 + Vite 8 SPA (Node >= 20.19)
data/                 # Raw test data (Excel files, docs)
docs/
  design/             # PRD and design documents
  templates/          # Report templates (.docx)
```

## Backend Commands

```bash
cd course_eval
uv run python manage.py <command>   # Django management (uv manages the venv)
uv run python manage.py runserver   # Start dev server on :8000
uv run python manage.py migrate     # Apply migrations
uv run python manage.py makemigrations  # Create new migrations
uv run python manage.py test        # Run all tests
uv run python manage.py test apps.course.tests  # Run a single app's tests
```

Dependencies are managed with [uv](https://docs.astral.sh/uv/). Add packages with `uv add <package>`.

## Frontend Commands

```bash
cd frontend
npm run dev           # Vite dev server with HMR
npm run build         # vue-tsc type-check then vite build
npm run preview       # Preview production build locally
```

The `build` script runs `vue-tsc -b && vite build` — type-checking happens as part of the build pipeline (flags in tsconfig: `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`). Prettier formatting is applied editor-side via VS Code's `formatOnSave`.

## Architecture Notes

- **Backend**: Three Django apps (`course`, `evaluate`, `report`) are scaffolded with standard `apps.py` configs but contain no models, views, or URL configs. None are registered in `INSTALLED_APPS` yet. Settings currently use SQLite, but the target database is MySQL 8 (see Database Configuration below).
- **Frontend**: Vue 3 SPA (TypeScript, Vite). Currently vanilla Vite scaffold — only `vue` is installed. The PRD prescribes additional dependencies: Element Plus, Pinia, Axios, ECharts, xlsx, vue-router, SCSS. None of these are installed yet.
- The backend and frontend are independent — no API client or proxy is configured yet.
- **PRD planned architecture**: The product spec calls for `apps/user` (auth), `apps/excel` (upload/parse), `apps/analysis` (statistics), and `apps/report` (report generation/export). The currently scaffolded apps (`course`, `evaluate`, `report`) may need to be restructured or replaced per the PRD.

## VS Code Workspace

- **Recommended extension**: Volar (`Vue.volar`) for `.vue` TypeScript support.
- **Format on save**: enabled, using Prettier as default formatter. Config at `frontend/.prettierrc.json`: semicolons off, single quotes, 100 char width.
- **File nesting**: `tsconfig.json`, `vite.config.*`, and `package.json` each nest related files for a cleaner explorer view.

## Database Configuration (MySQL 8 / Docker)

Target database is MySQL 8 running in Docker. Settings are in `.env.local` (gitignored):

- Host: `${MYSQL_HOST:-127.0.0.1}`
- Port: `${MYSQL_PORT:-3307}`
- User: `${MYSQL_ROOT_USER:-root}`
- Password: from `MYSQL_ROOT_PASSWORD` in `.env.local`
- Database: `${MYSQL_DATABASE}` (CourseEval)

`settings.py` currently points to SQLite. Switching to MySQL requires reading `.env.local` variables into `DATABASES['default']`.
