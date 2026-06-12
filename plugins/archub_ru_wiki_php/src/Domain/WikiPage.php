<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin\Domain;

final readonly class WikiPage
{
    public function __construct(
        public string $slug,
        public string $spaceKey,
        public string $title,
        public string $status,
        public string $owner,
        public array $labels,
        public string $body,
        public int $version,
        public string $updatedAt,
    ) {
    }

    public function toArray(): array
    {
        return [
            'slug' => $this->slug,
            'space_key' => $this->spaceKey,
            'title' => $this->title,
            'status' => $this->status,
            'owner' => $this->owner,
            'labels' => $this->labels,
            'body' => $this->body,
            'version' => $this->version,
            'updated_at' => $this->updatedAt,
        ];
    }
}
