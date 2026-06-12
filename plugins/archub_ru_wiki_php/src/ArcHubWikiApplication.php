<?php

declare(strict_types=1);

namespace ArcHub\WikiPlugin;

use ArcHub\WikiPlugin\Application\WikiService;
use ArcHub\WikiPlugin\Infrastructure\SeedWikiRepository;
use ArcHub\WikiPlugin\Renderer\WikiRenderer;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;

final readonly class ArcHubWikiApplication
{
    private WikiService $wiki;
    private WikiRenderer $renderer;

    public function __construct(private string $rootPath)
    {
        $this->wiki = new WikiService(new SeedWikiRepository());
        $this->renderer = new WikiRenderer($this->wiki);
    }

    public function handle(Request $request): Response
    {
        $path = '/' . trim($request->getPathInfo(), '/');
        $path = $path === '/' ? '/' : rtrim($path, '/');

        return match (true) {
            $path === '/' => $this->html($this->renderer->dashboard()),
            $path === '/health' => $this->json(['status' => 'ok', 'plugin' => 'archub.ru.wiki.php']),
            $path === '/api/arc-tool' && $request->getMethod() === 'POST' => $this->arcTool($request),
            $path === '/api/wiki/overview' => $this->json($this->wiki->overview()),
            $path === '/api/wiki/spaces' => $this->json(['items' => $this->wiki->spaces()]),
            $path === '/api/wiki/pages' => $this->json(['items' => $this->wiki->pages()]),
            $path === '/api/wiki/search' => $this->json($this->wiki->search((string) $request->query->get('q', ''))),
            $path === '/api/wiki/graph' => $this->json($this->wiki->graph()),
            $path === '/api/wiki/diagrams' => $this->json(['items' => $this->wiki->diagrams()]),
            str_starts_with($path, '/api/wiki/pages/') => $this->json($this->wiki->page(substr($path, 16))),
            str_starts_with($path, '/api/wiki/diagrams/') => $this->diagramXml(substr($path, 19)),
            str_starts_with($path, '/wiki/') => $this->wikiPage(substr($path, 6)),
            str_starts_with($path, '/diagrams/') => $this->html($this->renderer->diagramEditor(substr($path, 10))),
            default => $this->json(['error' => 'not_found', 'path' => $path], Response::HTTP_NOT_FOUND),
        };
    }

    private function arcTool(Request $request): JsonResponse
    {
        $payload = json_decode($request->getContent(), true);
        $arguments = is_array($payload) ? ($payload['arguments'] ?? []) : [];
        $query = is_array($arguments) ? (string) ($arguments['query'] ?? '') : '';
        $result = $query === '' ? $this->wiki->overview() : $this->wiki->search($query);

        return $this->json([
            'result' => json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES),
            'source' => 'archub.ru.wiki.php',
        ]);
    }

    private function wikiPage(string $slug): Response
    {
        $page = $this->wiki->page($slug);
        if ($page === null) {
            return $this->json(['error' => 'page_not_found', 'slug' => $slug], Response::HTTP_NOT_FOUND);
        }
        return $this->html($this->renderer->page($page));
    }

    private function diagramXml(string $id): Response
    {
        $id = preg_replace('/\.drawio$/', '', $id) ?? $id;
        $diagram = $this->wiki->diagram($id);
        if ($diagram === null) {
            return $this->json(['error' => 'diagram_not_found', 'id' => $id], Response::HTTP_NOT_FOUND);
        }
        return new Response($diagram['mxfile'], Response::HTTP_OK, ['Content-Type' => 'application/xml']);
    }

    private function html(string $body): Response
    {
        return new Response($body, Response::HTTP_OK, ['Content-Type' => 'text/html; charset=utf-8']);
    }

    private function json(array $payload, int $status = Response::HTTP_OK): JsonResponse
    {
        return new JsonResponse($payload, $status);
    }
}
