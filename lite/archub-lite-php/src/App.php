<?php

declare(strict_types=1);

namespace ArcHub\Lite;

use ArcHub\Lite\Application\Auth;
use ArcHub\Lite\Application\ContentService;
use ArcHub\Lite\Application\ServiceDeskService;
use ArcHub\Lite\Domain\Page;
use ArcHub\Lite\Domain\PageRepository;
use ArcHub\Lite\Domain\ServiceRequestRepository;
use ArcHub\Lite\Infrastructure\InMemoryPageRepository;
use ArcHub\Lite\Infrastructure\InMemoryServiceRequestRepository;
use ArcHub\Lite\Infrastructure\Migrator;
use ArcHub\Lite\Infrastructure\PdoPageRepository;
use ArcHub\Lite\Infrastructure\PdoServiceRequestRepository;
use ArcHub\Lite\Kernel\Config;
use ArcHub\Lite\Kernel\Database;
use ArcHub\Lite\Kernel\Request;
use ArcHub\Lite\Kernel\Response;
use ArcHub\Lite\Kernel\Router;
use ArcHub\Lite\Renderer\AdminRenderer;
use ArcHub\Lite\Renderer\Layout;
use ArcHub\Lite\Renderer\SiteRenderer;

/**
 * Composition root and HTTP routing for ArcHub Lite.
 */
final class App
{
    private Config $config;
    private ContentService $content;
    private ServiceDeskService $desk;
    private Auth $auth;
    private Layout $layout;
    private SiteRenderer $site;
    private AdminRenderer $admin;
    private Router $router;

    /** @param array<string,mixed> $fileConfig */
    public function __construct(array $fileConfig = [], ?PageRepository $pages = null, ?ServiceRequestRepository $requests = null)
    {
        $this->config = Config::load($fileConfig);

        if ($pages === null || $requests === null) {
            [$pages, $requests] = $this->buildRepositories();
        }

        $this->content = new ContentService($pages);
        $this->desk = new ServiceDeskService($requests);
        $this->auth = new Auth($this->config);
        $this->layout = new Layout($this->config);
        $this->site = new SiteRenderer($this->layout);
        $this->admin = new AdminRenderer($this->layout);
        $this->router = new Router();
        $this->registerRoutes();
    }

    public function handle(Request $request): Response
    {
        $this->auth->startSession();
        return $this->router->dispatch($request);
    }

    public function runFromGlobals(): void
    {
        $request = Request::fromGlobals($this->config->basePath());
        $this->handle($request)->send();
    }

    public function config(): Config
    {
        return $this->config;
    }

    /** @return array{0:PageRepository,1:ServiceRequestRepository} */
    private function buildRepositories(): array
    {
        if ($this->config->str('storage', 'pgsql') === 'memory') {
            $seed = $this->config->bool('seed_demo', true);
            return [new InMemoryPageRepository($seed), new InMemoryServiceRequestRepository($seed)];
        }
        $pdo = (new Database($this->config))->pdo();
        (new Migrator($pdo))->migrate($this->config->bool('seed_demo', true));
        return [new PdoPageRepository($pdo), new PdoServiceRequestRepository($pdo)];
    }

