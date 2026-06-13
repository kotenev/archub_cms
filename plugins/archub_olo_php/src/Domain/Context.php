<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin\Domain;

/**
 * A GTD context — the tool, place or person required to act on a task
 * (e.g. @calls, @errands, @computer). Tasks may belong to several contexts.
 */
final readonly class Context
{
    public function __construct(
        public string $key,
        public string $name,
        public string $icon,
        public string $color,
    ) {
    }

    public function toArray(): array
    {
        return [
            'key' => $this->key,
            'name' => $this->name,
            'icon' => $this->icon,
            'color' => $this->color,
        ];
    }
}
