<?php

declare(strict_types=1);

namespace ArcHub\Lite\Infrastructure;

use ArcHub\Lite\Domain\ServiceRequest;
use ArcHub\Lite\Domain\ServiceRequestRepository;

/**
 * In-memory service-desk repository for tests and a zero-database trial.
 */
final class InMemoryServiceRequestRepository implements ServiceRequestRepository
{
    /** @var array<int,ServiceRequest> */
    private array $requests = [];
    private int $nextId = 1;

    public function __construct(bool $seedDemo = false)
    {
        if ($seedDemo) {
            $this->create(new ServiceRequest(null, '', 'service_request',
                'Provision a new editor account', 'Create a CMS editor login.',
                ServiceRequest::STATUS_OPEN, 'medium', 'demo@example.com'));
        }
    }

    public function all(array $filters = []): array
    {
        $items = array_values($this->requests);
        foreach (['status', 'type', 'assignee'] as $field) {
            if (!empty($filters[$field])) {
                $items = array_values(array_filter(
                    $items,
                    static fn (ServiceRequest $r) => $r->{$field === 'assignee' ? 'assignee' : $field} === $filters[$field]
                ));
            }
        }
        usort($items, static fn ($a, $b) => ($b->id ?? 0) <=> ($a->id ?? 0));
        return $items;
    }

    public function findByKey(string $key): ?ServiceRequest
    {
        foreach ($this->requests as $request) {
            if ($request->key === $key) {
                return $request;
            }
        }
        return null;
    }

    public function create(ServiceRequest $request): ServiceRequest
    {
        $request->id = $this->nextId++;
        $request->key = 'REQ-' . $request->id;
        $request->createdAt = date('c');
        $request->updatedAt = date('c');
        $this->requests[$request->id] = $request;
        return $request;
    }

    public function update(ServiceRequest $request): ServiceRequest
    {
        $request->updatedAt = date('c');
        if ($request->id !== null) {
            $this->requests[$request->id] = $request;
        }
        return $request;
    }

    public function counts(): array
    {
        $counts = ['total' => 0, 'open' => 0];
        foreach ($this->requests as $request) {
            $counts[$request->status] = ($counts[$request->status] ?? 0) + 1;
            $counts['total']++;
        }
        $counts['open'] = ($counts[ServiceRequest::STATUS_OPEN] ?? 0)
            + ($counts[ServiceRequest::STATUS_IN_PROGRESS] ?? 0);
        return $counts;
    }
}
