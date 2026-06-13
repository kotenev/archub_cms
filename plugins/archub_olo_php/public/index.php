<?php

declare(strict_types=1);

use ArcHub\OloPlugin\ArcHubOloApplication;
use Symfony\Component\HttpFoundation\Request;

require dirname(__DIR__) . '/vendor/autoload.php';

$application = new ArcHubOloApplication(dirname(__DIR__));
$response = $application->handle(Request::createFromGlobals());
$response->send();
