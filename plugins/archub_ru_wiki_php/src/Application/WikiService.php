<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin\Application;

use ArcHub\WikiPlugin\Infrastructure\SeedWikiRepository;

final readonly class WikiService
{
    public function __construct(private SeedWikiRepository $repository)
    {
    }

    public function overview(): array
    {
        return [
            'product' => 'ArcHub.ru Enterprise Wiki',
            'spaces_total' => count($this->spaces()),
            'pages_total' => count($this->pages()),
            'diagrams_total' => count($this->diagrams()),
            'features' => [
                'spaces',
                'page_tree',
                'drawio_mxfile',
                'macros',
                'search',
                'graph',
                'audit',
                'templates',
                'rbac',
            ],
        ];
    }

    public function spaces(): array
    {
        return array_map(static fn ($space) => $space->toArray(), $this->repository->spaces());
    }

    public function pages(): array
    {
        return array_map(static fn ($page) => $page->toArray(), $this->repository->pages());
    }

    public function page(string $slug): ?array
    {
        return $this->repository->page($slug)?->toArray();
    }

    public function diagrams(): array
    {
        return array_map(static fn ($diagram) => $diagram->toArray(), $this->repository->diagrams());
    }

    public function diagram(string $id): ?array
    {
        return $this->repository->diagram($id)?->toArray();
    }

    public function search(string $query): array
    {
        $clean = strtolower(trim($query));
        $items = [];
        foreach ($this->repository->pages() as $page) {
            $haystack = strtolower($page->title . ' ' . $page->body . ' ' . implode(' ', $page->labels));
            if ($clean === '' || str_contains($haystack, $clean)) {
                $items[] = [
                    'slug' => $page->slug,
                    'title' => $page->title,
                    'excerpt' => substr(strip_tags($page->body), 0, 180),
                    'space' => $page->spaceKey,
                    'score' => $clean === '' ? 0.5 : 1.0,
                ];
            }
        }
        return ['query' => $query, 'items' => $items, 'total' => count($items)];
    }

    public function graph(): array
    {
        return [
            'nodes' => array_map(
                static fn ($page) => ['id' => $page->slug, 'label' => $page->title, 'space' => $page->spaceKey],
                $this->repository->pages()
            ),
            'edges' => $this->repository->links(),
        ];
    }
}
