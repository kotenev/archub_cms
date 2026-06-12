<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin\Domain;

final readonly class WikiSpace
{
    public function __construct(
        public string $key,
        public string $name,
        public string $description,
        public string $owner,
        public bool $private,
    ) {
    }

    public function toArray(): array
    {
        return [
            'key' => $this->key,
            'name' => $this->name,
            'description' => $this->description,
            'owner' => $this->owner,
            'private' => $this->private,
        ];
    }
}
