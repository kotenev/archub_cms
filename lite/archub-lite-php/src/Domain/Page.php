<?php

declare(strict_types=1);

namespace ArcHub\Lite\Domain;

/**
 * A content node in the lite CMS tree — the shared-hosting subset of the ArcHub
 * content model: hierarchy, slug, draft/published lifecycle and body.
 */
final class Page
{
    public const STATUS_DRAFT = 'draft';
    public const STATUS_PUBLISHED = 'published';

    public function __construct(
        public ?int $id,
        public string $slug,
        public ?int $parentId,
        public string $title,
        public string $body,
        public string $status,
        public int $sort,
        public ?string $createdAt = null,
        public ?string $updatedAt = null,
        public ?string $publishedAt = null,
    ) {
    }

    public function isPublished(): bool
    {
        return $this->status === self::STATUS_PUBLISHED;
    }

    /** @return array<string,mixed> */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'slug' => $this->slug,
            'parent_id' => $this->parentId,
            'title' => $this->title,
            'body' => $this->body,
            'status' => $this->status,
            'published' => $this->isPublished(),
            'sort' => $this->sort,
            'created_at' => $this->createdAt,
            'updated_at' => $this->updatedAt,
            'published_at' => $this->publishedAt,
        ];
    }

    /** @param array<string,mixed> $row */
    public static function fromRow(array $row): self
    {
        return new self(
            isset($row['id']) ? (int) $row['id'] : null,
            (string) $row['slug'],
            isset($row['parent_id']) && $row['parent_id'] !== null ? (int) $row['parent_id'] : null,
            (string) $row['title'],
            (string) ($row['body'] ?? ''),
            (string) $row['status'],
            (int) ($row['sort'] ?? 0),
            isset($row['created_at']) ? (string) $row['created_at'] : null,
            isset($row['updated_at']) ? (string) $row['updated_at'] : null,
            isset($row['published_at']) && $row['published_at'] !== null ? (string) $row['published_at'] : null,
        );
    }

    public static function slugify(string $value): string
    {
        $value = trim($value);
        $value = preg_replace('/[^\p{L}\p{N}]+/u', '-', $value) ?? $value;
        $value = trim($value, '-');
        $lower = mb_strtolower($value, 'UTF-8');
        return $lower === '' ? 'page-' . substr((string) time(), -6) : $lower;
    }
}
