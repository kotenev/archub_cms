<?php

declare(strict_types=1);

namespace ArcHub\OloPlugin;

use ArcHub\OloPlugin\Application\TaskService;
use ArcHub\OloPlugin\Infrastructure\SeedTaskRepository;
use ArcHub\OloPlugin\Renderer\TaskRenderer;
use DateTimeImmutable;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;

final readonly class ArcHubOloApplication
{
    private TaskService $tasks;
    private TaskRenderer $renderer;

    public function __construct(private string $rootPath /** @phpstan-ignore property.onlyWritten */, ?DateTimeImmutable $now = null)
    {
        $clock = $now ?? new DateTimeImmutable('2026-06-13T09:00:00Z');
        $this->tasks = new TaskService(new SeedTaskRepository(), $clock);
        $this->renderer = new TaskRenderer($this->tasks);
    }

    public function handle(Request $request): Response
    {
        $path = '/' . trim($request->getPathInfo(), '/');
        $path = $path === '/' ? '/' : rtrim($path, '/');

        return match (true) {
            $path === '/' => $this->html($this->renderer->dashboard()),
            $path === '/health' => $this->json(['status' => 'ok', 'plugin' => 'archub.olo.php']),
            $path === '/api/arc-tool' && $request->getMethod() === 'POST' => $this->arcTool($request),
            $path === '/api/olo/overview' => $this->json($this->tasks->overview()),
            $path === '/api/olo/tasks' => $this->json(['items' => $this->tasks->tasks()]),
            $path === '/api/olo/outline' => $this->json(['items' => $this->tasks->outline()]),
            $path === '/api/olo/todo' => $this->json(['items' => $this->tasks->todo()]),
            $path === '/api/olo/next-actions' => $this->json(['items' => $this->tasks->nextActions()]),
            $path === '/api/olo/inbox' => $this->json(['items' => $this->tasks->inbox()]),
            $path === '/api/olo/today' => $this->json(['items' => $this->tasks->today()]),
            $path === '/api/olo/overdue' => $this->json(['items' => $this->tasks->overdue()]),
            $path === '/api/olo/starred' => $this->json(['items' => $this->tasks->starred()]),
            $path === '/api/olo/due-soon' => $this->json([
                'items' => $this->tasks->dueSoon((int) $request->query->get('days', 7)),
            ]),
            $path === '/api/olo/contexts' => $this->json(['items' => $this->tasks->contexts()]),
            $path === '/api/olo/reports/summary' => $this->json(['items' => $this->tasks->summaryReport()]),
            $path === '/api/olo/events' => $this->json(['items' => $this->tasks->events()]),
            $path === '/api/olo/search' => $this->json($this->tasks->search((string) $request->query->get('q', ''))),
            str_starts_with($path, '/api/olo/contexts/') => $this->json([
                'items' => $this->tasks->tasksInContext(substr($path, 18)),
            ]),
            str_starts_with($path, '/api/olo/recurrence/') => $this->recurrence(substr($path, 20)),
            str_starts_with($path, '/api/olo/tasks/') => $this->json($this->tasks->task(substr($path, 15))),
            str_starts_with($path, '/tasks/') => $this->taskPage(substr($path, 7)),
            str_starts_with($path, '/context/') => $this->html($this->renderer->contextView(substr($path, 9))),
            str_starts_with($path, '/view/') => $this->viewPage(substr($path, 6)),
            default => $this->json(['error' => 'not_found', 'path' => $path], Response::HTTP_NOT_FOUND),
        };
    }

    private function arcTool(Request $request): JsonResponse
    {
        $payload = json_decode($request->getContent(), true);
        $arguments = is_array($payload) ? ($payload['arguments'] ?? []) : [];
        $query = is_array($arguments) ? (string) ($arguments['query'] ?? '') : '';
        $result = $query === ''
            ? ['overview' => $this->tasks->overview(), 'todo' => $this->tasks->todo()]
            : $this->tasks->search($query);

        return $this->json([
            'result' => json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
            'source' => 'archub.olo.php',
        ]);
    }

    private function recurrence(string $id): JsonResponse
    {
        $preview = $this->tasks->recurrencePreview($id);
        if ($preview === null) {
            return $this->json(['error' => 'task_not_found', 'id' => $id], Response::HTTP_NOT_FOUND);
        }
        return $this->json($preview);
    }

    private function taskPage(string $id): Response
    {
        $task = $this->tasks->task($id);
        if ($task === null) {
            return $this->json(['error' => 'task_not_found', 'id' => $id], Response::HTTP_NOT_FOUND);
        }
        return $this->html($this->renderer->task($task));
    }

    private function viewPage(string $view): Response
    {
        $items = match ($view) {
            'todo' => $this->tasks->todo(),
            'next-actions' => $this->tasks->nextActions(),
            'inbox' => $this->tasks->inbox(),
            'today' => $this->tasks->today(),
            'overdue' => $this->tasks->overdue(),
            'starred' => $this->tasks->starred(),
            default => null,
        };
        if ($items === null) {
            return $this->json(['error' => 'unknown_view', 'view' => $view], Response::HTTP_NOT_FOUND);
        }
        return $this->html($this->renderer->view($view, $items));
    }

    private function html(string $body): Response
    {
        return new Response($body, Response::HTTP_OK, ['Content-Type' => 'text/html; charset=utf-8']);
    }

    private function json(?array $payload, int $status = Response::HTTP_OK): JsonResponse
    {
        if ($payload === null) {
            return new JsonResponse(['error' => 'not_found'], Response::HTTP_NOT_FOUND);
        }
        return new JsonResponse($payload, $status);
    }
}
