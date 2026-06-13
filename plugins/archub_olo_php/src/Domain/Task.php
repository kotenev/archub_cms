<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Domain;

/**
 * A node in the OurLifeOrganized outline.
 *
 * Mirrors the OLO read model `rm_task`: hierarchy is encoded with a
 * materialised `path` and `depth` (root tasks have path "/" and depth 0;
 * a child has path "<parent_path><id>/" and depth = parent_depth + 1).
 *
 * MyLifeOrganized concepts preserved: a node may be an actionable to-do
 * (a leaf "next action") or a project/folder grouping sub-tasks; each carries
 * an importance and urgency weighting that feed the computed star priority.
 */
final readonly class Task
{
    public const STATUS_ACTIVE = 'ACTIVE';
    public const STATUS_COMPLETED = 'COMPLETED';

    /**
     * @param list<string>     $contexts GTD context keys (e.g. "calls", "errands")
     * @param array{rrule:string,mode:string}|null $recurrence
     */
    public function __construct(
        public string $id,
        public int $userId,
        public ?string $parentId,
        public string $path,
        public int $depth,
        public string $title,
        public string $notes,
        public string $status,
        public bool $todo,
        public int $importance,
        public int $urgency,
        public bool $starred,
        public array $contexts,
        public ?string $startAt,
        public ?string $dueAt,
        public ?string $reminderAt,
        public ?string $completedAt,
        public ?array $recurrence,
        public string $createdAt,
        public string $updatedAt,
    ) {
    }

    public function isCompleted(): bool
    {
        return $this->status === self::STATUS_COMPLETED;
    }

    public function isRoot(): bool
    {
        return $this->parentId === null;
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'user_id' => $this->userId,
            'parent_id' => $this->parentId,
            'path' => $this->path,
            'depth' => $this->depth,
            'title' => $this->title,
            'notes' => $this->notes,
            'status' => $this->status,
            'completed' => $this->isCompleted(),
            'todo' => $this->todo,
            'project' => !$this->todo,
            'importance' => $this->importance,
            'urgency' => $this->urgency,
            'starred' => $this->starred,
            'contexts' => $this->contexts,
            'start_at' => $this->startAt,
            'due_at' => $this->dueAt,
            'reminder_at' => $this->reminderAt,
            'completed_at' => $this->completedAt,
            'recurrence' => $this->recurrence,
            'created_at' => $this->createdAt,
            'updated_at' => $this->updatedAt,
        ];
    }
}
