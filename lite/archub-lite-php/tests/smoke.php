<?php

declare(strict_types=1);

/**
 * Dependency-free smoke test for ArcHub Lite. Exercises routing, content
 * delivery, search, the service desk and admin auth against the in-memory
 * storage backend — no PostgreSQL required.
 *
 *   php tests/smoke.php
 */

use ArcHub\Lite\App;
use ArcHub\Lite\Kernel\Autoloader;
use ArcHub\Lite\Kernel\Request;
use ArcHub\Lite\Kernel\Response;

require dirname(__DIR__) . '/src/Kernel/Autoloader.php';
Autoloader::register('ArcHub\\Lite', dirname(__DIR__) . '/src');

$_SESSION = [];

$config = [
    'storage' => 'memory',
    'seed_demo' => true,
    'admin_password_hash' => password_hash('secret', PASSWORD_DEFAULT),
    'admin_token' => 'tok-123',
    'debug' => true,
];
$app = new App($config);

$failures = 0;
$count = 0;

/** @param array<string,string> $query @param array<string,mixed> $post @param array<string,string> $headers */
function call(App $app, string $method, string $path, array $query = [], array $post = [], string $body = '', array $headers = []): Response
{
    return $app->handle(new Request($method, $path, $query, $post, $headers, $body));
}

function check(string $label, bool $ok, string $detail = ''): void
{
    global $failures, $count;
    $count++;
    if (!$ok) {
        $failures++;
    }
    printf("%s %-46s %s\n", $ok ? 'PASS' : 'FAIL', $label, $detail);
}

// --- public delivery ---
$r = call($app, 'GET', '/health');
check('GET /health', $r->status === 200 && str_contains($r->body, 'ok'), "status={$r->status}");

$r = call($app, 'GET', '/');
check('GET / (home html)', $r->status === 200 && str_contains($r->body, 'ArcHub Lite'), "status={$r->status}");

$r = call($app, 'GET', '/api/content/tree');
$tree = json_decode($r->body, true);
check('GET /api/content/tree', $r->status === 200 && !empty($tree['items']), 'roots=' . count($tree['items'] ?? []));

$r = call($app, 'GET', '/api/content/welcome');
check('GET /api/content/welcome', $r->status === 200 && str_contains($r->body, '"slug": "welcome"'), "status={$r->status}");

$r = call($app, 'GET', '/api/content/draft-note');
check('GET draft is hidden from delivery', $r->status === 404, "status={$r->status}");

$r = call($app, 'GET', '/p/draft-note');
check('GET /p/draft-note (draft) -> 404', $r->status === 404, "status={$r->status}");

$r = call($app, 'GET', '/api/search', ['q' => 'delivery']);
$search = json_decode($r->body, true);
check('GET /api/search?q=delivery', $r->status === 200 && ($search['total'] ?? 0) >= 1, 'total=' . ($search['total'] ?? 0));

// --- public service desk ---
$r = call($app, 'POST', '/support', [], [
    'type' => 'incident', 'summary' => 'Printer down', 'description' => 'On floor 3',
    'priority' => 'high', 'requester' => 'user@example.com',
]);
$loc = $r->headers['Location'] ?? '';
check('POST /support creates + redirects', $r->status === 302 && str_contains($loc, '/support/REQ-'), "loc={$loc}");
$createdKey = substr($loc, (int) strrpos($loc, '/') + 1);

$r = call($app, 'GET', '/support/' . $createdKey);
check('GET /support/{key}', $r->status === 200 && str_contains($r->body, $createdKey), "status={$r->status}");

$r = call($app, 'POST', '/api/requests', [], [], json_encode(['summary' => 'API ticket', 'type' => 'question']) ?: '');
check('POST /api/requests (json) -> 201', $r->status === 201 && str_contains($r->body, '"key"'), "status={$r->status}");

// --- headless token-protected write ---
$r = call($app, 'POST', '/api/content', [], [], json_encode(['title' => 'X']) ?: '');
check('POST /api/content without token -> 401', $r->status === 401, "status={$r->status}");

$r = call($app, 'POST', '/api/content', [], [], json_encode(['title' => 'Released Notes', 'publish' => true]) ?: '', ['x-admin-token' => 'tok-123']);
check('POST /api/content with token -> 201', $r->status === 201 && str_contains($r->body, 'released-notes'), "status={$r->status}");

// --- admin auth ---
$r = call($app, 'GET', '/admin');
check('GET /admin unauthenticated -> redirect', $r->status === 302, "status={$r->status}");

$r = call($app, 'POST', '/admin/login', [], ['password' => 'wrong']);
check('POST /admin/login wrong -> 401', $r->status === 401, "status={$r->status}");

$r = call($app, 'POST', '/admin/login', [], ['password' => 'secret']);
check('POST /admin/login correct -> 302', $r->status === 302, "status={$r->status}");

$r = call($app, 'GET', '/admin');
check('GET /admin authenticated -> dashboard', $r->status === 200 && str_contains($r->body, 'Dashboard'), "status={$r->status}");

$r = call($app, 'POST', '/admin/pages', [], ['title' => 'New Guide', 'body' => 'Body', 'publish' => '1']);
check('POST /admin/pages create -> 302', $r->status === 302, "status={$r->status}");

$r = call($app, 'GET', '/api/content/new-guide');
check('created page is published in delivery', $r->status === 200, "status={$r->status}");

// --- workflow guard ---
$r = call($app, 'POST', '/admin/requests/' . $createdKey . '/transition', [], ['status' => 'in_progress']);
check('transition open -> in_progress', $r->status === 200, "status={$r->status}");

$r = call($app, 'POST', '/admin/requests/' . $createdKey . '/transition', [], ['status' => 'open']);
check('transition in_progress -> open (legal)', $r->status === 200, "status={$r->status}");

$r = call($app, 'POST', '/admin/requests/' . $createdKey . '/transition', [], ['status' => 'resolved']);
$r = call($app, 'POST', '/admin/requests/' . $createdKey . '/transition', [], ['status' => 'closed']);
$r = call($app, 'POST', '/admin/requests/' . $createdKey . '/transition', [], ['status' => 'resolved']);
check('illegal transition closed -> resolved -> 409', $r->status === 409, "status={$r->status}");

$r = call($app, 'GET', '/admin/logout');
check('GET /admin/logout -> redirect', $r->status === 302, "status={$r->status}");

$r = call($app, 'GET', '/nope');
check('GET /nope -> 404', $r->status === 404, "status={$r->status}");

echo "\n";
printf("%d checks, %d failures\n", $count, $failures);
exit($failures === 0 ? 0 : 1);