    private function registerRoutes(): void
    {
        $r = $this->router;

        // --- public site ---
        $r->get('/', fn () => Response::html($this->site->home($this->content->publishedTree())));
        $r->get('/health', fn () => Response::json(['status' => 'ok', 'app' => 'archub-lite']));
        $r->get('/p/{slug}', function (Request $req, array $p): Response {
            $page = $this->content->publishedPage($p['slug']);
            if ($page === null) {
                return Response::html($this->layout->render('Not found', '<h1>404</h1><p>Page not found.</p>'), 404);
            }
            return Response::html($this->site->page($page, $this->content->publishedChildren($page->id)));
        });
        $r->get('/search', function (Request $req): Response {
            $q = $req->query('q');
            return Response::html($this->site->search($q, $q === '' ? [] : $this->content->search($q)));
        });

        // --- public service desk ---
        $r->get('/support', fn () => Response::html($this->site->supportForm()));
        $r->post('/support', function (Request $req): Response {
            $result = $this->desk->create(
                $req->input('type'),
                $req->input('summary'),
                $req->input('description'),
                $req->input('priority', 'medium'),
                $req->input('requester'),
            );
            if (!$result['ok']) {
                return Response::html($this->site->supportForm($result['error']), 422);
            }
            return Response::redirect($this->config->url('/support/' . $result['request']->key));
        });
        $r->get('/support/{key}', function (Request $req, array $p): Response {
            $request = $this->desk->get($p['key']);
            if ($request === null) {
                return Response::html($this->layout->render('Not found', '<h1>404</h1>'), 404);
            }
            return Response::html($this->site->requestStatus($request));
        });

        // --- headless delivery API ---
        $r->get('/api/health', fn () => Response::json(['status' => 'ok', 'app' => 'archub-lite']));
        $r->get('/api/content/tree', fn () => Response::json(['items' => $this->content->publishedTree()]));
        $r->get('/api/content/{slug}', function (Request $req, array $p): Response {
            $page = $this->content->publishedPage($p['slug']);
            return $page === null
                ? Response::json(['error' => 'not_found', 'slug' => $p['slug']], 404)
                : Response::json($page->toArray());
        });
        $r->get('/api/search', function (Request $req): Response {
            $q = $req->query('q');
            $items = array_map(static fn (array $hit) => $hit['page']->toArray() + [
                'rank' => $hit['rank'],
                'excerpt' => strip_tags($hit['excerpt']),
            ], $q === '' ? [] : $this->content->search($q));
            return Response::json(['query' => $q, 'items' => $items, 'total' => count($items)]);
        });
        $r->post('/api/requests', function (Request $req): Response {
            $data = $req->json();
            $result = $this->desk->create(
                (string) ($data['type'] ?? 'incident'),
                (string) ($data['summary'] ?? ''),
                (string) ($data['description'] ?? ''),
                (string) ($data['priority'] ?? 'medium'),
                (string) ($data['requester'] ?? 'anonymous'),
            );
            return $result['ok']
                ? Response::json($result['request']->toArray(), 201)
                : Response::json(['error' => $result['error']], 422);
        });
        // Token-protected headless write: create a page.
        $r->post('/api/content', function (Request $req): Response {
            if (!$this->auth->tokenValid($req)) {
                return Response::json(['error' => 'unauthorized'], 401);
            }
            $data = $req->json();
            $result = $this->content->createPage(
                (string) ($data['title'] ?? ''),
                (string) ($data['slug'] ?? ''),
                (string) ($data['body'] ?? ''),
                isset($data['parent_id']) ? (int) $data['parent_id'] : null,
                (int) ($data['sort'] ?? 0),
                (bool) ($data['publish'] ?? false),
            );
            return $result['ok']
                ? Response::json($result['page']->toArray(), 201)
                : Response::json(['error' => $result['error']], 422);
        });

        $this->registerAdminRoutes();
    }

