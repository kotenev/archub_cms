<?php

declare(strict_types=1);

namespace ArcHub\Lite\Infrastructure;

use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\PageRepository;
use PDO;

/**
 * PostgreSQL-backed content repository.
 */
final class PdoPageRepository implements PageRepository
{
    public function __construct(private PDO $pdo)
    {
    }

    public function all(): array
    {
        $rows = $this->pdo->query(
            'SELECT * FROM archub_lite_pages ORDER BY coalesce(parent_id, 0), sort, id'
        )->fetchAll();
        return array_map(Page::fromRow(...), $rows);
    }

    public function published(): array
    {
        $rows = $this->pdo->query(
            "SELECT * FROM archub_lite_pages WHERE status = 'published'
             ORDER BY coalesce(parent_id, 0), sort, id"
        )->fetchAll();
        return array_map(Page::fromRow(...), $rows);
    }

    public function find(int $id): ?Page
    {
        $stmt = $this->pdo->prepare('SELECT * FROM archub_lite_pages WHERE id = :id');
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch();
        return $row ? Page::fromRow($row) : null;
    }

    public function findBySlug(string $slug): ?Page
    {
        $stmt = $this->pdo->prepare('SELECT * FROM archub_lite_pages WHERE slug = :slug');
        $stmt->execute(['slug' => $slug]);
        $row = $stmt->fetch();
        return $row ? Page::fromRow($row) : null;
    }

    public function slugExists(string $slug, ?int $exceptId = null): bool
    {
        $sql = 'SELECT 1 FROM archub_lite_pages WHERE slug = :slug';
        $params = ['slug' => $slug];
        if ($exceptId !== null) {
            $sql .= ' AND id <> :id';
            $params['id'] = $exceptId;
        }
        $stmt = $this->pdo->prepare($sql);
        $stmt->execute($params);
        return (bool) $stmt->fetchColumn();
    }

    public function save(Page $page): Page
    {
        if ($page->id === null) {
            $stmt = $this->pdo->prepare(
                'INSERT INTO archub_lite_pages (slug, parent_id, title, body, status, sort, published_at)
                 VALUES (:slug, :parent_id, :title, :body, :status, :sort, :published_at)
                 RETURNING *'
            );
        } else {
            $stmt = $this->pdo->prepare(
                'UPDATE archub_lite_pages
                    SET slug = :slug, parent_id = :parent_id, title = :title, body = :body,
                        status = :status, sort = :sort, published_at = :published_at, updated_at = now()
                  WHERE id = :id
                 RETURNING *'
            );
        }
        $params = [
            'slug' => $page->slug,
            'parent_id' => $page->parentId,
            'title' => $page->title,
            'body' => $page->body,
            'status' => $page->status,
            'sort' => $page->sort,
            'published_at' => $page->isPublished() ? ($page->publishedAt ?? date('c')) : null,
        ];
        if ($page->id !== null) {
            $params['id'] = $page->id;
        }
        $stmt->execute($params);
        return Page::fromRow($stmt->fetch());
    }

    public function delete(int $id): void
    {
        $stmt = $this->pdo->prepare('DELETE FROM archub_lite_pages WHERE id = :id');
        $stmt->execute(['id' => $id]);
    }

    public function search(string $query, int $limit = 20): array
    {
        $query = trim($query);
        if ($query === '') {
            return [];
        }
        // The query text is bound once via a CTE so this works with real
        // (non-emulated) prepared statements, where pdo_pgsql forbids reusing
        // the same named placeholder.
        $stmt = $this->pdo->prepare(
            "WITH q AS (SELECT websearch_to_tsquery('simple', :q) AS query)
             SELECT p.*,
                    ts_rank(p.tsv, q.query) AS rank,
                    ts_headline('simple', p.body, q.query,
                                'MaxWords=30, MinWords=10, ShortWord=2') AS excerpt
               FROM archub_lite_pages p, q
              WHERE p.status = 'published'
                AND p.tsv @@ q.query
              ORDER BY rank DESC
              LIMIT :limit"
        );
        $stmt->bindValue('q', $query);
        $stmt->bindValue('limit', $limit, PDO::PARAM_INT);
        $stmt->execute();

        $results = [];
        foreach ($stmt->fetchAll() as $row) {
            $results[] = [
                'page' => Page::fromRow($row),
                'rank' => (float) $row['rank'],
                'excerpt' => (string) $row['excerpt'],
            ];
        }
        return $results;
    }
}
