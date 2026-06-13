<?php

declare(strict_types=1);

namespace ArcHub\Lite\Application;

use ArcHub\Lite\Kernel\Config;
use ArcHub\Lite\Kernel\Request;

/**
 * Minimal authentication for the admin surface, sized for shared hosting:
 *  - a browser session established by a password (compared to a configured hash);
 *  - a shared-secret token (X-Admin-Token) for write API calls.
 *
 * If no admin password hash is configured, the admin UI is locked entirely
 * (read-only public site only) — safe by default.
 */
final class Auth
{
    private const SESSION_KEY = 'archub_lite_admin';

    public function __construct(private Config $config)
    {
    }

    public function startSession(): void
    {
        if (PHP_SAPI !== 'cli' && session_status() === PHP_SESSION_NONE) {
            session_start();
        }
    }

    public function configured(): bool
    {
        return $this->config->str('admin_password_hash') !== '';
    }

    public function attemptLogin(string $password): bool
    {
        $hash = $this->config->str('admin_password_hash');
        if ($hash === '' || !password_verify($password, $hash)) {
            return false;
        }
        $_SESSION[self::SESSION_KEY] = true;
        return true;
    }

    public function logout(): void
    {
        unset($_SESSION[self::SESSION_KEY]);
    }

    public function isAdmin(): bool
    {
        return !empty($_SESSION[self::SESSION_KEY]);
    }

    /** API write authorization via shared-secret token (constant-time compare). */
    public function tokenValid(Request $request): bool
    {
        $token = $this->config->str('admin_token');
        if ($token === '') {
            return false;
        }
        $provided = $request->header('x-admin-token');
        return $provided !== '' && hash_equals($token, $provided);
    }
}
