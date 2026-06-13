<?php

declare(strict_types=1);

namespace ArcHub\Lite\Kernel;

/**
 * Tiny PSR-4 autoloader so ArcHub Lite runs on shared hosting with **no Composer**.
 *
 * Upload the folder over FTP and it works — `require src/Kernel/Autoloader.php`
 * then `Autoloader::register()`.
 */
final class Autoloader
{
    public function __construct(
        private string $prefix,
        private string $baseDir,
    ) {
        $this->prefix = trim($prefix, '\\') . '\\';
        $this->baseDir = rtrim($baseDir, '/') . '/';
    }

    public static function register(string $prefix = 'ArcHub\\Lite', ?string $baseDir = null): void
    {
        $baseDir ??= __DIR__ . '/..';
        $loader = new self($prefix, $baseDir);
        spl_autoload_register($loader->load(...));
    }

    public function load(string $class): void
    {
        if (!str_starts_with($class, $this->prefix)) {
            return;
        }
        $relative = substr($class, strlen($this->prefix));
        $file = $this->baseDir . str_replace('\\', '/', $relative) . '.php';
        if (is_file($file)) {
            require $file;
        }
    }
}
