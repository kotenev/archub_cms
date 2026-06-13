<?php

declare(strict_types=1);

namespace ArcHub\Lite\Kernel;

/**
 * Minimal HTTP request wrapper over PHP superglobals — no framework required.
 */
final class Request
{
    /**
     * @param array<string,string> $query
     * @param array<string,mixed>  $post
     * @param array<string,string> $headers lower-cased header names
     */
    public function __construct(
        public readonly string $method,
        public readonly string $path,
        public readonly array $query,
        public readonly array $post,
        public readonly array $headers,
        public readonly string $body,
    ) {
    }

    public static function fromGlobals(string $basePath = ''): self
    {
        $uri = (string) ($_SERVER['REQUEST_URI'] ?? '/');
        $path = parse_url($uri, PHP_URL_PATH);
        $path = is_string($path) ? rawurldecode($path) : '/';

        if ($basePath !== '' && str_starts_with($path, $basePath)) {
            $path = substr($path, strlen($basePath));
        }
        $path = '/' . trim($path, '/');

        $headers = [];
        foreach ($_SERVER as $key => $value) {
            if (str_starts_with($key, 'HTTP_')) {
                $name = strtolower(str_replace('_', '-', substr($key, 5)));
                $headers[$name] = (string) $value;
            }
        }

        return new self(
            strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET')),
            $path,
            array_map('strval', $_GET),
            $_POST,
            $headers,
            (string) file_get_contents('php://input'),
        );
    }

    public function query(string $key, string $default = ''): string
    {
        return isset($this->query[$key]) ? (string) $this->query[$key] : $default;
    }

    public function input(string $key, string $default = ''): string
    {
        return isset($this->post[$key]) ? trim((string) $this->post[$key]) : $default;
    }

    public function header(string $name, string $default = ''): string
    {
        return $this->headers[strtolower($name)] ?? $default;
    }

    /** @return array<string,mixed> */
    public function json(): array
    {
        $decoded = json_decode($this->body, true);
        return is_array($decoded) ? $decoded : [];
    }

    public function wantsJson(): bool
    {
        return str_starts_with($this->path, '/api/')
            || str_contains($this->header('accept'), 'application/json');
    }
}
