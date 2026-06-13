<?php

declare(strict_types=1);

namespace ArcHub\Lite\Infrastructure;

use ArcHub\Lite\Domain\ServiceRequest;
use ArcHub\Lite\Domain\ServiceRequestRepository;
use PDO;

/**
 * PostgreSQL-backed service-desk repository.
 */
final class PdoServiceRequestRepository implements ServiceRequestRepository
{
    public function __construct(private PDO $pdo)
    {
    }

    public function all(array $filters = []): array
    {
        $sql = 'SELECT * FROM archub_lite_requests';
        $where = [];
        $params = [];
        foreach (['status', 'type', 'assignee'] as $field) {
            if (!empty($filters[$field])) {
                $where[] = "$field = :$field";
                $params[$field] = $filters[$field];
            }
        }
        if ($where !== []) {
            $sql .= ' WHERE ' . implode(' AND ', $where);
        }
        $sql .= ' ORDER BY id DESC';
        $stmt = $this->pdo->prepare($sql);
        $stmt->execute($params);
        return array_map(ServiceRequest::fromRow(...), $stmt->fetchAll());
    }

    public function findByKey(string $key): ?ServiceRequest
    {
        $stmt = $this->pdo->prepare('SELECT * FROM archub_lite_requests WHERE key = :key');
        $stmt->execute(['key' => $key]);
        $row = $stmt->fetch();
        return $row ? ServiceRequest::fromRow($row) : null;
    }

    public function create(ServiceRequest $request): ServiceRequest
    {
        $this->pdo->beginTransaction();
        try {
            $stmt = $this->pdo->prepare(
                "INSERT INTO archub_lite_requests (key, type, summary, description, status, priority, requester, assignee)
                 VALUES ('REQ-PENDING', :type, :summary, :description, :status, :priority, :requester, :assignee)
                 RETURNING id"
            );
            $stmt->execute([
                'type' => $request->type,
                'summary' => $request->summary,
                'description' => $request->description,
                'status' => $request->status,
                'priority' => $request->priority,
                'requester' => $request->requester,
                'assignee' => $request->assignee,
            ]);
            $id = (int) $stmt->fetchColumn();
            $key = 'REQ-' . $id;
            $this->pdo->prepare('UPDATE archub_lite_requests SET key = :key WHERE id = :id')
                ->execute(['key' => $key, 'id' => $id]);
            $this->pdo->commit();
        } catch (\Throwable $e) {
            $this->pdo->rollBack();
            throw $e;
        }
        return $this->findByKey($key) ?? $request;
    }

    public function update(ServiceRequest $request): ServiceRequest
    {
        $stmt = $this->pdo->prepare(
            'UPDATE archub_lite_requests
                SET type = :type, summary = :summary, description = :description, status = :status,
                    priority = :priority, requester = :requester, assignee = :assignee, updated_at = now()
              WHERE key = :key
             RETURNING *'
        );
        $stmt->execute([
            'type' => $request->type,
            'summary' => $request->summary,
            'description' => $request->description,
            'status' => $request->status,
            'priority' => $request->priority,
            'requester' => $request->requester,
            'assignee' => $request->assignee,
            'key' => $request->key,
        ]);
        return ServiceRequest::fromRow($stmt->fetch());
    }

    public function counts(): array
    {
        $rows = $this->pdo->query('SELECT status, count(*) AS n FROM archub_lite_requests GROUP BY status')
            ->fetchAll();
        $counts = ['total' => 0, 'open' => 0];
        foreach ($rows as $row) {
            $n = (int) $row['n'];
            $counts[$row['status']] = $n;
            $counts['total'] += $n;
        }
        $counts['open'] = ($counts[ServiceRequest::STATUS_OPEN] ?? 0)
            + ($counts[ServiceRequest::STATUS_IN_PROGRESS] ?? 0);
        return $counts;
    }
}
