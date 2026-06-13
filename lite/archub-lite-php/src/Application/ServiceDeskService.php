<?php

declare(strict_types=1);

namespace ArcHub\Lite\Application;

use ArcHub\Lite\Domain\ServiceRequest;
use ArcHub\Lite\Domain\ServiceRequestRepository;

/**
 * Lite ITSM service-desk use cases: raise a request and walk it through a guarded
 * status workflow.
 */
final readonly class ServiceDeskService
{
    public function __construct(private ServiceRequestRepository $requests)
    {
    }

    /**
     * @param array{status?:string,type?:string,assignee?:string} $filters
     * @return list<ServiceRequest>
     */
    public function list(array $filters = []): array
    {
        return $this->requests->all($filters);
    }

    public function get(string $key): ?ServiceRequest
    {
        return $this->requests->findByKey($key);
    }

    /** @return array<string,int> */
    public function counts(): array
    {
        return $this->requests->counts();
    }

    /**
     * @return array{ok:bool,request?:ServiceRequest,error?:string}
     */
    public function create(string $type, string $summary, string $description, string $priority, string $requester): array
    {
        $summary = trim($summary);
        if ($summary === '') {
            return ['ok' => false, 'error' => 'summary_required'];
        }
        $type = in_array($type, ServiceRequest::TYPES, true) ? $type : 'incident';
        $priority = in_array($priority, ServiceRequest::PRIORITIES, true) ? $priority : 'medium';
        $requester = trim($requester) !== '' ? trim($requester) : 'anonymous';

        $request = new ServiceRequest(
            null,
            '',
            $type,
            $summary,
            $description,
            ServiceRequest::STATUS_OPEN,
            $priority,
            $requester,
        );
        return ['ok' => true, 'request' => $this->requests->create($request)];
    }

    /**
     * @return array{ok:bool,request?:ServiceRequest,error?:string}
     */
    public function transition(string $key, string $status): array
    {
        $request = $this->requests->findByKey($key);
        if ($request === null) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        if (!$request->canTransitionTo($status)) {
            return ['ok' => false, 'error' => 'illegal_transition'];
        }
        $request->status = $status;
        return ['ok' => true, 'request' => $this->requests->update($request)];
    }

    /**
     * @return array{ok:bool,request?:ServiceRequest,error?:string}
     */
    public function assign(string $key, string $assignee): array
    {
        $request = $this->requests->findByKey($key);
        if ($request === null) {
            return ['ok' => false, 'error' => 'not_found'];
        }
        $request->assignee = trim($assignee) !== '' ? trim($assignee) : null;
        return ['ok' => true, 'request' => $this->requests->update($request)];
    }
}
