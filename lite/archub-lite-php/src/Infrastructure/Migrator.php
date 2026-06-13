<?php

declare(strict_types=1);

namespace ArcHub\Lite\Infrastructure;

use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\ServiceRequest;
use PDO;

/**
 * Idempotent PostgreSQL schema bootstrap. Designed for shared hosting: it runs on
 * first request (or via bin/migrate.php) using only `CREATE … IF NOT EXISTS`, so
 * there is no separate migration tool to install.
 *
 * Full-text search uses a generated `tsvector` column + GIN index (PostgreSQL 12+),
 * matching the FTS capability of the full ArcHub platform.
 */
final class Migrator
{
    public function __construct(private PDO $pdo)
    {
    }

    public function migrate(bool $seedDemo = true): void
    {
        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS archub_lite_pages (
                id          BIGSERIAL PRIMARY KEY,
                slug        TEXT NOT NULL UNIQUE,
                parent_id   BIGINT REFERENCES archub_lite_pages(id) ON DELETE SET NULL,
                title       TEXT NOT NULL,
                body        TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'draft',
                sort        INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                published_at TIMESTAMPTZ,
                tsv         tsvector GENERATED ALWAYS AS (
                                to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, ''))
                            ) STORED
            );
            SQL);
        $this->pdo->exec('CREATE INDEX IF NOT EXISTS archub_lite_pages_tsv_idx ON archub_lite_pages USING GIN (tsv);');
        $this->pdo->exec('CREATE INDEX IF NOT EXISTS archub_lite_pages_parent_idx ON archub_lite_pages (parent_id);');
        $this->pdo->exec('CREATE INDEX IF NOT EXISTS archub_lite_pages_status_idx ON archub_lite_pages (status);');

        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS archub_lite_requests (
                id          BIGSERIAL PRIMARY KEY,
                key         TEXT NOT NULL UNIQUE,
                type        TEXT NOT NULL DEFAULT 'incident',
                summary     TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'open',
                priority    TEXT NOT NULL DEFAULT 'medium',
                requester   TEXT NOT NULL DEFAULT 'anonymous',
                assignee    TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            SQL);
        $this->pdo->exec('CREATE INDEX IF NOT EXISTS archub_lite_requests_status_idx ON archub_lite_requests (status);');

        if ($seedDemo) {
            $this->seed();
        }
    }

    private function seed(): void
    {
        $count = (int) $this->pdo->query('SELECT count(*) FROM archub_lite_pages')->fetchColumn();
        if ($count > 0) {
            return;
        }

        $insert = $this->pdo->prepare(
            'INSERT INTO archub_lite_pages (slug, parent_id, title, body, status, sort, published_at)
             VALUES (:slug, :parent_id, :title, :body, :status, :sort, now())'
        );
        $home = [
            'slug' => 'welcome',
            'parent_id' => null,
            'title' => 'Welcome to ArcHub Lite',
            'body' => "ArcHub Lite is the shared-hosting edition of the ArcHub platform.\n\n"
                . "It runs on PHP-FPM + nginx + PostgreSQL with no Composer, no Docker and no daemons — "
                . "a single folder you upload over FTP. It ships a headless CMS with a JSON delivery API, "
                . "PostgreSQL full-text search, and a lite ITIL service desk.",
            'status' => Page::STATUS_PUBLISHED,
            'sort' => 0,
        ];
        $insert->execute($home);
        $homeId = (int) $this->pdo->lastInsertId('archub_lite_pages_id_seq');

        $insert->execute([
            'slug' => 'getting-started',
            'parent_id' => $homeId,
            'title' => 'Getting Started',
            'body' => "Edit config.php with your PostgreSQL credentials and an admin password hash, "
                . "point your nginx document root at public/, and open the site. The schema is created "
                . "automatically on first request.",
            'status' => Page::STATUS_PUBLISHED,
            'sort' => 1,
        ]);
        $insert->execute([
            'slug' => 'delivery-api',
            'parent_id' => $homeId,
            'title' => 'Delivery API',
            'body' => "Consume published content as JSON: GET /api/content/tree, "
                . "/api/content/{slug} and /api/search?q=... — ideal for a headless frontend.",
            'status' => Page::STATUS_PUBLISHED,
            'sort' => 2,
        ]);

        $req = $this->pdo->prepare(
            'INSERT INTO archub_lite_requests (key, type, summary, description, status, priority, requester)
             VALUES (:key, :type, :summary, :description, :status, :priority, :requester)'
        );
        $req->execute([
            'key' => 'REQ-1',
            'type' => 'service_request',
            'summary' => 'Provision a new editor account',
            'description' => 'Please create a CMS editor login for the marketing team.',
            'status' => ServiceRequest::STATUS_OPEN,
            'priority' => 'medium',
            'requester' => 'demo@example.com',
        ]);
    }
}
