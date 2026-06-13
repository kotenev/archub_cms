<?php

declare(strict_types=1);

namespace ArcHub\Lite\Domain;

/**
 * A lite ITSM service-desk request: the shared-hosting subset of the ArcHub ITSM
 * suite — type, priority and a guarded status lifecycle.
 */
final class ServiceRequest
{
    public const STATUS_OPEN = 'open';
    public const STATUS_IN_PROGRESS = 'in_progress';
    public const STATUS_RESOLVED = 'resolved';
    public const STATUS_CLOSED = 'closed';

    public const TYPES = ['incident', 'service_request', 'question'];
    public const PRIORITIES = ['low', 'medium', 'high', 'urgent'];

    /** Allowed status transitions (the lite workflow state machine). */
    public const TRANSITIONS = [
        self::STATUS_OPEN => [self::STATUS_IN_PROGRESS, self::STATUS_RESOLVED, self::STATUS_CLOSED],
        self::STATUS_IN_PROGRESS => [self::STATUS_RESOLVED, self::STATUS_CLOSED, self::STATUS_OPEN],
        self::STATUS_RESOLVED => [self::STATUS_CLOSED, self::STATUS_IN_PROGRESS],
        self::STATUS_CLOSED => [self::STATUS_OPEN],
    ];

    public function __construct(
        public ?int $id,
        public string $key,
        public string $type,
        public string $summary,
        public string $description,
        public string $status,
        public string $priority,
        public string $requester,
        public ?string $assignee = null,
        public ?string $createdAt = null,
        public ?string $updatedAt = null,
    ) {
    }

    public function canTransitionTo(string $status): bool
    {
        return in_array($status, self::TRANSITIONS[$this->status] ?? [], true);
    }

    /** @return array<string,mixed> */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'key' => $this->key,
            'type' => $this->type,
            'summary' => $this->summary,
            'description' => $this->description,
            'status' => $this->status,
            'priority' => $this->priority,
            'requester' => $this->requester,
            'assignee' => $this->assignee,
            'created_at' => $this->createdAt,
            'updated_at' => $this->updatedAt,
            'next_transitions' => self::TRANSITIONS[$this->status] ?? [],
        ];
    }

    /** @param array<string,mixed> $row */
    public static function fromRow(array $row): self
    {
        return new self(
            isset($row['id']) ? (int) $row['id'] : null,
            (string) $row['key'],
            (string) $row['type'],
            (string) $row['summary'],
            (string) ($row['description'] ?? ''),
            (string) $row['status'],
            (string) $row['priority'],
            (string) $row['requester'],
            isset($row['assignee']) && $row['assignee'] !== null ? (string) $row['assignee'] : null,
            isset($row['created_at']) ? (string) $row['created_at'] : null,
            isset($row['updated_at']) ? (string) $row['updated_at'] : null,
        );
    }
}
