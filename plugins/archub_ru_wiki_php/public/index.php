<?php

declare(strict_types=1);

use ArcHub\WikiPlugin\ArcHubWikiApplication;
use Symfony\Component\HttpFoundation\Request;

require dirname(__DIR__) . '/vendor/autoload.php';

$application = new ArcHubWikiApplication(dirname(__DIR__));
$response = $application->handle(Request::createFromGlobals());
$response->send();
