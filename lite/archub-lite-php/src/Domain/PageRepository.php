<?php

declare(strict_types=1);

namespace ArcHub\Lite\Domain;

/**
 * Port for content persistence. Implemented by the PostgreSQL adapter (production)
 * and an in-memory adapter (tests / no-database trial).
 */
interface PageRepository
{
    /** @return list<Page> */
    public function all(): array;

    /** @return list<Page> */
    public function published(): array;

    public function find(int $id): ?Page;

    public function findBySlug(string $slug): ?Page;

    public function slugExists(string $slug, ?int $exceptId = null): bool;

    /** Persist a new or existing page; returns the stored page (with id). */
    public function save(Page $page): Page;

    public function delete(int $id): void;

    /**
     * Full-text search over published content.
     *
     * @return list<array{page:Page,rank:float,excerpt:string}>
     */
    public function search(string $query, int $limit = 20): array;
}
