<?php

declare(strict_types=1);

/**
 * CLI schema bootstrap for hosts that prefer a deploy step over auto-migration.
 *
 *   php bin/migrate.php            # create schema + seed demo content
 *   php bin/migrate.php --no-seed  # create schema only
 */

use ArcHub\Lite\Kernel\Autoloader;
use ArcHub\Lite\Kernel\Config;
use ArcHub\Lite\Kernel\Database;
use ArcHub\Lite\Infrastructure\Migrator;

require dirname(__DIR__) . '/src/Kernel/Autoloader.php';
Autoloader::register('ArcHub\\Lite', dirname(__DIR__) . '/src');

$configFile = dirname(__DIR__) . '/config.php';
$fileConfig = is_file($configFile) ? (array) require $configFile : [];
$config = Config::load($fileConfig);

$seed = !in_array('--no-seed', $argv, true) && $config->bool('seed_demo', true);

try {
    $pdo = (new Database($config))->pdo();
    (new Migrator($pdo))->migrate($seed);
    fwrite(STDOUT, "ArcHub Lite schema is ready" . ($seed ? " (demo content seeded)" : "") . ".\n");
    exit(0);
} catch (Throwable $e) {
    fwrite(STDERR, "Migration failed: " . $e->getMessage() . "\n");
    exit(1);
}