    private function registerAdminRoutes(): void
    {
        $r = $this->router;

        $r->get('/admin/login', fn () => $this->auth->configured()
            ? Response::html($this->site->login())
            : Response::html($this->site->adminLocked(), 403));
        $r->post('/admin/login', function (Request $req): Response {
            if (!$this->auth->configured()) {
                return Response::html($this->site->adminLocked(), 403);
            }
            if ($this->auth->attemptLogin($req->input('password'))) {
                return Response::redirect($this->config->url('/admin'));
            }
            return Response::html($this->site->login('Invalid password.'), 401);
        });
        $r->get('/admin/logout', function (): Response {
            $this->auth->logout();
            return Response::redirect($this->config->url('/'));
        });

        $r->get('/admin', $this->guard(function (): Response {
            $pages = $this->content->allPages();
            $published = count(array_filter($pages, static fn (Page $p) => $p->isPublished()));
            return Response::html($this->admin->dashboard(count($pages), $published, $this->desk->counts()));
        }));

        $r->get('/admin/pages', $this->guard(fn () => Response::html($this->admin->pages($this->content->allPages()))));
        $r->get('/admin/pages/new', $this->guard(fn () => Response::html($this->admin->pageForm($this->content->allPages()))));
        $r->post('/admin/pages', $this->guard(function (Request $req): Response {
            $result = $this->content->createPage(
                $req->input('title'),
                $req->input('slug'),
                $req->input('body'),
                $this->intOrNull($req->input('parent_id')),
                (int) $req->input('sort', '0'),
                $req->input('publish') === '1',
            );
            if (!$result['ok']) {
                return Response::html($this->admin->pageForm($this->content->allPages(), null, $result['error']), 422);
            }
            return Response::redirect($this->config->url('/admin/pages'));
        }));
        $r->get('/admin/pages/{id}/edit', $this->guard(function (Request $req, array $p): Response {
            $page = $this->content->find((int) $p['id']);
            if ($page === null) {
                return Response::redirect($this->config->url('/admin/pages'));
            }
            return Response::html($this->admin->pageForm($this->content->allPages(), $page));
        }));
        $r->post('/admin/pages/{id}', $this->guard(function (Request $req, array $p): Response {
            $result = $this->content->updatePage(
                (int) $p['id'],
                $req->input('title'),
                $req->input('slug'),
                $req->input('body'),
                $this->intOrNull($req->input('parent_id')),
                (int) $req->input('sort', '0'),
            );
            if (!$result['ok']) {
                $page = $this->content->find((int) $p['id']);
                return Response::html($this->admin->pageForm($this->content->allPages(), $page, $result['error']), 422);
            }
            return Response::redirect($this->config->url('/admin/pages'));
        }));
        $r->post('/admin/pages/{id}/publish', $this->guard(function (Request $req, array $p): Response {
            $this->content->setPublished((int) $p['id'], true);
            return Response::redirect($this->config->url('/admin/pages'));
        }));
        $r->post('/admin/pages/{id}/unpublish', $this->guard(function (Request $req, array $p): Response {
            $this->content->setPublished((int) $p['id'], false);
            return Response::redirect($this->config->url('/admin/pages'));
        }));
        $r->post('/admin/pages/{id}/delete', $this->guard(function (Request $req, array $p): Response {
            $this->content->deletePage((int) $p['id']);
            return Response::redirect($this->config->url('/admin/pages'));
        }));

        $r->get('/admin/requests', $this->guard(function (Request $req): Response {
            $filters = array_filter(['status' => $req->query('status'), 'type' => $req->query('type')]);
            return Response::html($this->admin->requests($this->desk->list($filters), $this->desk->counts()));
        }));
        $r->get('/admin/requests/{key}', $this->guard(function (Request $req, array $p): Response {
            $request = $this->desk->get($p['key']);
            if ($request === null) {
                return Response::redirect($this->config->url('/admin/requests'));
            }
            return Response::html($this->admin->requestDetail($request));
        }));
        $r->post('/admin/requests/{key}/transition', $this->guard(function (Request $req, array $p): Response {
            $result = $this->desk->transition($p['key'], $req->input('status'));
            if (!$result['ok'] && $result['error'] === 'not_found') {
                return Response::redirect($this->config->url('/admin/requests'));
            }
            $request = $result['ok'] ? $result['request'] : $this->desk->get($p['key']);
            $error = $result['ok'] ? null : 'Illegal transition.';
            return Response::html($this->admin->requestDetail($request, $error), $result['ok'] ? 200 : 409);
        }));
        $r->post('/admin/requests/{key}/assign', $this->guard(function (Request $req, array $p): Response {
            $this->desk->assign($p['key'], $req->input('assignee'));
            return Response::redirect($this->config->url('/admin/requests/' . $p['key']));
        }));
    }

    /** Wrap an admin handler with the session guard. */
    private function guard(callable $handler): callable
    {
        return function (Request $req, array $params = []) use ($handler): Response {
            if (!$this->auth->configured()) {
                return Response::html($this->site->adminLocked(), 403);
            }
            if (!$this->auth->isAdmin()) {
                return Response::redirect($this->config->url('/admin/login'));
            }
            return $handler($req, $params);
        };
    }

    private function intOrNull(string $value): ?int
    {
        return $value === '' ? null : (int) $value;
    }
}
