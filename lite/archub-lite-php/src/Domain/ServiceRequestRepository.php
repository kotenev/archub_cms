<?php

declare(strict_types=1);

namespace ArcHub\Lite\Domain;

/**
 * Port for service-desk persistence.
 */
interface ServiceRequestRepository
{
    /**
     * @param array{status?:string,type?:string,assignee?:string} $filters
     * @return list<ServiceRequest>
     */
    public function all(array $filters = []): array;

    public function findByKey(string $key): ?ServiceRequest;

    /** Persist a new request, allocating its REQ-<n> key; returns the stored request. */
    public function create(ServiceRequest $request): ServiceRequest;

    public function update(ServiceRequest $request): ServiceRequest;

    /** @return array<string,int> counts keyed by status, plus "total" and "open". */
    public function counts(): array;
}
