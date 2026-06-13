<?php

declare(strict_types=1);

namespace ArcHub\Lite\Kernel;

use PDO;
use PDOException;
use RuntimeException;

/**
 * PostgreSQL connection factory (PDO). Lazily connects so the in-memory storage
 * mode and CLI tooling never require a database.
 */
final class Database
{
    private ?PDO $pdo = null;

    public function __construct(private Config $config)
    {
    }

    public function pdo(): PDO
    {
        if ($this->pdo instanceof PDO) {
            return $this->pdo;
        }

        $dsn = $this->config->str('db_dsn');
        if ($dsn === '') {
            $dsn = sprintf(
                'pgsql:host=%s;port=%s;dbname=%s',
                $this->config->str('db_host'),
                $this->config->str('db_port'),
                $this->config->str('db_name'),
            );
        }

        try {
            $this->pdo = new PDO(
                $dsn,
                $this->config->str('db_user'),
                $this->config->str('db_password'),
                [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false,
                ],
            );
        } catch (PDOException $e) {
            throw new RuntimeException('ArcHub Lite cannot connect to PostgreSQL: ' . $e->getMessage(), 0, $e);
        }

        return $this->pdo;
    }
}
