<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin\Domain;

final readonly class Diagram
{
    public function __construct(
        public string $id,
        public string $title,
        public string $spaceKey,
        public string $mxfile,
        public string $updatedAt,
    ) {
    }

    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'title' => $this->title,
            'space_key' => $this->spaceKey,
            'mxfile' => $this->mxfile,
            'updated_at' => $this->updatedAt,
        ];
    }
}
