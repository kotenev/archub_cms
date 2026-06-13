<?php

declare(strict_types=1);

/**
 * ArcHub Lite front controller. Point your nginx/Apache document root here
 * (the `public/` directory). No Composer or framework required.
 */

use ArcHub\Lite\App;
use ArcHub\Lite\Kernel\Autoloader;

require dirname(__DIR__) . '/src/Kernel/Autoloader.php';
Autoloader::register('ArcHub\\Lite', dirname(__DIR__) . '/src');

$configFile = dirname(__DIR__) . '/config.php';
$fileConfig = is_file($configFile) ? (array) require $configFile : [];

try {
    (new App($fileConfig))->runFromGlobals();
} catch (Throwable $e) {
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    $debug = ($fileConfig['debug'] ?? getenv('ARCHUB_LITE_DEBUG')) ? $e->getMessage() : 'internal_error';
    echo json_encode(['error' => 'internal_error', 'detail' => $debug], JSON_UNESCAPED_SLASHES);
}
