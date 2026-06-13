<?php

declare(strict_types=1);

namespace ArcHub\Lite\Infrastructure;

use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\PageRepository;

/**
 * In-memory content repository for tests and a zero-database trial. Not for
 * production: state lives only for the current request.
 */
final class InMemoryPageRepository implements PageRepository
{
    /** @var array<int,Page> */
    private array $pages = [];
    private int $nextId = 1;

    public function __construct(bool $seedDemo = false)
    {
        if ($seedDemo) {
            $home = $this->save(new Page(null, 'welcome', null, 'Welcome to ArcHub Lite',
                'Shared-hosting edition of ArcHub: CMS, delivery API, FTS search and a lite service desk.',
                Page::STATUS_PUBLISHED, 0));
            $this->save(new Page(null, 'getting-started', $home->id, 'Getting Started',
                'Edit config.php, point nginx at public/, open the site.', Page::STATUS_PUBLISHED, 1));
            $this->save(new Page(null, 'delivery-api', $home->id, 'Delivery API',
                'Consume published content as JSON via /api/content and /api/search.',
                Page::STATUS_PUBLISHED, 2));
            $this->save(new Page(null, 'draft-note', null, 'A Draft Note',
                'This page is a draft and must not appear in delivery.', Page::STATUS_DRAFT, 3));
        }
    }

    public function all(): array
    {
        $pages = array_values($this->pages);
        usort($pages, $this->order(...));
        return $pages;
    }

    public function published(): array
    {
        return array_values(array_filter($this->all(), static fn (Page $p) => $p->isPublished()));
    }

    public function find(int $id): ?Page
    {
        return $this->pages[$id] ?? null;
    }

    public function findBySlug(string $slug): ?Page
    {
        foreach ($this->pages as $page) {
            if ($page->slug === $slug) {
                return $page;
            }
        }
        return null;
    }

    public function slugExists(string $slug, ?int $exceptId = null): bool
    {
        foreach ($this->pages as $page) {
            if ($page->slug === $slug && $page->id !== $exceptId) {
                return true;
            }
        }
        return false;
    }

    public function save(Page $page): Page
    {
        if ($page->id === null) {
            $page->id = $this->nextId++;
            $page->createdAt ??= date('c');
        }
        $page->updatedAt = date('c');
        if ($page->isPublished() && $page->publishedAt === null) {
            $page->publishedAt = date('c');
        }
        $this->pages[$page->id] = $page;
        return $page;
    }

    public function delete(int $id): void
    {
        unset($this->pages[$id]);
    }

    public function search(string $query, int $limit = 20): array
    {
        $needle = mb_strtolower(trim($query), 'UTF-8');
        if ($needle === '') {
            return [];
        }
        $results = [];
        foreach ($this->published() as $page) {
            $haystack = mb_strtolower($page->title . ' ' . $page->body, 'UTF-8');
            $pos = mb_strpos($haystack, $needle);
            if ($pos === false) {
                continue;
            }
            $titleHit = mb_strpos(mb_strtolower($page->title, 'UTF-8'), $needle) !== false;
            $results[] = [
                'page' => $page,
                'rank' => $titleHit ? 1.0 : 0.5,
                'excerpt' => mb_substr($page->body, 0, 160, 'UTF-8'),
            ];
        }
        usort($results, static fn ($a, $b) => $b['rank'] <=> $a['rank']);
        return array_slice($results, 0, $limit);
    }

    private function order(Page $a, Page $b): int
    {
        return [$a->parentId ?? 0, $a->sort, $a->id ?? 0] <=> [$b->parentId ?? 0, $b->sort, $b->id ?? 0];
    }
}
