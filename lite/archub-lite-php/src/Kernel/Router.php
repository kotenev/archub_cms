<?php

declare(strict_types=1);

namespace ArcHub\Lite\Kernel;

/**
 * Tiny path-parameter router. Patterns use `{name}` placeholders, e.g.
 * `/admin/pages/{id}/edit`. Handlers receive (Request, array<string,string> $params).
 */
final class Router
{
    /** @var list<array{method:string,regex:string,params:list<string>,handler:callable}> */
    private array $routes = [];

    public function add(string $method, string $pattern, callable $handler): void
    {
        $params = [];
        $regex = preg_replace_callback(
            '/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/',
            static function (array $m) use (&$params): string {
                $params[] = $m[1];
                return '([^/]+)';
            },
            $pattern,
        );
        $this->routes[] = [
            'method' => strtoupper($method),
            'regex' => '#^' . $regex . '$#',
            'params' => $params,
            'handler' => $handler,
        ];
    }

    public function get(string $pattern, callable $handler): void
    {
        $this->add('GET', $pattern, $handler);
    }

    public function post(string $pattern, callable $handler): void
    {
        $this->add('POST', $pattern, $handler);
    }

    public function dispatch(Request $request): Response
    {
        $allowed = false;
        foreach ($this->routes as $route) {
            if (!preg_match($route['regex'], $request->path, $matches)) {
                continue;
            }
            if ($route['method'] !== $request->method) {
                $allowed = true;
                continue;
            }
            $params = [];
            foreach ($route['params'] as $index => $name) {
                $params[$name] = rawurldecode($matches[$index + 1]);
            }
            return ($route['handler'])($request, $params);
        }

        if ($allowed) {
            return $this->notFound($request, 'method_not_allowed', 405);
        }
        return $this->notFound($request, 'not_found', 404);
    }

    private function notFound(Request $request, string $error, int $status): Response
    {
        if ($request->wantsJson()) {
            return Response::json(['error' => $error, 'path' => $request->path], $status);
        }
        return Response::html(
            '<!doctype html><meta charset="utf-8"><title>' . $status . '</title>'
            . '<h1>' . $status . '</h1><p>' . htmlspecialchars($error) . '</p>',
            $status,
        );
    }
}
