<?php

declare(strict_types=1);

namespace ArcHub\Lite\Application;

use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\PageRepository;

/**
 * Content/CMS use cases: the hierarchical tree, draft/publish lifecycle, the
 * headless delivery read model and full-text search.
 */
final readonly class ContentService
{
    public function __construct(private PageRepository $pages)
    {
    }

    // ---- delivery (published) -------------------------------------------

    /** @return list<array<string,mixed>> nested published tree */
    public function publishedTree(): array
    {
        return $this->buildTree($this->pages->published(), null);
    }

    public function publishedPage(string $slug): ?Page
    {
        $page = $this->pages->findBySlug($slug);
        return $page !== null && $page->isPublished() ? $page : null;
    }

    /** @return list<Page> direct published children of a page */
    public function publishedChildren(?int $parentId): array
    {
        return array_values(array_filter(
            $this->pages->published(),
            static fn (Page $p) => $p->parentId === $parentId,
        ));
    }

    /** @return list<array{page:Page,rank:float,excerpt:string}> */
    public function search(string $query, int $limit = 20): array
    {
        return $this->pages->search($query, $limit);
    }

    // ---- authoring ------------------------------------------------------

    /** @return list<Page> */
    public function allPages(): array
    {
        return $this->pages->all();
    }

    public function find(int $id): ?Page
    {
        return $this->pages->find($id);
    }

    /**
     * @return array{ok:bool,page?:Page,error?:string}
     */
    public function createPage(string $title, string $slug, string $body, ?int $parentId, int $sort, bool $publish): array
    {
        $title = trim($title);
        if ($title === '') {
            return ['ok' => false, 'error' => 'title_required'];
        }
        $slug = $slug !== '' ? Page::slugify($slug) : Page::slugify($title);
        if ($this->pages->slugExists($slug)) {
            return ['ok' => false, 'error' => 'slug_taken'];
        }
        $page = new Page(
            null,
            $slug,
            $parentId,
            $title,
            $body,
            $publish ? Page::STATUS_PUBLISHED : Page::STATUS_DRAFT,
            $sort,
        );
        return ['ok' => true, 'page' => $this->pages->save($page)];
    }

    /**
     * @return array{ok:bool,page?:Page,error?:string}
     */
    public function updatePage(int $id, string $title, string $slug, string $body, ?int $parentId, int $sort): array
    {
        $page = $this->pages->find($id);
        if ($page === null) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        $title = trim($title);
        if ($title === '') {
            return ['ok' => false, 'error' => 'title_required'];
        }
        $slug = $slug !== '' ? Page::slugify($slug) : $page->slug;
        if ($this->pages->slugExists($slug, $id)) {
            return ['ok' => false, 'error' => 'slug_taken'];
        }
        if ($parentId === $id) {
            return ['ok' => false, 'error' => 'cannot_parent_to_self'];
        }
        $page->title = $title;
        $page->slug = $slug;
        $page->body = $body;
        $page->parentId = $parentId;
        $page->sort = $sort;
        return ['ok' => true, 'page' => $this->pages->save($page)];
    }

    public function setPublished(int $id, bool $published): ?Page
    {
        $page = $this->pages->find($id);
        if ($page === null) {
            return null;
        }
        $page->status = $published ? Page::STATUS_PUBLISHED : Page::STATUS_DRAFT;
        if (!$published) {
            $page->publishedAt = null;
        }
        return $this->pages->save($page);
    }

    public function deletePage(int $id): void
    {
        $this->pages->delete($id);
    }

    /**
     * @param list<Page> $pages
     * @return list<array<string,mixed>>
     */
    private function buildTree(array $pages, ?int $parentId): array
    {
        $nodes = [];
        foreach ($pages as $page) {
            if ($page->parentId === $parentId) {
                $nodes[] = $page->toArray() + ['children' => $this->buildTree($pages, $page->id)];
            }
        }
        return $nodes;
    }
}
